"""Deterministic quality gate for prescription RAG traces.

It diagnoses weak results and proposes experiments. It never changes production
prompts or retrievers automatically; dataset re-evaluation and human approval
remain mandatory.
"""
from __future__ import annotations

from typing import Any

THRESHOLDS = {
    "groundedness": 0.50,
    "source_relevance": 0.50,
    "completeness": 0.60,
    "medical_safety": 0.80,
    "drug_coverage": 0.80,
    "citation_coverage": 0.70,
    "drug_source_match": 0.80,
    "required_section_coverage": 0.80,
}

ACTION_MAP = {
    "RETRIEVAL_RELEVANCE_FAILURE": ["제품명·성분명 검색과 metadata filter, reranker를 검토한다."],
    "GROUNDING_FAILURE": ["각 의료 주장에 source_id를 연결하고 근거 없는 문장은 생성하지 않는다."],
    "INCOMPLETE_GUIDANCE": ["용법·복용시점·주의·중복투여·DUR 체크리스트를 적용한다."],
    "OCR_OR_DRUG_MAPPING_FAILURE": ["OCR 정규화 후 제품명→성분명→동일제제 fallback 매핑을 적용한다."],
    "MEDICAL_SAFETY_REVIEW_REQUIRED": ["의료 전문가 검토 전에는 후보를 운영에 반영하지 않는다."],
}


def classify_rag_failure(scores: dict[str, float], *, excluded_ocr_count: int = 0) -> list[str]:
    failures: list[str] = []
    if scores.get("source_relevance", 1.0) < THRESHOLDS["source_relevance"]:
        failures.append("RETRIEVAL_RELEVANCE_FAILURE")
    if scores.get("groundedness", 1.0) < THRESHOLDS["groundedness"]:
        failures.append("GROUNDING_FAILURE")
    if (
        scores.get("completeness", 1.0) < THRESHOLDS["completeness"]
        or scores.get("required_section_coverage", 1.0) < THRESHOLDS["required_section_coverage"]
    ):
        failures.append("INCOMPLETE_GUIDANCE")
    if excluded_ocr_count or scores.get("drug_coverage", 1.0) < THRESHOLDS["drug_coverage"]:
        failures.append("OCR_OR_DRUG_MAPPING_FAILURE")
    if scores.get("medical_safety", 1.0) < THRESHOLDS["medical_safety"]:
        failures.append("MEDICAL_SAFETY_REVIEW_REQUIRED")
    return failures


def build_quality_diagnosis(
    scores: dict[str, float], *, excluded_items: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    excluded_items = excluded_items or []
    failures = classify_rag_failure(scores, excluded_ocr_count=len(excluded_items))
    actions = [
        {"priority": index + 1, "failure_category": category, "action": action}
        for index, (category, action) in enumerate(
            (category, action) for category in failures for action in ACTION_MAP.get(category, [])
        )
    ]
    return {
        "gate_status": "needs_experiment" if failures else "passed",
        "failure_categories": failures,
        "failed_metrics": {
            name: round(value, 4)
            for name, value in scores.items()
            if name in THRESHOLDS and value < THRESHOLDS[name]
        },
        "excluded_items": excluded_items,
        "recommended_actions": actions,
        "requires_human_review": bool(failures),
        "release_policy": "dataset_re_evaluation_then_human_approval",
    }
