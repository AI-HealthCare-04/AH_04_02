from unittest.mock import patch

from rag.dur_master import (
    search_age_taboo,
    search_elderly_caution,
    search_pregnancy_taboo,
    search_usjnt_taboo,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _ok(items: list[dict]) -> dict:
    return {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {"pageNo": 1, "totalCount": len(items), "numOfRows": len(items), "items": items},
    }


USJNT_TABOO_RESPONSE = _ok(
    [
        {
            "ITEM_NAME": "와파린정",
            "MIXTURE_ITEM_NAME": "아스피린정",
            "PROHBT_CONTENT": "출혈 위험 증가로 병용을 피하십시오.",
        },
        # 제조사만 다른 중복 브랜드 — dedup 대상
        {
            "ITEM_NAME": "와파린정(제네릭)",
            "MIXTURE_ITEM_NAME": "아스피린정",
            "PROHBT_CONTENT": "출혈 위험 증가로 병용을 피하십시오.",
        },
    ]
)

ELDERLY_RESPONSE = _ok(
    [
        {"ITEM_NAME": "요시케어정5밀리그램(솔리페나신숙신산염)", "PROHBT_CONTENT": "항콜린 작용으로 노인에서 주의가 필요."},
    ]
)

AGE_TABOO_RESPONSE = _ok(
    [
        {
            "ITEM_NAME": "마도파에취비에스캅셀125",
            "PROHBT_CONTENT": "25세 미만에서 안전성이 확립되지 않았습니다.",
        },
    ]
)

PREGNANCY_TABOO_RESPONSE = _ok(
    [
        {"ITEM_NAME": "씨앤유캡슐", "PROHBT_CONTENT": "임부 투여금기(금기등급 1)."},
    ]
)

EMPTY_RESPONSE = _ok([])


def test_search_usjnt_taboo_parses_and_dedupes():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(USJNT_TABOO_RESPONSE)):
        results = search_usjnt_taboo("와파린정")

    assert len(results) == 1  # 브랜드 중복 제거됨
    assert results[0].mixture_item_name == "아스피린정"
    assert results[0].prohbt_content == "출혈 위험 증가로 병용을 피하십시오."


def test_search_usjnt_taboo_no_match_returns_empty():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(EMPTY_RESPONSE)):
        assert search_usjnt_taboo("존재하지않는약") == []


def test_search_elderly_caution_maps_category():
    """[2026-07-14] API 전환 이후 노인주의(해열진통소염제) 세부 분류는 통합돼 "노인주의" 하나로만 나온다."""
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(ELDERLY_RESPONSE)):
        results = search_elderly_caution("요시케어정5밀리그램(솔리페나신숙신산염)")

    assert len(results) == 1
    assert results[0].category == "노인주의"
    assert "항콜린" in results[0].detail


def test_search_age_taboo_detail_includes_condition_text():
    """API에는 별도 extra 필드가 없어 연령 조건이 detail(자연어) 안에 포함된다."""
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(AGE_TABOO_RESPONSE)):
        results = search_age_taboo("마도파에취비에스캅셀125")

    assert len(results) == 1
    assert results[0].category == "연령금기"
    assert results[0].extra is None
    assert "25세 미만" in results[0].detail


def test_search_pregnancy_taboo_detail_includes_grade_text():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(PREGNANCY_TABOO_RESPONSE)):
        results = search_pregnancy_taboo("씨앤유캡슐")

    assert len(results) == 1
    assert results[0].category == "임부금기"
    assert results[0].extra is None
    assert "금기등급 1" in results[0].detail


def test_search_elderly_caution_no_match_returns_empty():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(EMPTY_RESPONSE)):
        assert search_elderly_caution("존재하지않는약") == []
