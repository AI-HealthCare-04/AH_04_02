"""
test_drug_reference.py — get_drug_name_list()이 성분명 하드코딩 사전을 후보로
안 섞는지 검증 (2026-07-20, REQ-037 관련 버그 수정)

_HARDCODED_FALLBACK(services/drug_reference.py)은 get_drug_class()의 "약효분류
부분일치" 판정 전용 사전이라 키가 "메트포르민"처럼 성분명일 뿐 실제 완전한 제품명이
아니다. get_drug_name_list()가 이 키들도 매칭 후보(drug_matcher.py)로 함께 섞었던
탓에, OCR이 "메트포르민정500mg"을 읽어도 이 성분명과 유사도 0.9 이상으로 매칭돼
(needs_review=False) OcrResult.display_name이 원문(전체 제품명)보다 정보가 적은
성분명을 오히려 우선 표시했다.
"""
from unittest.mock import patch

import services.drug_reference as drug_reference
from services.drug_reference import _HARDCODED_FALLBACK, get_drug_name_list


def test_get_drug_name_list_excludes_hardcoded_fallback_keys():
    """HIRA/e약은요 데이터가 전혀 없어도(하드코딩만 남는 상황) 결과가 비어야 한다 —
    _HARDCODED_FALLBACK 키(성분명)가 더 이상 매칭 후보로 섞이지 않는지 확인."""
    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", None),
        patch("services.drug_reference._load_drug_table", return_value=[]),
    ):
        names = get_drug_name_list()

    assert names == []
    for ingredient_name in _HARDCODED_FALLBACK:
        assert ingredient_name not in names


def test_metformin_ocr_text_does_not_match_bare_ingredient_name():
    """[재현] "메트포르민정500mg"이 성분명 "메트포르민"과 오매칭돼 needs_review=False로
    확정되던 문제 — 하드코딩 사전만 남은 상황에서는 매칭 후보 자체가 없어 낮은 점수로
    떨어지고(needs_review=True), 원문이 그대로 표시 대상으로 유지돼야 한다."""
    from services.drug_matcher import MATCH_THRESHOLD, match_drug

    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", None),
        patch("services.drug_reference._load_drug_table", return_value=[]),
        patch("services.drug_matcher._cached_names", None),
        patch("services.drug_matcher._cached_norm_names", None),
    ):
        _, score = match_drug("메트포르민정500mg")

    assert score < MATCH_THRESHOLD
