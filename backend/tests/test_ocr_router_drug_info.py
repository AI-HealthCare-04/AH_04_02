"""
ocr_router.py — GET /ocr/drug-info 주의사항/부작용/상호작용/보관법 보강 조회 테스트
(2026-07-20 신규, 담당: 김영혜)

DrugDetail.tsx(복약 일정 기반, OCR 기록과 연결 안 됨)가 "주의사항 등은 준비 중"이라는
고정 문구만 보여주던 문제 — rag/ 패키지의 e약은요/DUR/허가정보 상세 live API를
온디맨드로 보강 조회하도록 고쳤다. 이 API는 인증/DB 의존성이 없는 stateless 조회라
세션 픽스처 없이 TestClient만으로 검증한다. 특히 "완전 실패" 케이스가 회귀 방지의
핵심 — 정부 API가 어떤 이유로든 실패해도 이 엔드포인트가 500이 되면 안 된다.

[2026-07-20 추가] "사용상의 주의사항"이라는 정확한 명칭의 필드는 e약은요(atpn_qesitm)가
아니라 허가정보 상세(search_permit_detail의 nb_doc_data, XML)에 있다는 걸 뒤늦게
반영했다 — 모든 테스트가 이 호출도 함께 mock해야 한다(안 그러면 실제 rag/.env에 키가
있는 로컬 환경에서 진짜 네트워크 호출이 나간다).
"""
import json
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


def _permit_detail_hit(nb_doc_data: str | None):
    return SimpleNamespace(item_name="테스트약정10mg", nb_doc_data=nb_doc_data)


_SAMPLE_NB_DOC_XML = (
    '<DOC><SECTION><ARTICLE title="1. 경고">'
    "<PARAGRAPH>이 약을 장기 복용하지 마십시오.</PARAGRAPH>"
    "</ARTICLE></SECTION></DOC>"
)


def _dur_caution(category: str, detail: str | None = None, extra: str | None = None):
    return SimpleNamespace(category=category, detail=detail, extra=extra)


