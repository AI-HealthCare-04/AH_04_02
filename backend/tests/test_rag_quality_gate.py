from services.rag_quality_gate import build_quality_diagnosis, classify_rag_failure


def test_low_retrieval_scores_are_classified_for_experiment():
    scores = {
        "groundedness": 0.25,
        "source_relevance": 0.28,
        "completeness": 0.42,
        "medical_safety": 0.90,
        "drug_coverage": 0.50,
        "required_section_coverage": 0.40,
    }
    failures = classify_rag_failure(scores, excluded_ocr_count=2)
    assert failures == [
        "RETRIEVAL_RELEVANCE_FAILURE",
        "GROUNDING_FAILURE",
        "INCOMPLETE_GUIDANCE",
        "OCR_OR_DRUG_MAPPING_FAILURE",
    ]


def test_quality_diagnosis_never_auto_releases_failed_candidate():
    diagnosis = build_quality_diagnosis(
        {"groundedness": 0.25, "source_relevance": 0.28, "medical_safety": 0.90},
        excluded_items=[{"ocr_text": "약품명", "reason": "drug_master_not_matched"}],
    )
    assert diagnosis["gate_status"] == "needs_experiment"
    assert diagnosis["requires_human_review"] is True
    assert diagnosis["release_policy"] == "dataset_re_evaluation_then_human_approval"


def test_quality_diagnosis_passes_when_every_metric_meets_threshold():
    scores = {
        "groundedness": 0.9,
        "source_relevance": 0.9,
        "completeness": 0.9,
        "medical_safety": 0.9,
        "drug_coverage": 1.0,
        "citation_coverage": 1.0,
        "drug_source_match": 1.0,
        "required_section_coverage": 1.0,
    }
    diagnosis = build_quality_diagnosis(scores)
    assert diagnosis["gate_status"] == "passed"
    assert diagnosis["requires_human_review"] is False
