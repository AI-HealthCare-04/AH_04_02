"""
ocr_router.py — GET /ocr/drug-info 주의사항/부작용/상호작용/보관법 보강 조회 테스트
(2026-07-20 신규, 담당: 김영혜)

DrugDetail.tsx(복약 일정 기반, OCR 기록과 연결 안 됨)가 "주의사항 등은 준비 중"이라는
고정 문구만 보여주던 문제 — rag/ 패키지의 e약은요/DUR live API를 온디맨드로 보강
조회하도록 고쳤다. 이 API는 인증/DB 의존성이 없는 stateless 조회라 세션 픽스처 없이
TestClient만으로 검증한다. 특히 "완전 실패" 케이스가 회귀 방지의 핵심 — 정부 API가
어떤 이유로든 실패해도 이 엔드포인트가 500이 되면 안 된다.
"""
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _drug_info_hit(**overrides):
    base = {
        "item_name": "테스트약정10mg",
        "atpn_qesitm": "이 약을 복용하는 동안 술을 마시지 마세요.",
        "atpn_warn_qesitm": "심한 간 손상 병력이 있는 환자는 복용하지 마세요.",
        "se_qesitm": "어지러움, 두통이 나타날 수 있습니다.",
        "intrc_qesitm": "다른 진통제와 함께 복용 시 상호작용이 있을 수 있습니다.",
        "deposit_method_qesitm": "실온보관, 습기를 피하세요.",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _dur_caution(category: str, detail: str | None = None, extra: str | None = None):
    return SimpleNamespace(category=category, detail=detail, extra=extra)


class TestDrugInfoSuccess:
    def test_all_fields_populated_with_warning_prefix(self):
        with (
            patch("rag.mfds_client.search_by_name", return_value=[_drug_info_hit()]),
            patch("rag.dur_master.search_elderly_caution", return_value=[_dur_caution("노인주의", "낙상 위험 증가")]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        assert r.status_code == 200
        data = r.json()
        assert data["precautions"].startswith("[경고] 심한 간 손상 병력이 있는 환자는 복용하지 마세요.")
        assert "술을 마시지 마세요" in data["precautions"]
        assert data["side_effects"] == "어지러움, 두통이 나타날 수 있습니다."
        assert data["interactions"] == "다른 진통제와 함께 복용 시 상호작용이 있을 수 있습니다."
        assert data["storage"] == "실온보관, 습기를 피하세요."
        assert data["dur_cautions"] == [{"category": "노인주의", "detail": "낙상 위험 증가", "extra": None}]

    def test_partial_data_emed_hit_but_no_dur_cautions(self):
        with (
            patch("rag.mfds_client.search_by_name", return_value=[_drug_info_hit(atpn_warn_qesitm=None)]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        data = r.json()
        assert data["precautions"] == "이 약을 복용하는 동안 술을 마시지 마세요."
        assert data["dur_cautions"] == []


class TestDrugInfoDegradedGracefully:
    def test_all_external_calls_failing_still_returns_200(self):
        with (
            patch("rag.mfds_client.search_by_name", side_effect=Exception("network down")),
            patch("rag.dur_master.search_elderly_caution", side_effect=Exception("network down")),
            patch("rag.dur_master.search_age_taboo", side_effect=Exception("network down")),
            patch("rag.dur_master.search_pregnancy_taboo", side_effect=Exception("network down")),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "암로디핀정5mg"})

        assert r.status_code == 200
        data = r.json()
        assert data["precautions"] is None
        assert data["side_effects"] is None
        assert data["interactions"] is None
        assert data["storage"] is None
        assert data["dur_cautions"] == []
        # 정적 매칭(drug_class/indication)은 rag 조회 실패와 무관하게 그대로 동작해야 함
        assert "drug_class" in data

    def test_unregistered_drug_name_no_hits_returns_empty_gracefully(self):
        with (
            patch("rag.mfds_client.search_by_name", return_value=[]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "존재하지않는약이름"})

        assert r.status_code == 200
        data = r.json()
        assert data["precautions"] is None
        assert data["dur_cautions"] == []


class TestDrugInfoLookupNameSelection:
    def test_non_emed_match_source_uses_raw_drug_name_for_rag_lookup(self):
        """HIRA 코드 매칭 등 emed가 아닌 경로에서 matched_item이 검색 불가능한 값
        (예: "코드:123")이어도 rag 조회는 원본 drug_name으로 나가야 한다."""
        with (
            patch(
                "routers.ocr_router.get_drug_info",
                return_value={
                    "drug_name": "케이캡정50mg",
                    "drug_class": "위산분비억제제",
                    "efficacy": "",
                    "match_source": "hira_name",
                    "matched_item": "케이캡정50mg",
                    "atc_code": "A02BC",
                },
            ),
            patch("rag.mfds_client.search_by_name", return_value=[]) as mock_search,
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "케이캡정50mg"})

        assert r.status_code == 200
        mock_search.assert_called_once_with("케이캡정50mg", num_of_rows=1)
