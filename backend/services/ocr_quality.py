"""OCR drug-name quality gates.

The fuzzy matcher is useful for recovering typos, but it can also turn text
near the prescription table ("튼튼", "샘플 OCR") into plausible drug names.
This module keeps that risk out of automatic RAG guide generation.
"""
from __future__ import annotations

import re
from typing import Any

from services.drug_matcher import MATCH_THRESHOLD

# Fuzzy matching below 0.7 is simply uncertain. Even above that, if the matcher
# changes the OCR text into another drug name, we require a stronger score before
# using it for automatic RAG guide generation.
AUTO_GUIDE_MATCH_THRESHOLD = 0.85

_OBVIOUS_NOISE_RE = re.compile(
    r"샘플|OCR|가상|처방전|약국|병원|의원|의료기관|환자|성명|전화번호",
    re.IGNORECASE,
)


def _compact(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s\-_()/.,·]+", "", value).lower()


def is_obvious_ocr_noise(drug_name: str | None) -> bool:
    """Return True for OCR text that is clearly not a drug name."""
    return bool(drug_name and _OBVIOUS_NOISE_RE.search(drug_name))


def requires_drug_name_review(raw_name: str, matched_name: str, match_score: float) -> bool:
    """Whether a parsed drug row needs human review before guide generation."""
    if is_obvious_ocr_noise(raw_name) or is_obvious_ocr_noise(matched_name):
        return True
    if match_score < MATCH_THRESHOLD:
        return True
    # Example: "튼튼정" can be changed to a real item "고리튼정" with score 0.8.
    # That is too risky for automatic patient-facing guide generation.
    if matched_name and _compact(raw_name) != _compact(matched_name) and match_score < AUTO_GUIDE_MATCH_THRESHOLD:
        return True
    return False


def is_auto_guide_eligible_ocr_item(item: Any) -> bool:
    """Whether an OcrResult-like object can be used for automatic RAG guides."""
    raw_name = getattr(item, "drug_name", "") or ""
    matched_name = getattr(item, "matched_drug_name", "") or ""
    display_name = getattr(item, "display_name", raw_name) or raw_name
    match_score = float(getattr(item, "match_score", 0.0) or 0.0)

    if getattr(item, "needs_review", False):
        return False
    if is_obvious_ocr_noise(raw_name) or is_obvious_ocr_noise(matched_name) or is_obvious_ocr_noise(display_name):
        return False
    if match_score > 0 and match_score < MATCH_THRESHOLD:
        return False
    if matched_name and _compact(raw_name) != _compact(matched_name) and 0 < match_score < AUTO_GUIDE_MATCH_THRESHOLD:
        return False
    return True


def explain_auto_guide_exclusion(item: Any) -> dict[str, Any] | None:
    """Return a non-PII diagnostic when an OCR row is excluded from auto guidance."""
    if is_auto_guide_eligible_ocr_item(item):
        return None
    raw_name = getattr(item, "drug_name", "") or ""
    matched_name = getattr(item, "matched_drug_name", "") or ""
    display_name = getattr(item, "display_name", raw_name) or raw_name
    score = float(getattr(item, "match_score", 0.0) or 0.0)
    if getattr(item, "needs_review", False):
        reason = "human_review_required"
    elif (
        is_obvious_ocr_noise(raw_name)
        or is_obvious_ocr_noise(matched_name)
        or is_obvious_ocr_noise(display_name)
    ):
        reason = "non_drug_instruction"
    elif score and score < MATCH_THRESHOLD:
        reason = "drug_master_not_matched"
    else:
        reason = "ambiguous_drug_mapping"
    return {
        "ocr_text": raw_name,
        "reason": reason,
        "best_candidate": matched_name or None,
        "similarity": round(score, 4),
    }
