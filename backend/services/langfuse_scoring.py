"""Automatic Langfuse scoring helpers.

These scores are lightweight operational signals, not a clinical judgment.
They intentionally use deterministic metadata so scoring never adds another
LLM call or blocks the user-facing response.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from services.langfuse_tracing import get_langfuse_client, mask_for_langfuse

logger = logging.getLogger(__name__)

_DANGEROUS_MEDICAL_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"임의로\s*(중단|끊)",
        r"(용량|복용량).{0,8}(늘리|증량|두\s*배)",
        r"(무조건|반드시)\s*(괜찮|안전)",
        r"의사.{0,8}상담.{0,12}(필요\s*없|안\s*해도)",
    )
]
_SAFETY_GUIDANCE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"의사",
        r"약사",
        r"상담",
        r"문의",
        r"응급",
        r"병원",
    )
]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _ratio(count: int | float, target: int | float) -> float:
    if target <= 0:
        return 0.0
    return _clamp(float(count) / float(target))


def _source_ref_count(source_refs: list[dict] | None) -> int:
    return len(source_refs or [])


def _score_current_trace(name: str, value: float, *, comment: str, metadata: dict[str, Any] | None = None) -> None:
    """Write a numeric score to the current Langfuse trace if available."""
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.score_current_trace(
            name=name,
            value=round(_clamp(value), 2),
            data_type="NUMERIC",
            comment=comment,
            metadata=metadata or {},
        )
    except Exception:  # noqa: BLE001 — scoring must never break the app response
        logger.warning("Langfuse 자동 점수(%s) 기록에 실패했습니다.", name, exc_info=True)


def _medical_safety_score(answer: str) -> float:
    dangerous_hits = sum(1 for pattern in _DANGEROUS_MEDICAL_PATTERNS if pattern.search(answer))
    guidance_hits = sum(1 for pattern in _SAFETY_GUIDANCE_PATTERNS if pattern.search(answer))
    return _clamp(0.82 + min(guidance_hits, 3) * 0.04 - dangerous_hits * 0.25)


def _patient_clarity_score(answer: str) -> float:
    if not answer:
        return 0.0
    length_score = 1.0 if len(answer) <= 900 else 0.78 if len(answer) <= 1400 else 0.58
    sentence_count = len([part for part in re.split(r"[.!?。！？\n]+", answer) if part.strip()])
    structure_score = 0.9 if sentence_count >= 2 else 0.72
    jargon_penalty = 0.08 * sum(term in answer for term in ("CYP", "금기", "상호작용", "허가사항", "DUR"))
    return _clamp((length_score + structure_score) / 2 - jargon_penalty)


def score_chat_answer(
    *,
    question: str,
    answer: str,
    answer_source: str,
    source_refs: list[dict] | None,
    rag_context_count: int,
    dur_context_count: int,
) -> None:
    """Score chatbot answers, giving retrieved RAG evidence the highest weight."""
    ref_count = _source_ref_count(source_refs)
    rag_signal = _ratio(rag_context_count, 3)
    ref_signal = _ratio(ref_count, 3)
    dur_signal = _ratio(dur_context_count, 2)
    used_llm = answer_source.startswith("llm")

    # RAG retrieval is the strongest grounding signal. DUR is important too,
    # but it may be external API evidence rather than ChromaDB retrieval.
    evidence_score = rag_signal * 0.70 + ref_signal * 0.20 + dur_signal * 0.10
    source_relevance = _clamp(0.18 + evidence_score * 0.78 if used_llm else 0.25 + ref_signal * 0.35)
    groundedness = _clamp(0.20 + evidence_score * 0.75 + (0.05 if used_llm and ref_count else 0.0))
    completeness = _clamp(0.32 + evidence_score * 0.50 + _ratio(len(answer), 500) * 0.18)

    metadata = {
        "question": mask_for_langfuse(question),
        "answer_source": answer_source,
        "rag_context_count": rag_context_count,
        "dur_context_count": dur_context_count,
        "source_ref_count": ref_count,
        "scoring_method": "heuristic_v1_rag_weighted",
    }
    _score_current_trace(
        "groundedness",
        groundedness,
        comment="RAG context와 source_refs가 많을수록 높게 평가한 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "source_relevance",
        source_relevance,
        comment="RAG 검색 근거를 70% 비중으로 반영한 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "completeness",
        completeness,
        comment="근거 수와 답변 분량을 함께 본 자동 완성도 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "medical_safety",
        _medical_safety_score(answer),
        comment="위험한 복약 지시 표현은 감점하고 의사·약사 상담 안내는 가점한 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "patient_clarity",
        _patient_clarity_score(answer),
        comment="답변 길이와 환자 친화적 표현을 기준으로 한 자동 점수입니다.",
        metadata=metadata,
    )


def score_prescription_guide(
    *,
    medication_guide: dict,
    lifestyle_guide: dict,
    source_refs: list[dict] | None,
    from_cache: bool,
    rag_available: bool,
) -> None:
    """Score prescription guide generation traces."""
    drugs = (medication_guide or {}).get("drugs") or []
    lifestyle_guides = (lifestyle_guide or {}).get("guides") or []
    ref_count = _source_ref_count(source_refs)
    review_required_count = sum(1 for drug in drugs if drug.get("review_required"))
    drugs_with_precautions = sum(1 for drug in drugs if drug.get("precautions") or drug.get("caution"))
    rag_signal = _ratio(ref_count, max(1, len(drugs) + len(lifestyle_guides)))

    metadata = {
        "from_cache": from_cache,
        "rag_available": rag_available,
        "medication_drug_count": len(drugs),
        "lifestyle_guide_count": len(lifestyle_guides),
        "source_ref_count": ref_count,
        "review_required_count": review_required_count,
        "scoring_method": "heuristic_v1_rag_weighted",
    }
    _score_current_trace(
        "groundedness",
        _clamp(0.25 + rag_signal * 0.70),
        comment="복약가이드 source_refs 비율을 가장 크게 반영한 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "source_relevance",
        _clamp(0.25 + rag_signal * 0.72 + (0.03 if rag_available else 0.0)),
        comment="RAG 출처가 약/진단명 결과에 충분히 붙었는지 본 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "completeness",
        _clamp(
            0.20
            + _ratio(len(drugs), 1) * 0.22
            + _ratio(drugs_with_precautions, max(1, len(drugs))) * 0.28
            + _ratio(len(lifestyle_guides), 1) * 0.20
            + rag_signal * 0.10
        ),
        comment="약별 주의사항과 진단명별 생활습관 안내가 채워졌는지 본 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "medical_safety",
        _clamp(0.90 - _ratio(review_required_count, max(1, len(drugs))) * 0.20),
        comment="검토 필요 약품 비율을 반영한 자동 안전성 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "patient_clarity",
        0.82 if drugs or lifestyle_guides else 0.35,
        comment="구조화된 복약/생활습관 안내 존재 여부를 기준으로 한 자동 점수입니다.",
        metadata=metadata,
    )


def score_drug_info_detail(
    *,
    drug_name: str,
    rag_detail: dict,
    patient_summary: dict | None,
    match_score: float,
) -> None:
    """Score drug detail lookups that enrich caution fields from public data."""
    has_precautions = bool(rag_detail.get("precautions"))
    has_side_effects = bool(rag_detail.get("side_effects"))
    has_interactions = bool(rag_detail.get("interactions"))
    dur_caution_count = len(rag_detail.get("dur_cautions") or [])
    evidence_count = sum([has_precautions, has_side_effects, has_interactions]) + min(dur_caution_count, 2)
    evidence_signal = _ratio(evidence_count, 4)

    metadata = {
        "drug_name": mask_for_langfuse(drug_name),
        "match_score": round(match_score, 4),
        "has_precautions": has_precautions,
        "has_side_effects": has_side_effects,
        "has_interactions": has_interactions,
        "has_patient_summary": patient_summary is not None,
        "dur_caution_count": dur_caution_count,
        "scoring_method": "heuristic_v1_rag_weighted",
    }
    _score_current_trace(
        "groundedness",
        _clamp(0.25 + evidence_signal * 0.65 + _ratio(match_score, 1) * 0.10),
        comment="허가사항/e약은요/DUR 근거 필드 존재 여부를 반영한 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "source_relevance",
        _clamp(0.25 + evidence_signal * 0.55 + _ratio(match_score, 1) * 0.20),
        comment="약품명 매칭 점수와 근거 필드 존재 여부를 반영한 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "completeness",
        _clamp(0.25 + evidence_signal * 0.55 + (0.15 if patient_summary else 0.0)),
        comment="주의사항/부작용/상호작용/환자용 요약이 채워졌는지 본 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "medical_safety",
        0.9 if has_precautions or dur_caution_count else 0.62,
        comment="주의사항 또는 DUR 주의 근거가 있으면 높게 평가한 자동 안전성 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "patient_clarity",
        0.88 if patient_summary else 0.55,
        comment="환자용 쉬운 말 요약 생성 여부를 기준으로 한 자동 점수입니다.",
        metadata=metadata,
    )


def score_ocr_extraction(
    *,
    medication_count: int,
    diagnosis_count: int,
    low_confidence_count: int,
    review_required: bool,
    false_positive_hint_count: int = 0,
) -> None:
    """Score OCR extraction quality for prescription upload test traces."""
    med_signal = _ratio(medication_count, 3)
    diagnosis_signal = _ratio(diagnosis_count, 1)
    confidence_penalty = _ratio(low_confidence_count, max(1, medication_count)) * 0.25
    false_positive_penalty = _ratio(false_positive_hint_count, max(1, medication_count)) * 0.20

    metadata = {
        "medication_count": medication_count,
        "diagnosis_count": diagnosis_count,
        "low_confidence_count": low_confidence_count,
        "review_required": review_required,
        "false_positive_hint_count": false_positive_hint_count,
        "scoring_method": "heuristic_v1_ocr_extraction",
    }
    _score_current_trace(
        "source_relevance",
        _clamp(0.25 + med_signal * 0.45 + diagnosis_signal * 0.25 - false_positive_penalty),
        comment="OCR 결과에 약품명과 진단명이 실제로 추출됐는지 본 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "completeness",
        _clamp(0.25 + med_signal * 0.40 + diagnosis_signal * 0.30 - confidence_penalty),
        comment="약품 개수, 진단명 추출, 낮은 신뢰도 비율을 반영한 OCR 완성도 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "groundedness",
        _clamp(0.30 + med_signal * 0.35 + diagnosis_signal * 0.25 - false_positive_penalty),
        comment="처방전에서 구조화된 약/진단 근거를 얼마나 확보했는지 본 자동 점수입니다.",
        metadata=metadata,
    )
    _score_current_trace(
        "medical_safety",
        0.72 if review_required else 0.88,
        comment="검토 필요 상태이면 OCR 결과를 그대로 신뢰하지 않도록 낮게 표시한 자동 점수입니다.",
        metadata=metadata,
    )
