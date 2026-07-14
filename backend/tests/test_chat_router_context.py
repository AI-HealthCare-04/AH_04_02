"""
chat_router.py — 챗봇 컨텍스트 구성 함수 테스트 (2026-07-14 추가)

_summarize_medication_guide()에 precautions가 빠져 있던 것과, source_refs(DUR
병용금기/노인주의/연령금기/임부금기)가 챗봇 컨텍스트에 전혀 포함되지 않던 문제를
고쳤다 — "부작용 있으면 어떻게 하나요?" 같은 질문에 DUR 데이터가 실제로 반영되는지
회귀 방지용 테스트.
"""
import json

from routers.chat_router import (
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
