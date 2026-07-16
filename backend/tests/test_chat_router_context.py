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
    _extract_dur_candidate_drug_names,
    _menu_map_text,
    _retrieve_chat_rag_context,
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


def test_summarize_lifestyle_guide_still_works_unaffected():
    """회귀 확인 — 이번 수정이 기존 생활습관 가이드 요약에 영향을 주지 않았는지."""
    lifestyle_guide_json = json.dumps({"guides": ["규칙적으로 운동하세요."]})
    lines = _summarize_lifestyle_guide(lifestyle_guide_json)
    assert any("규칙적으로 운동" in line for line in lines)


def test_dur_question_does_not_use_general_kdca_rag_context():
    """병용금기/임부주의 같은 의약품 안전 질문은 질병관리청 건강정보로 보강하지 않는다."""
    assert _should_answer_from_dur_only("이 약 임부금기야?")
    assert _should_answer_from_dur_only("혈압약이랑 같이 먹어도 돼?")
    assert _should_answer_from_dur_only("와파린이랑 타이레놀 같이 복용해도 되나요?")
    assert _should_answer_from_dur_only("아스피린과 와파린을 함께 복용해도 괜찮나요?")
    assert _should_answer_from_dur_only("이 약 드셔도 되나요?")
    assert _retrieve_chat_rag_context("이 약 임부금기야?", "[DUR 임부금기] 테스트약: 임신 3기 주의") == []


def test_extract_dur_candidate_includes_unregistered_drug_mentioned_in_question():
    names = _extract_dur_candidate_drug_names("처방전 약이랑 타이레놀 같이 먹어도 돼?", ["암로디핀정"])

    assert "타이레놀" in names


def test_extract_dur_candidate_handles_ingredient_name_without_hardcoded_alias():
    names = _extract_dur_candidate_drug_names("심바스타틴이랑 먹으면 안되는 의약품 정보 알려줘", [])

    assert "심바스타틴" in names


def test_on_demand_dur_context_queries_drug_mentioned_in_question():
    with (
        patch("rag.mfds_client.search_by_name", return_value=[]),
        patch("rag.mfds_client.search_permit_info", return_value=[]),
        patch.dict(
            _build_on_demand_dur_context.__globals__,
            {"_search_dur_taboo": lambda _name: [], "_search_dur_cautions": lambda _name: []},
        ),
    ):
        lines = _build_on_demand_dur_context("타이레놀 임부금기 있어?", [])

    assert lines
    assert "타이레놀" in lines[0]
    assert "안전 판단으로 확정하지 마세요" in lines[0]


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
        lines = _build_on_demand_dur_context("심바스타틴이랑 먹으면 안되는 의약품 정보 알려줘", [])

    assert any("이트라코나졸" in line and "병용금기" in line for line in lines), lines


def test_service_info_contains_app_description_for_chatbot():
    text = _service_info_text()

    assert "복약 안내" in text
    assert "생활습관 가이드" in text
    assert "담당 의사나 약사" in text


def test_menu_map_text_points_to_top_menu_not_bottom_menu():
    text = _menu_map_text()

    assert "상단" in text
    assert "하단" not in text
