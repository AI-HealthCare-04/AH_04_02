from __future__ import annotations

from types import SimpleNamespace

from services.ocr_quality import (
    explain_auto_guide_exclusion,
    is_auto_guide_eligible_ocr_item,
    requires_drug_name_review,
)


def test_obvious_sample_text_requires_review():
    assert requires_drug_name_review("샘플은OCR", "아펜CR정", 0.5714) is True


def test_low_confidence_changed_drug_name_requires_review():
    assert requires_drug_name_review("튼튼정", "고리튼정", 0.8) is True
    assert requires_drug_name_review("장다정", "암로다정", 0.8) is True


def test_exact_high_confidence_match_is_auto_guide_eligible():
    item = SimpleNamespace(
        drug_name="노바스크정5밀리그람",
        matched_drug_name="노바스크정5밀리그람",
        display_name="노바스크정5밀리그람",
        match_score=1.0,
        needs_review=False,
    )

    assert is_auto_guide_eligible_ocr_item(item) is True


def test_changed_name_under_auto_guide_threshold_is_excluded():
    item = SimpleNamespace(
        drug_name="튼튼정",
        matched_drug_name="고리튼정",
        display_name="고리튼정",
        match_score=0.8,
        needs_review=False,
    )

    assert is_auto_guide_eligible_ocr_item(item) is False


def test_already_review_required_item_is_excluded():
    item = SimpleNamespace(
        drug_name="노바스크정5밀리그람",
        matched_drug_name="노바스크정5밀리그람",
        display_name="노바스크정5밀리그람",
        match_score=1.0,
        needs_review=True,
    )

    assert is_auto_guide_eligible_ocr_item(item) is False


def test_exclusion_diagnostic_records_reason_and_candidate():
    item = SimpleNamespace(
        drug_name="sample OCR",
        matched_drug_name="sample drug",
        display_name="sample drug",
        match_score=0.57,
        needs_review=True,
    )

    diagnostic = explain_auto_guide_exclusion(item)

    assert diagnostic == {
        "ocr_text": "sample OCR",
        "reason": "non_drug_instruction",
        "best_candidate": "sample drug",
        "similarity": 0.57,
    }
