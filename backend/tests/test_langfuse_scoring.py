from __future__ import annotations

import services.langfuse_scoring as scoring
from services.langfuse_scoring import (
    score_chat_answer,
    score_drug_info_detail,
    score_ocr_extraction,
    score_prescription_guide,
)


class FakeLangfuseClient:
    def __init__(self, trace_id: str | None = None):
        self.scores: list[dict] = []
        self.trace_id = trace_id

    def get_current_trace_id(self):
        return self.trace_id

    def score_current_trace(self, **kwargs):
        self.scores.append(kwargs)

    def create_score(self, **kwargs):
        self.scores.append(kwargs)


class FakeObservation:
    def __init__(self):
        self.updates: list[dict] = []
        self.scores: list[dict] = []

    def update(self, **kwargs):
        self.updates.append(kwargs)

    def score(self, **kwargs):
        self.scores.append(kwargs)


def _score_map(client: FakeLangfuseClient) -> dict[str, float]:
    return {item["name"]: item["value"] for item in client.scores}


def test_chat_answer_rag_retrieval_gets_higher_grounding_scores(monkeypatch):
    high_client = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: high_client)

    score_chat_answer(
        question="노바스크정5mg 주의사항 알려줘",
        answer="근거에 따르면 어지러움이 있으면 의사나 약사에게 상담하세요.",
        answer_source="llm (gpt-4o-mini)",
        source_refs=[
            {"item_name": "노바스크정5밀리그램", "field": "precautions"},
            {"disease": "고혈압", "source": "질병관리청 국가건강정보포털"},
            {"dur_category": "노인주의", "dur_detail": "어지러움 주의"},
        ],
        rag_context_count=3,
        dur_context_count=1,
    )

    low_client = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: low_client)

    score_chat_answer(
        question="노바스크정5mg 주의사항 알려줘",
        answer="정확한 정보는 의사나 약사에게 문의하세요.",
        answer_source="llm (gpt-4o-mini)",
        source_refs=[],
        rag_context_count=0,
        dur_context_count=0,
    )

    high_scores = _score_map(high_client)
    low_scores = _score_map(low_client)
    assert high_scores["groundedness"] > low_scores["groundedness"]
    assert high_scores["source_relevance"] > low_scores["source_relevance"]
    assert high_scores["source_relevance"] >= 0.8


def test_chat_answer_records_auto_scores_in_trace_output(monkeypatch):
    client = FakeLangfuseClient()
    observation = FakeObservation()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: client)

    score_chat_answer(
        question="고혈압 생활습관 알려줘",
        answer="근거에 따르면 싱겁게 먹고, 의사나 약사에게 문의하세요.",
        answer_source="llm (gpt-4o-mini)",
        source_refs=[{"disease": "고혈압", "source": "질병관리청 국가건강정보포털"}],
        rag_context_count=2,
        dur_context_count=0,
        observation=observation,
    )

    assert observation.updates
    output = observation.updates[-1]["output"]
    assert output["auto_score_method"] == "heuristic_v1_rag_weighted"
    assert set(output["auto_scores"]) >= {
        "groundedness",
        "source_relevance",
        "completeness",
        "medical_safety",
        "patient_clarity",
    }
    # [2026-07-31 버그수정 회귀 테스트] observation이 있으면 observation.score()로 그
    # 특정 span에 점수가 붙어야 한다 — client.create_score(trace_id=...)로만 붙이면
    # Langfuse UI에서 그 observation을 peek하며 보는 Scores 탭엔 안 뜬다(observationId
    # 없는 트레이스-레벨 점수라서). client.scores가 비어있다는 것으로 트레이스-레벨
    # fallback 경로를 안 탔다는 것까지 함께 확인한다.
    assert _score_map(observation)["groundedness"] == output["auto_scores"]["groundedness"]
    assert client.scores == []


