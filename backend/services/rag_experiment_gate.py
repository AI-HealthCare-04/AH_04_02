"""Offline dataset gate for proposed prescription RAG changes.

This module only evaluates experiment results. Passing the gate makes a change
eligible for human review; it never updates prompts, retrievers, or production.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from services.rag_quality_gate import THRESHOLDS


def evaluate_rag_dataset(
    candidate_rows: Iterable[Mapping[str, Any]],
    *,
    baseline_rows: Iterable[Mapping[str, Any]] | None = None,
    max_regression: float = 0.02,
) -> dict[str, Any]:
    """Aggregate an evaluation dataset and decide if it can enter human review."""
    candidate = list(candidate_rows)
    baseline = list(baseline_rows or [])
    candidate_summary = _summarize(candidate)
    baseline_summary = _summarize(baseline) if baseline else None

    failed_thresholds = {
        metric: value
        for metric, value in candidate_summary["averages"].items()
        if metric in THRESHOLDS and value < THRESHOLDS[metric]
    }
    regressions: dict[str, float] = {}
    if baseline_summary:
        for metric, baseline_value in baseline_summary["averages"].items():
            candidate_value = candidate_summary["averages"].get(metric)
            if candidate_value is not None and candidate_value < baseline_value - max_regression:
                regressions[metric] = round(candidate_value - baseline_value, 4)

    eligible = bool(candidate) and not failed_thresholds and not regressions
    return {
        "candidate": candidate_summary,
        "baseline": baseline_summary,
        "failed_thresholds": failed_thresholds,
        "regressions": regressions,
        "eligible_for_human_review": eligible,
        "production_change_allowed": False,
        "decision": "awaiting_human_approval" if eligible else "experiment_failed",
    }


def _summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    failed_cases: list[str] = []
    for index, row in enumerate(rows):
        scores = row.get("scores") or {}
        case_id = str(row.get("case_id") or index)
        case_failed = False
        for metric, raw_value in scores.items():
            if not isinstance(raw_value, (int, float)):
                continue
            value = float(raw_value)
            totals[metric] = totals.get(metric, 0.0) + value
            counts[metric] = counts.get(metric, 0) + 1
            if metric in THRESHOLDS and value < THRESHOLDS[metric]:
                case_failed = True
        if case_failed:
            failed_cases.append(case_id)
    return {
        "case_count": len(rows),
        "averages": {
            metric: round(total / counts[metric], 4) for metric, total in totals.items()
        },
        "failed_case_ids": failed_cases,
    }
