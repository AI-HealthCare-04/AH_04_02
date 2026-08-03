import json

from rag.public_api_master import (
    prune_unverified_empty_records,
    records_to_documents,
    write_records,
)

from rag import dur_master, mfds_client


def _drug_payload(name: str) -> dict:
    return {
        "itemSeq": "123",
        "itemName": name,
        "entpName": "테스트제약",
        "efcyQesitm": "통증을 완화합니다.",
        "useMethodQesitm": "정해진 용법대로 복용합니다.",
    }


def test_master_lookup_normalizes_name_and_avoids_live_api(tmp_path, monkeypatch):
    path = tmp_path / "master.jsonl"
    write_records(
        [{"record_type": "drug_info", "lookup_name": "테스트정 5mg", "items": [_drug_payload("테스트정5mg")]}],
        path,
    )
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_MASTER_PATH", str(path))
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_MASTER_ENABLED", True)
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_LIVE_FALLBACK", False)
    monkeypatch.setattr(mfds_client, "_request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))

    result = mfds_client.search_by_name("테스트정-5mg")

    assert result[0].item_name == "테스트정5mg"


def test_master_miss_is_fast_when_live_fallback_is_disabled(tmp_path, monkeypatch):
    path = tmp_path / "master.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_MASTER_PATH", str(path))
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_MASTER_ENABLED", True)
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_LIVE_FALLBACK", False)
    monkeypatch.setattr(mfds_client, "_request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))

    assert mfds_client.search_by_name("없는약") == []


def test_master_records_become_rag_documents(tmp_path):
    path = tmp_path / "master.jsonl"
    write_records(
        [{"record_type": "drug_info", "lookup_name": "테스트정", "items": [_drug_payload("테스트정")]}],
        path,
    )

    documents = records_to_documents(path)

    assert len(documents) == 1
    assert documents[0].metadata["doc_type"] == "public_api_master"
    assert documents[0].metadata["record_type"] == "drug_info"
    assert "통증을 완화합니다" in documents[0].page_content


def test_master_file_is_compact_jsonl(tmp_path):
    path = tmp_path / "master.jsonl"
    write_records([{"record_type": "drug_info", "lookup_name": "테스트정", "items": []}], path)
    parsed = json.loads(path.read_text(encoding="utf-8").strip())
    assert parsed["version"] == 1
    assert parsed["status"] == "empty"
    assert parsed["items"] == []


def test_master_miss_uses_safe_live_drug_fallback_by_default(tmp_path, monkeypatch):
    path = tmp_path / "master.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_MASTER_PATH", str(path))
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_MASTER_ENABLED", True)
    monkeypatch.setattr(mfds_client.settings, "PUBLIC_API_LIVE_FALLBACK", True)
    response = {
        "header": {"resultCode": "00"},
        "body": {"items": [_drug_payload("마스터에없는약")]},
    }
    monkeypatch.setattr(mfds_client, "_request", lambda *args, **kwargs: response)

    result = mfds_client.search_by_name("마스터에없는약")

    assert result[0].item_name == "마스터에없는약"


def test_master_miss_uses_safe_live_dur_fallback_by_default(tmp_path, monkeypatch):
    path = tmp_path / "master.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(dur_master.settings, "PUBLIC_API_MASTER_PATH", str(path))
    monkeypatch.setattr(dur_master.settings, "PUBLIC_API_MASTER_ENABLED", True)
    monkeypatch.setattr(dur_master.settings, "PUBLIC_API_LIVE_FALLBACK", True)
    response = {
        "header": {"resultCode": "00"},
        "body": {
            "items": [
                {
                    "ITEM_NAME": "마스터에없는약",
                    "PROHBT_CONTENT": "특정 연령에서는 사용하지 않습니다.",
                }
            ]
        },
    }
    monkeypatch.setattr(dur_master, "_request", lambda *args, **kwargs: response)

    result = dur_master.search_age_taboo("마스터에없는약")

    assert len(result) == 1
    assert result[0].detail == "특정 연령에서는 사용하지 않습니다."


def test_prune_removes_legacy_empty_rows_but_keeps_verified_data(tmp_path):
    path = tmp_path / "master.jsonl"
    write_records(
        [
            {"record_type": "drug_info", "lookup_name": "있는약", "items": [_drug_payload("있는약")]},
            {"record_type": "drug_info", "lookup_name": "불명확한빈약", "items": []},
        ],
        path,
    )

    assert prune_unverified_empty_records(path) == 1
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["lookup_name"] for row in rows] == ["있는약"]
    assert rows[0]["status"] == "ok"