def test_chat_answer_creates_scores_with_current_trace_id(monkeypatch):
    client = FakeLangfuseClient(trace_id="trace-123")
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: client)

    score_chat_answer(
        question="노바스크 주의사항 알려줘",
        answer="근거에 따르면 어지러움이 있으면 의사나 약사에게 상담하세요.",
        answer_source="llm (gpt-4o-mini)",
        source_refs=[{"item_name": "노바스크정5밀리그램", "field": "주의사항"}],
        rag_context_count=1,
        dur_context_count=0,
    )

    assert client.scores
    assert all(score["trace_id"] == "trace-123" for score in client.scores)
    assert {score["name"] for score in client.scores} >= {"groundedness", "source_relevance"}


def test_chat_answer_dangerous_instruction_lowers_medical_safety(monkeypatch):
    client = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: client)

    score_chat_answer(
        question="약을 끊어도 되나요?",
        answer="의사 상담은 필요 없고 임의로 중단해도 안전합니다.",
        answer_source="llm (gpt-4o-mini)",
        source_refs=[{"item_name": "테스트약"}],
        rag_context_count=1,
        dur_context_count=0,
    )

    assert _score_map(client)["medical_safety"] < 0.7


def test_prescription_guide_scores_source_refs_and_lifestyle_completeness(monkeypatch):
    client = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: client)

    score_prescription_guide(
        medication_guide={
            "drugs": [
                {"drug_name": "노바스크정5밀리그램", "precautions": "어지러움 주의", "review_required": False}
            ]
        },
        lifestyle_guide={
            "guides": [
                {
                    "diagnosis": "고혈압",
                    "diet": {"recommended": ["싱겁게 먹기"], "avoid": ["짠 음식"]},
                    "exercise": {"recommended": ["걷기"], "avoid": []},
                }
            ]
        },
        source_refs=[
            {"item_name": "노바스크정5밀리그램", "field": "precautions"},
            {"disease": "고혈압", "source": "질병관리청 국가건강정보포털"},
        ],
        from_cache=False,
        rag_available=True,
    )

    scores = _score_map(client)
    assert scores["groundedness"] >= 0.9
    assert scores["completeness"] >= 0.9


def test_drug_info_detail_patient_summary_improves_clarity(monkeypatch):
    with_summary = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: with_summary)

    score_drug_info_detail(
        drug_name="노바스크정5밀리그램",
        rag_detail={
            "precautions": "어지러움 주의",
            "side_effects": "두통",
            "interactions": "다른 혈압약",
            "dur_cautions": [{"category": "노인주의"}],
        },
        patient_summary={"must_check": ["심한 어지러움이 있으면 상담하세요"]},
        match_score=0.98,
    )

    without_summary = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: without_summary)

    score_drug_info_detail(
        drug_name="노바스크정5밀리그램",
        rag_detail={"precautions": None, "side_effects": None, "interactions": None, "dur_cautions": []},
        patient_summary=None,
        match_score=0.98,
    )

    assert _score_map(with_summary)["patient_clarity"] > _score_map(without_summary)["patient_clarity"]


def test_ocr_extraction_scores_diagnosis_and_false_positive_hints(monkeypatch):
    clean_client = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: clean_client)

    score_ocr_extraction(
        medication_count=3,
        diagnosis_count=2,
        low_confidence_count=0,
        review_required=False,
        false_positive_hint_count=0,
    )

    noisy_client = FakeLangfuseClient()
    monkeypatch.setattr(scoring, "get_langfuse_client", lambda: noisy_client)

    score_ocr_extraction(
        medication_count=3,
        diagnosis_count=0,
        low_confidence_count=1,
        review_required=True,
        false_positive_hint_count=1,
    )

    clean_scores = _score_map(clean_client)
    noisy_scores = _score_map(noisy_client)
    assert clean_scores["completeness"] > noisy_scores["completeness"]
    assert clean_scores["source_relevance"] > noisy_scores["source_relevance"]
