from services.rag_experiment_gate import evaluate_rag_dataset


def _scores(value: float) -> dict[str, float]:
    return {
        "groundedness": value,
        "source_relevance": value,
        "completeness": value,
        "medical_safety": value,
        "drug_coverage": value,
        "citation_coverage": value,
        "drug_source_match": value,
        "required_section_coverage": value,
    }


def test_dataset_gate_never_allows_automatic_production_change():
    result = evaluate_rag_dataset([{"case_id": "good", "scores": _scores(1.0)}])

    assert result["eligible_for_human_review"] is True
    assert result["decision"] == "awaiting_human_approval"
    assert result["production_change_allowed"] is False


def test_dataset_gate_rejects_threshold_failure_and_regression():
    candidate = [{"case_id": "weak", "scores": _scores(0.4)}]
    baseline = [{"case_id": "baseline", "scores": _scores(0.9)}]

    result = evaluate_rag_dataset(candidate, baseline_rows=baseline)

    assert result["eligible_for_human_review"] is False
    assert "groundedness" in result["failed_thresholds"]
    assert result["regressions"]["groundedness"] == -0.5
    assert result["decision"] == "experiment_failed"