class TestDrugInfoSuccess:
    def test_all_fields_populated_with_permit_and_emed_precautions_merged(self):
        with (
            patch("rag.mfds_client.search_permit_detail", return_value=[_permit_detail_hit(_SAMPLE_NB_DOC_XML)]),
            patch("rag.mfds_client.search_by_name", return_value=[_drug_info_hit()]),
            patch("rag.dur_master.search_elderly_caution", return_value=[_dur_caution("노인주의", "낙상 위험 증가")]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        assert r.status_code == 200
        data = r.json()
        # 허가정보 상세(사용상의 주의사항)가 e약은요 필드보다 먼저 나와야 함
        assert "[사용상의 주의사항 - 1. 경고] 이 약을 장기 복용하지 마십시오." in data["precautions"]
        assert data["precautions"].startswith("[사용상의 주의사항")
        assert "[경고] 심한 간 손상 병력이 있는 환자는 복용하지 마세요." in data["precautions"]
        assert "술을 마시지 마세요" in data["precautions"]
        assert data["side_effects"] == "어지러움, 두통이 나타날 수 있습니다."
        assert data["interactions"] == "다른 진통제와 함께 복용 시 상호작용이 있을 수 있습니다."
        assert data["storage"] == "실온보관, 습기를 피하세요."
        assert data["dur_cautions"] == [{"category": "노인주의", "detail": "낙상 위험 증가", "extra": None}]

    def test_partial_data_emed_hit_but_no_permit_detail_or_dur_cautions(self):
        with (
            patch("rag.mfds_client.search_permit_detail", return_value=[]),
            patch("rag.mfds_client.search_by_name", return_value=[_drug_info_hit(atpn_warn_qesitm=None)]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        data = r.json()
        assert data["precautions"] == "이 약을 복용하는 동안 술을 마시지 마세요."
        assert data["dur_cautions"] == []

    def test_permit_detail_with_no_nb_doc_data_falls_back_to_emed_only(self):
        """허가정보는 매칭됐지만 사용상의주의사항(nb_doc_data) 자체가 빈 품목도 있다."""
        with (
            patch("rag.mfds_client.search_permit_detail", return_value=[_permit_detail_hit(None)]),
            patch("rag.mfds_client.search_by_name", return_value=[_drug_info_hit(atpn_warn_qesitm=None)]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        data = r.json()
        assert data["precautions"] == "이 약을 복용하는 동안 술을 마시지 마세요."


class TestDrugInfoDegradedGracefully:
    def test_all_external_calls_failing_still_returns_200(self):
        with (
            patch("rag.mfds_client.search_permit_detail", side_effect=Exception("network down")),
            patch("rag.mfds_client.search_by_name", side_effect=Exception("network down")),
            patch("rag.dur_master.search_elderly_caution", side_effect=Exception("network down")),
            patch("rag.dur_master.search_age_taboo", side_effect=Exception("network down")),
            patch("rag.dur_master.search_pregnancy_taboo", side_effect=Exception("network down")),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
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
            patch("rag.mfds_client.search_permit_detail", return_value=[]),
            patch("rag.mfds_client.search_by_name", return_value=[]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "존재하지않는약이름"})

        assert r.status_code == 200
        data = r.json()
        assert data["precautions"] is None
        assert data["dur_cautions"] == []


class TestDrugInfoMatchedNameValidation:
    """[2026-07-20, PR #52 기준 정렬] matched_name은 get_drug_info()의 matched_item이
    아니라 match_drug()의 유사도 점수로 판정한다 — "졸피뎀아무말"처럼 실제 이름 뒤에
    엉뚱한 말을 붙인 입력을 get_drug_info()의 atc_pattern/fallback(키워드 부분일치)은
    통과시키지만 match_drug()의 전체 문자열 유사도는 걸러낸다는 게 PR #52의 요지 —
    그 기준을 그대로 재사용한다."""

    def test_high_similarity_score_confirms_drug_name_itself(self):
        with (
            patch("routers.ocr_router.match_drug", return_value=("무관한매칭명", 0.95)),
            patch("rag.mfds_client.search_permit_detail", return_value=[]),
            patch("rag.mfds_client.search_by_name", return_value=[]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "암로디핀정5mg"})

        # matched_name은 match_drug()이 찾아준 다른 이름이 아니라 검증된 원본 drug_name 그대로다.
        assert r.json()["matched_name"] == "암로디핀정5mg"

    def test_low_similarity_score_below_threshold_returns_null(self):
        """"졸피뎀아무말"처럼 일부만 맞는 입력 — 키워드 부분일치라면 통과했겠지만
        전체 유사도 기준으로는 걸러져야 한다."""
        with (
            patch("routers.ocr_router.match_drug", return_value=("졸피뎀정10mg", 0.4)),
            patch("rag.mfds_client.search_permit_detail", return_value=[]),
            patch("rag.mfds_client.search_by_name", return_value=[]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "졸피뎀아무말"})

        assert r.json()["matched_name"] is None

    def test_rag_lookup_always_uses_raw_drug_name_regardless_of_match_result(self):
        """matched_name이 항상 drug_name 자체이거나 None이라, "더 정확한 이름으로 바꿔서
        조회"할 대상이 없다 — rag/DUR 조회는 검증 결과와 무관하게 원본으로 그대로 나간다."""
        with (
            patch("routers.ocr_router.match_drug", return_value=("전혀다른약", 0.1)),
            patch("rag.mfds_client.search_permit_detail", return_value=[]) as mock_permit,
            patch("rag.mfds_client.search_by_name", return_value=[]) as mock_search,
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "케이캡정50mg"})

        assert r.status_code == 200
        # [2026-07-20] resolve_drug_name_candidates()가 원문 다음으로 용량표기 제거명도
        # 시도하므로 이제 호출이 1회로 고정되지 않는다 — 원문 그대로 조회했는지(다른 이름으로
        # "바꿔치기"되지 않았는지)만 확인한다.
        mock_search.assert_any_call("케이캡정50mg", num_of_rows=1)
        mock_permit.assert_any_call("케이캡정50mg", num_of_rows=1)


class TestDrugInfoPatientSummaryField:
    """/ocr/drug-info 응답에 patient_summary가 정상적으로 포함/누락되는지 — LLM 자체
    로직(_summarize_precautions_for_patient)의 세부 동작은 아래 별도 클래스에서 검증."""

    def test_patient_summary_included_when_helper_succeeds(self):
        fake_summary = {"must_check": ["a"], "tell_doctor": ["b"], "avoid_together": []}
        with (
            patch("rag.mfds_client.search_permit_detail", return_value=[]),
            patch("rag.mfds_client.search_by_name", return_value=[_drug_info_hit()]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=fake_summary),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        assert r.json()["patient_summary"] == fake_summary

    def test_patient_summary_null_when_helper_returns_none(self):
        with (
            patch("rag.mfds_client.search_permit_detail", return_value=[]),
            patch("rag.mfds_client.search_by_name", return_value=[]),
            patch("rag.dur_master.search_elderly_caution", return_value=[]),
            patch("rag.dur_master.search_age_taboo", return_value=[]),
            patch("rag.dur_master.search_pregnancy_taboo", return_value=[]),
            patch("routers.ocr_router._summarize_precautions_for_patient", return_value=None),
        ):
            r = client.get("/ocr/drug-info", params={"drug_name": "테스트약"})

        assert r.json()["patient_summary"] is None


class TestSummarizePrecautionsForPatient:
    """_summarize_precautions_for_patient() 자체 — ChatOpenAI를 mock해서 실제 네트워크
    호출 없이 검증한다(이 worktree엔 rag/.env에 실제 OPENAI_API_KEY가 들어있어서, mock
    안 하면 진짜 LLM 호출이 나간다)."""

    def test_no_raw_text_at_all_skips_llm_call_entirely(self):
        from routers.ocr_router import _summarize_precautions_for_patient

        with patch("langchain_openai.ChatOpenAI") as mock_chat_cls:
            result = _summarize_precautions_for_patient("테스트약", None, None, None)

        assert result is None
        mock_chat_cls.assert_not_called()

    def test_no_openai_api_key_returns_none_without_calling_llm(self):
        from routers.ocr_router import _summarize_precautions_for_patient

        with (
            patch("rag.config.settings.OPENAI_API_KEY", None),
            patch("langchain_openai.ChatOpenAI") as mock_chat_cls,
        ):
            result = _summarize_precautions_for_patient("테스트약", "주의하세요", None, None)

        assert result is None
        mock_chat_cls.assert_not_called()

    def test_valid_json_response_parsed_and_truncated_to_four_each(self):
        from routers.ocr_router import _summarize_precautions_for_patient

        fake_response = SimpleNamespace(
            content=json.dumps(
                {
                    "must_check": ["a", "b", "c", "d", "e"],  # 5개 — 4개로 잘려야 함
                    "tell_doctor": ["간질환이 있으면 알려주세요"],
                    "avoid_together": [],
                },
                ensure_ascii=False,
            )
        )
        mock_chat_instance = SimpleNamespace(invoke=lambda *_a, **_kw: fake_response)
        with (
            patch("rag.config.settings.OPENAI_API_KEY", "fake-key"),
            patch("langchain_openai.ChatOpenAI", return_value=mock_chat_instance),
        ):
            result = _summarize_precautions_for_patient("테스트약", "주의사항 원문", "부작용 원문", None)

        assert result == {
            "must_check": ["a", "b", "c", "d"],
            "tell_doctor": ["간질환이 있으면 알려주세요"],
            "avoid_together": [],
        }

    def test_malformed_json_response_returns_none(self):
        from routers.ocr_router import _summarize_precautions_for_patient

        fake_response = SimpleNamespace(content="이건 JSON이 아닙니다")
        mock_chat_instance = SimpleNamespace(invoke=lambda *_a, **_kw: fake_response)
        with (
            patch("rag.config.settings.OPENAI_API_KEY", "fake-key"),
            patch("langchain_openai.ChatOpenAI", return_value=mock_chat_instance),
        ):
            result = _summarize_precautions_for_patient("테스트약", "주의사항 원문", None, None)

        assert result is None

    def test_llm_call_raising_exception_returns_none(self):
        from routers.ocr_router import _summarize_precautions_for_patient

        def _raise(*_a, **_kw):
            raise RuntimeError("openai down")

        mock_chat_instance = SimpleNamespace(invoke=_raise)
        with (
            patch("rag.config.settings.OPENAI_API_KEY", "fake-key"),
            patch("langchain_openai.ChatOpenAI", return_value=mock_chat_instance),
        ):
            result = _summarize_precautions_for_patient("테스트약", "주의사항 원문", None, None)

        assert result is None
