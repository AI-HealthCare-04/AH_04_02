"""
test_ocr_interface_bbox_merge.py — _merge_split_drug_name_fields() 단위 테스트

배경: CLOVA OCR이 "글루코파지XR"처럼 한글 브랜드명 뒤에 영문 방출제어 접미사
(SR/XR/ER/CR/MR/IR/LA/CD/SA)가 붙는 약품명을, 스크립트(문자 체계)가 바뀌는
지점에서 별개의 bounding box 2개로 쪼개 인식하는 경우가 실제로 있다. 이 함수는
raw_text로 펼치기 전, boundingPoly 좌표가 남아있는 시점에 그 두 필드를 합친다.

핵심 검증: (1) 합쳐야 하는 케이스, (2) 각 조건 중 하나라도 어긋나면 절대
합치지 않는 케이스 — 무관한 필드까지 잘못 병합되는 사고를 막는 게 이 함수의
존재 이유이므로, "안 합쳐야 할 때 안 합친다"쪽 커버리지가 더 중요하다.
"""
from __future__ import annotations

from services.ocr_interface import _merge_split_drug_name_fields


def _field(text: str, x0: float, y0: float, x1: float, y1: float, confidence: float = 0.99) -> dict:
    """CLOVA fields[] 항목 형태의 synthetic dict 생성 헬퍼."""
    return {
        "inferText": text,
        "inferConfidence": confidence,
        "boundingPoly": {
            "vertices": [
                {"x": x0, "y": y0},
                {"x": x1, "y": y0},
                {"x": x1, "y": y1},
                {"x": x0, "y": y1},
            ]
        },
    }


# ── 병합되어야 하는 케이스 ───────────────────────────────────────────────────

def test_merges_hangul_and_release_suffix_when_tight_and_same_row():
    """같은 행, 좁은 간격(글자 높이의 40% 이내), 한글+순수대문자 1~3자 → 병합."""
    fields = [
        _field("글루코파지", 100, 100, 200, 130),  # height=30
        _field("XR", 202, 100, 220, 130),  # gap=2, well within 30*0.4=12
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 1
    assert result[0]["inferText"] == "글루코파지XR"


def test_merged_confidence_takes_minimum_of_both():
    fields = [
        _field("디아미크롱", 0, 0, 100, 30, confidence=0.95),
        _field("MR", 102, 0, 120, 30, confidence=0.60),
    ]
    result = _merge_split_drug_name_fields(fields)
    assert result[0]["inferConfidence"] == 0.60


def test_preserves_unrelated_fields_around_a_merge():
    """병합 대상이 아닌 앞뒤 필드는 그대로 유지되어야 한다."""
    fields = [
        _field("고혈압약", 0, 0, 80, 30),
        _field("글루코파지", 100, 100, 200, 130),
        _field("XR", 202, 100, 220, 130),
        _field("500mg", 300, 100, 360, 130),
    ]
    result = _merge_split_drug_name_fields(fields)
    texts = [f["inferText"] for f in result]
    assert texts == ["고혈압약", "글루코파지XR", "500mg"]


# ── 병합되지 않아야 하는 케이스 ─────────────────────────────────────────────

def test_does_not_merge_when_gap_too_wide():
    """일반적인 단어 사이 공백만큼 떨어져 있으면(높이의 40% 초과) 합치지 않는다."""
    fields = [
        _field("글루코파지", 0, 0, 100, 30),  # height=30
        _field("XR", 150, 0, 170, 30),  # gap=50, exceeds 30*0.4=12
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_does_not_merge_when_different_rows():
    """y좌표가 겹치지 않는 다른 행이면 합치지 않는다."""
    fields = [
        _field("글루코파지", 0, 0, 100, 30),
        _field("XR", 102, 200, 120, 230),  # 전혀 다른 행
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_does_not_merge_second_field_not_pure_uppercase_suffix():
    """두번째 필드가 순수 대문자 1~3자가 아니면(예: 용량 숫자) 합치지 않는다 —
    약품명 옆 용량 표기까지 잘못 합쳐지는 사고를 막는 핵심 조건."""
    fields = [
        _field("글루코파지", 0, 0, 100, 30),
        _field("500mg", 102, 0, 160, 30),
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_does_not_merge_when_first_field_has_no_hangul():
    """첫 필드에 한글이 전혀 없으면(순수 영문 단어 두 개) 합치지 않는다."""
    fields = [
        _field("Cold", 0, 0, 60, 30),
        _field("XR", 62, 0, 80, 30),
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_does_not_merge_more_than_three_uppercase_letters():
    """방출제어 접미사는 보통 1~3자 — 4자 이상 순수 대문자는 다른 단어로 보고 합치지 않는다."""
    fields = [
        _field("글루코파지", 0, 0, 100, 30),
        _field("TABS", 102, 0, 140, 30),
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_does_not_merge_lowercase_suffix():
    """소문자(대소문자 구분 없이 순수 영문 소문자)는 방출제어 접미사 패턴이 아니므로 합치지 않는다."""
    fields = [
        _field("글루코파지", 0, 0, 100, 30),
        _field("xr", 102, 0, 120, 30),
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_missing_bounding_poly_skips_merge_safely():
    """boundingPoly가 없는 필드(mock 등)는 좌표를 비교할 수 없으므로 합치지 않는다."""
    fields = [
        {"inferText": "글루코파지", "inferConfidence": 0.9},
        {"inferText": "XR", "inferConfidence": 0.9},
    ]
    result = _merge_split_drug_name_fields(fields)
    assert len(result) == 2


def test_empty_or_single_field_list_returned_unchanged():
    assert _merge_split_drug_name_fields([]) == []
    single = [_field("암로디핀정5mg", 0, 0, 100, 30)]
    assert _merge_split_drug_name_fields(single) == single
