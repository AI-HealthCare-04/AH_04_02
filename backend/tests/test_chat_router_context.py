"""
chat_router.py — 챗봇 컨텍스트 구성 함수 테스트 (2026-07-14 추가)

_summarize_medication_guide()에 precautions가 빠져 있던 것과, source_refs(DUR
병용금기/노인주의/연령금기/임부금기)가 챗봇 컨텍스트에 전혀 포함되지 않던 문제를
고쳤다 — "부작용 있으면 어떻게 하나요?" 같은 질문에 DUR 데이터가 실제로 반영되는지
회귀 방지용 테스트.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from routers.chat_router import (
    _build_on_demand_dur_context,
    _dur_lookup_modes,
    _extract_dur_candidate_drug_names,
    _is_lifestyle_question,
    _menu_map_text,
    _retrieve_chat_rag_docs,
    _service_info_text,
    _should_answer_from_dur_only,
    _summarize_lifestyle_guide,
    _summarize_medication_guide,
    _summarize_source_refs,
)


def test_summarize_medication_guide_includes_precautions():
    medication_guide_json = json.dumps(
        {
            "drugs": [
                {
                    "drug_name": "아스피린정",
                    "medication_guide": "출혈 위험이 있는 약입니다.",
                    "precautions": ["출혈 경향이 있으면 복용을 피하세요.", "수술 전에는 의사에게 알리세요."],
                }
            ]
        }
    )
    lines = _summarize_medication_guide(medication_guide_json)

    assert any("복약 안내" in line and "출혈 위험" in line for line in lines)
    assert any("주의사항" in line and "수술 전" in line for line in lines)


def test_summarize_medication_guide_stub_shape_without_precautions():
    """스텁 모양(precautions 없음)도 에러 없이 처리한다."""
    medication_guide_json = json.dumps({"drugs": [{"drug_name": "테스트약", "caution": "테스트 주의사항"}]})
    lines = _summarize_medication_guide(medication_guide_json)

    assert any("테스트 주의사항" in line for line in lines)


def test_summarize_source_refs_includes_dur_taboo_warning():
    source_refs_json = json.dumps(
        [
            {"drug_name": "아스피린정", "item_name": "아스피린정", "field": "효능·효과"},  # 의약품 인용 — 무시
            {"drug_name": "와파린정", "mixture_item_name": "아스피린정", "prohbt_content": "출혈 위험 증가"},
        ]
    )
    lines = _summarize_source_refs(source_refs_json)

    assert len(lines) == 1
    assert "DUR 병용금기" in lines[0]
    assert "아스피린정" in lines[0]
    assert "출혈 위험 증가" in lines[0]


def test_summarize_source_refs_includes_dur_caution():
    source_refs_json = json.dumps(
        [
            {
                "drug_name": "아스피린정",
                "dur_category": "임부금기",
                "dur_detail": "임신 3기 태아 위험",
                "dur_extra": None,
            }
        ]
    )
    lines = _summarize_source_refs(source_refs_json)

    assert len(lines) == 1
    assert "DUR 임부금기" in lines[0]
    assert "임신 3기 태아 위험" in lines[0]


def test_summarize_source_refs_ignores_non_dur_refs():
    """의약품/생활지침 인용은 medication_guide/lifestyle_guide 텍스트에 이미 있으므로 중복 추가하지 않는다."""
    source_refs_json = json.dumps(
        [
            {"drug_name": "아스피린정", "item_name": "아스피린정", "field": "효능·효과"},
            {"drug_name": "아스피린정", "disease": "고혈압", "category": "식이요법", "source": "질병관리청"},
        ]
    )
    assert _summarize_source_refs(source_refs_json) == []


def test_summarize_source_refs_empty_or_invalid_json_returns_empty():
    assert _summarize_source_refs("[]") == []
    assert _summarize_source_refs("not json") == []


def test_summarize_lifestyle_guide_reads_structured_categories():
    """[2026-07-23 수정] guides[]는 이제 진단명별 diet/exercise/other × recommended/avoid
    구조다 — 각 카테고리 항목이 요약에 포함되는지 확인."""
    lifestyle_guide_json = json.dumps(
        {
            "guides": [
                {
                    "diagnosis": "고혈압",
                    "diet": {"recommended": ["싱겁게 먹기"], "avoid": ["짠 음식"]},
                    "exercise": {"recommended": ["규칙적으로 운동하세요."], "avoid": []},
                    "other": {"recommended": [], "avoid": []},
                }
            ]
        }
    )
    lines = _summarize_lifestyle_guide(lifestyle_guide_json)
    assert any("규칙적으로 운동" in line for line in lines)
    assert any("짠 음식" in line for line in lines)


def test_summarize_lifestyle_guide_handles_legacy_free_text_guide():
    """v1.1 이하로 이미 저장된 처방전 기록(guides[].guide: 자유 텍스트)도 죽지 않고 요약한다."""
    lifestyle_guide_json = json.dumps(
        {"guides": [{"diagnosis": "고혈압", "guide": "규칙적으로 운동하세요."}]}
    )
    lines = _summarize_lifestyle_guide(lifestyle_guide_json)
    assert any("규칙적으로 운동" in line for line in lines)


def test_summarize_lifestyle_guide_handles_legacy_string_list():
    """더 옛 캐시(문자열 배열 모양)가 아직 남아있어도 죽지 않고 그대로 사용한다."""
    lifestyle_guide_json = json.dumps({"guides": ["옛날 모양 문자열"]})
    lines = _summarize_lifestyle_guide(lifestyle_guide_json)
    assert any("옛날 모양 문자열" in line for line in lines)


def test_dur_question_does_not_use_general_kdca_rag_context():
    """병용금기/임부주의 같은 의약품 안전 질문은 질병관리청 건강정보로 보강하지 않는다."""
    assert _should_answer_from_dur_only("이 약 임부금기야?")
    assert _should_answer_from_dur_only("혈압약이랑 같이 먹어도 돼?")
    assert _should_answer_from_dur_only("와파린이랑 타이레놀 같이 복용해도 되나요?")
    assert _should_answer_from_dur_only("아스피린과 와파린을 함께 복용해도 괜찮나요?")
    assert _should_answer_from_dur_only("노바스크정5밀리그람과 타이레놀 병용 가능해?")
    assert _should_answer_from_dur_only("이 약 드셔도 되나요?")
    with patch("rag.vectorstore.similarity_search") as mock_search:
        assert _retrieve_chat_rag_docs("노바스크정5밀리그람과 타이레놀 병용 가능해?") == []

    mock_search.assert_not_called()


def test_extract_dur_candidate_includes_unregistered_drug_mentioned_in_question():
    names = _extract_dur_candidate_drug_names("처방전 약이랑 타이레놀 같이 먹어도 돼?", ["암로디핀정"])

    assert "타이레놀" in names


def test_extract_dur_candidate_handles_ingredient_name_without_hardcoded_alias():
    names = _extract_dur_candidate_drug_names("심바스타틴이랑 먹으면 안되는 의약품 정보 알려줘", [])

    assert "심바스타틴" in names


def test_dur_lookup_modes_avoid_unneeded_caution_apis_for_taboo_question():
    needs_taboo, needs_cautions = _dur_lookup_modes("노바스크정5밀리그람과 타이레놀 병용 가능해?")

    assert needs_taboo is True
    assert needs_cautions is False


def test_dur_lookup_modes_avoid_unneeded_taboo_api_for_pregnancy_question():
    needs_taboo, needs_cautions = _dur_lookup_modes("타이레놀 임부금기 있어?")

    assert needs_taboo is False
    assert needs_cautions is True


def test_on_demand_dur_context_queries_drug_mentioned_in_question():
    with (
        patch("rag.mfds_client.search_by_name", return_value=[]),
        patch("rag.mfds_client.search_permit_info", return_value=[]),
        patch.dict(
            _build_on_demand_dur_context.__globals__,
            {"_search_dur_taboo": lambda _name: [], "_search_dur_cautions": lambda _name: []},
        ),
    ):
        lines, refs = _build_on_demand_dur_context("타이레놀 임부금기 있어?", [])

    assert lines
    assert "타이레놀" in lines[0]
    assert "안전 판단으로 확정하지 마세요" in lines[0]
    assert refs == []  # 아무것도 못 찾았으니 프론트에 실어줄 인용도 없음


def test_on_demand_dur_context_skips_caution_lookup_for_taboo_question():
    taboo = SimpleNamespace(mixture_item_name="타이레놀정500밀리그람", prohbt_content="상호작용 주의")

    with (
        patch("rag.mfds_client.search_by_name", return_value=[]),
        patch("rag.mfds_client.search_permit_info", return_value=[]),
        patch.dict(
            _build_on_demand_dur_context.__globals__,
            {
                "_search_dur_taboo": lambda _name: [taboo],
                "_search_dur_cautions": lambda _name: (_ for _ in ()).throw(AssertionError("unexpected caution lookup")),
            },
        ),
    ):
        lines, refs = _build_on_demand_dur_context("노바스크정5밀리그람과 타이레놀 병용 가능해?", [])

    assert any("타이레놀" in line and "병용금기" in line for line in lines)
    assert refs == [{"mixture_item_name": "타이레놀정500밀리그람", "prohbt_content": "상호작용 주의"}]


def test_on_demand_dur_context_resolves_drug_name_then_returns_taboo_list():
    taboo = SimpleNamespace(mixture_item_name="이트라코나졸캡슐", prohbt_content="심바스타틴 혈중농도 증가")
    permit = SimpleNamespace(item_name="심바스타틴정20밀리그램", ingr_name="심바스타틴")

    with (
        patch("rag.mfds_client.search_by_name", return_value=[]),
        patch("rag.mfds_client.search_permit_info", return_value=[permit]),
        patch.dict(
            _build_on_demand_dur_context.__globals__,
            {"_search_dur_taboo": lambda _name: [taboo], "_search_dur_cautions": lambda _name: []},
        ),
    ):
        lines, refs = _build_on_demand_dur_context("심바스타틴이랑 먹으면 안되는 의약품 정보 알려줘", [])

    assert any("이트라코나졸" in line and "병용금기" in line for line in lines), lines
    assert any(ref.get("mixture_item_name") == "이트라코나졸캡슐" for ref in refs), refs


def test_is_lifestyle_question_detects_food_exercise_keywords():
    assert _is_lifestyle_question("고혈압에 좋은 음식이 뭐야?")
    assert _is_lifestyle_question("운동은 얼마나 해야 돼?")
    assert _is_lifestyle_question("생활습관 어떻게 관리해야 해?")
    assert not _is_lifestyle_question("이 약 부작용이 뭐야?")


def test_retrieve_chat_rag_docs_prefers_kdca_for_lifestyle_question():
    """[2026-07-21] 생활습관(음식/운동) 질문은 질병관리청 건강정보(doc_type=kdca_health_info)를
    최우선으로 조회한다."""
    kdca_doc = SimpleNamespace(
        page_content="채소와 저염식 위주로 드세요.",
        metadata={"title": "고혈압", "source": "질병관리청 국가건강정보포털", "doc_type": "kdca_health_info"},
    )
    with patch("rag.vectorstore.similarity_search", return_value=[kdca_doc]) as mock_search:
        docs = _retrieve_chat_rag_docs("고혈압에 좋은 음식이 뭐야?")

    mock_search.assert_called_once()
    assert mock_search.call_args.kwargs["filter"] == {"doc_type": "kdca_health_info"}
    assert docs == [kdca_doc]


def test_retrieve_chat_rag_docs_falls_back_when_kdca_has_no_match():
    """질병관리청 필터로 못 찾으면 필터 없는 전체 검색으로 폴백한다."""
    fallback_doc = SimpleNamespace(
        page_content="일부 참고 자료",
        metadata={"title": "일부 참고 자료", "source": "기타"},
    )
    with patch("rag.vectorstore.similarity_search", side_effect=[[], [fallback_doc]]) as mock_search:
        docs = _retrieve_chat_rag_docs("운동은 얼마나 해야 돼?")

    assert mock_search.call_count == 2
    assert mock_search.call_args_list[0].kwargs["filter"] == {"doc_type": "kdca_health_info"}
    assert "filter" not in mock_search.call_args_list[1].kwargs
    assert docs == [fallback_doc]


def test_retrieve_chat_rag_docs_prefers_drug_docs_for_non_lifestyle_question():
    """의약품 관련(생활습관 키워드 없는) 질문은 doc_type=drug 문서를 최우선으로 조회한다."""
    drug_doc = SimpleNamespace(
        page_content="고혈압에 사용합니다.",
        metadata={"item_name": "암로디핀정5mg", "field_label": "효능·효과"},
    )
    with patch("rag.vectorstore.similarity_search", return_value=[drug_doc]) as mock_search:
        docs = _retrieve_chat_rag_docs("이 약 효능이 뭐야?")

    mock_search.assert_called_once()
    assert mock_search.call_args.kwargs["filter"] == {"doc_type": "drug"}
    assert docs == [drug_doc]


def test_retrieve_chat_rag_docs_uses_exact_drug_name_before_similarity_search():
    """질문에 약명이 명시되면 ChromaDB 유사도 검색보다 item_name 직접 조회를 먼저 사용한다."""
    novasc_doc = SimpleNamespace(
        page_content="혈압을 낮추는 데 사용합니다.",
        metadata={"item_name": "노바스크정5밀리그람", "field_label": "효능·효과", "doc_type": "drug"},
    )
    with (
        patch("rag.vectorstore.search_by_item_name", return_value=[novasc_doc]) as mock_exact,
        patch("rag.vectorstore.similarity_search") as mock_similarity,
    ):
        docs = _retrieve_chat_rag_docs("노바스크정5밀리그람 효능 알려줘")

    mock_exact.assert_called()
    mock_similarity.assert_not_called()
    assert docs == [novasc_doc]


def test_retrieve_chat_rag_docs_drops_unmatched_drug_sources():
    """약명이 명시된 질문에서 다른 약 문서가 검색되면 참고자료로 노출하지 않는다."""
    tylenol_doc = SimpleNamespace(
        page_content="해열진통제입니다.",
        metadata={"item_name": "타이레놀정500밀리그람", "field_label": "효능·효과", "doc_type": "drug"},
    )
    with (
        patch("rag.vectorstore.search_by_item_name", return_value=[]),
        patch("rag.vectorstore.similarity_search", return_value=[tylenol_doc]) as mock_search,
    ):
        docs = _retrieve_chat_rag_docs("노바스크정5밀리그람 효능 알려줘")

    assert mock_search.call_count == 2
    assert docs == []


def test_on_demand_dur_context_creates_langfuse_retriever_span():
    """[2026-07-21] DUR 전용 질문은 ChromaDB를 건너뛰어(_retrieve_chat_rag_docs가 []을
    반환) Langfuse에 retriever 스팬이 하나도 안 남았다 — 실제 DUR 조회 자체를 스팬으로 남긴다."""
    with (
        patch("rag.mfds_client.search_by_name", return_value=[]),
        patch("rag.mfds_client.search_permit_info", return_value=[]),
        patch.dict(
            _build_on_demand_dur_context.__globals__,
            {"_search_dur_taboo": lambda _name: [], "_search_dur_cautions": lambda _name: []},
        ),
        patch("routers.chat_router.optional_observation") as mock_observation,
    ):
        _build_on_demand_dur_context("타이레놀 임부금기 있어?", [])  # 반환값(lines, refs) 자체는 이 테스트 관심사 아님

    assert any(
        call.kwargs.get("name") == "retrieve-dur-lookup" and call.kwargs.get("as_type") == "retriever"
        for call in mock_observation.call_args_list
    )


def test_service_info_contains_app_description_for_chatbot():
    text = _service_info_text()

    assert "복약 안내" in text
    assert "생활습관 가이드" in text
    assert "담당 의사나 약사" in text


def test_menu_map_text_points_to_top_menu_not_bottom_menu():
    text = _menu_map_text()

    assert "상단" in text
    assert "하단" not in text
