"""
chat_router.py — POST /chat/ask/stream (REQ-021 SSE) 테스트 (2026-07-19 신규, 담당: 김영혜)

테스트 환경은 CHAT_PROVIDER가 기본값(stub)이라 _CHAT_LLM_AVAILABLE이 항상 False다 —
실제 LLM 스트리밍(astream 토큰 단위 분할)까지는 재현하지 않지만, /ask와 동일한
question_id/question 해석 규칙, IDOR 보호, SSE 폴백 응답 형태, ChatMessage 저장을
결정적으로 검증한다.
"""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import routers.chat_router as chat_router
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, ChatMessage, Patient, PatientMedication
from routers.chat_router import PRESET_QUESTIONS
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


def _install_mock_llm(monkeypatch: pytest.MonkeyPatch, answer: str) -> MagicMock:
    """CHAT_PROVIDER=real / API 키 있음 상태(_CHAT_LLM_AVAILABLE=True)를 mock으로 흉내내고,
    langchain_openai.ChatOpenAI를 가짜로 바꿔 실제 네트워크 호출 없이 호출 여부만 검증한다.
    반환한 MagicMock으로 .assert_not_called()/.assert_called() 확인."""
    import langchain_openai

    response = MagicMock()
    response.content = answer
    instance = MagicMock()
    instance.invoke.return_value = response

    async def _astream(messages, config=None):
        for piece in answer.split():
            chunk = MagicMock()
            chunk.content = piece + " "
            yield chunk

    instance.astream = _astream
    chat_cls = MagicMock(return_value=instance)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", chat_cls)
    monkeypatch.setattr(chat_router, "_CHAT_LLM_AVAILABLE", True)
    monkeypatch.setattr(
        chat_router, "_rag_settings",
        SimpleNamespace(OPENAI_MODEL="gpt-test", OPENAI_API_KEY="test-key"),
        raising=False,
    )
    return chat_cls


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _make_patient(session: Session, name: str = "환자") -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_caregiver(session: Session, name: str = "보호자") -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


class TestAskStreamAuth:
    def test_other_caregiver_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "owner")
        cg_other = _make_caregiver(session, "other")
        pt = _make_patient(session)
        session.add(CaregiverPatient(caregiver_id=cg_owner.id, patient_id=pt.id))
        session.commit()
        headers = {"Authorization": f"Bearer {create_access_token(cg_other.id, 'caregiver')}"}

        r = client.post("/chat/ask/stream", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 403

    def test_no_auth_401(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        r = client.post("/chat/ask/stream", json={"patient_id": pt.id, "question_id": "q1"})
        assert r.status_code in (401, 403)

    def test_unknown_question_id_404s(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        r = client.post(
            "/chat/ask/stream", json={"patient_id": pt.id, "question_id": "no-such-id"}, headers=headers
        )
        assert r.status_code == 404

    def test_missing_question_id_and_question_422s(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        r = client.post("/chat/ask/stream", json={"patient_id": pt.id}, headers=headers)
        assert r.status_code == 422


class TestAskStreamFallback:
    def test_preset_question_streams_fallback_and_persists_message(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}

        r = client.post("/chat/ask/stream", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(r.text)
        assert any("delta" in e for e in events)
        done = next(e for e in events if e.get("done"))
        assert done["answer_source"] == "preset"
        assert done["partial"] is False

        msg = session.exec(select(ChatMessage).where(ChatMessage.patient_id == pt.id)).first()
        assert msg is not None
        assert msg.question_id == "q1"
        assert "식후" in msg.answer_text or "식사" in msg.answer_text or len(msg.answer_text) > 0

    def test_dynamic_question_id_resolves_drug_specific_answer(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        session.add(
            PatientMedication(
                patient_id=pt.id, medication_name="암로디핀정5밀리그램", source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}

        listed = client.get(
            "/chat/questions", params={"patient_id": pt.id, "drug_name": "암로디핀정5밀리그램"}, headers=headers
        )
        dyn_id = listed.json()[0]["id"]

        r = client.post("/chat/ask/stream", json={"patient_id": pt.id, "question_id": dyn_id}, headers=headers)
        assert r.status_code == 200
        events = _parse_sse(r.text)
        deltas = "".join(e["delta"] for e in events if "delta" in e)
        assert "암로디핀정5밀리그램" in deltas

    def test_freeform_question_streams_unsupported_fallback(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}

        r = client.post(
            "/chat/ask/stream", json={"patient_id": pt.id, "question": "임의의 자유 질문입니다"}, headers=headers
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        done = next(e for e in events if e.get("done"))
        assert done["answer_source"] == "unsupported"

        msg = session.exec(select(ChatMessage).where(ChatMessage.patient_id == pt.id)).first()
        assert msg.question_id == "freeform"
        assert msg.question_text == "임의의 자유 질문입니다"


def _mock_llm(monkeypatch: pytest.MonkeyPatch, answer: str = "테스트 답변입니다.") -> None:
    """_CHAT_LLM_AVAILABLE=True(실 LLM 사용 조건)를 흉내내고 ChatOpenAI를 가짜로 바꿔
    실제 호출 없이 답변만 채운다."""
    import langchain_openai

    response = MagicMock()
    response.content = answer
    fake_chat = MagicMock()
    fake_chat.invoke.return_value = response

    async def _fake_astream(*_args, **_kwargs):
        yield SimpleNamespace(content=answer)

    fake_chat.astream = _fake_astream

    monkeypatch.setattr(chat_router, "_CHAT_LLM_AVAILABLE", True)
    monkeypatch.setattr(chat_router, "_rag_settings", SimpleNamespace(OPENAI_MODEL="gpt-test", OPENAI_API_KEY="test-key"), raising=False)
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", MagicMock(return_value=fake_chat))


class TestSourceRefs:
    """[2026-07-20 이슈1 수정] source_refs가 실제 ChromaDB 검색 결과를 반영하는지 —
    답변 생성 방법 라벨(answer_source)이 아니라 진짜 인용 데이터가 응답에 담기는지 검증."""

    def _fake_docs(self):
        return [
            SimpleNamespace(
                page_content="테스트 본문",
                metadata={"item_name": "타이레놀정500밀리그람(아세트아미노펜)", "field_label": "주의사항"},
            )
        ]

    def test_ask_returns_real_retrieved_source_refs(self, client: TestClient, session: Session, monkeypatch):
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        _mock_llm(monkeypatch)
        monkeypatch.setattr("rag.vectorstore.similarity_search", lambda *a, **k: self._fake_docs())

        r = client.post(
            "/chat/ask", json={"patient_id": pt.id, "question": "이 약 먹어도 되나요?"}, headers=headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["source_refs"] == [
            {"item_name": "타이레놀정500밀리그람(아세트아미노펜)", "field": "주의사항"}
        ]

    def test_dur_only_question_surfaces_dur_source_ref(self, client: TestClient, session: Session, monkeypatch):
        """[2026-07-24 추가] DUR 전용 질문(_should_answer_from_dur_only)은 ChromaDB를
        건너뛰므로 위 두 테스트(ChromaDB 문서 기반)와 겹치지 않는 별도 경로다 — 이 경로도
        source_refs가 채워지는지(예전엔 프롬프트 텍스트로만 쓰이고 프론트엔 전혀 안
        내려가서 "출처: AI 실시간 답변"만 보였다) 확인한다."""
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        _mock_llm(monkeypatch)
        monkeypatch.setattr("rag.mfds_client.search_by_name", lambda *a, **k: [])
        monkeypatch.setattr("rag.mfds_client.search_permit_info", lambda *a, **k: [])
        # "임부금기 있어?"는 병용금기가 아니라 주의정보(cautions) 조회 의도라
        # (_dur_lookup_modes) 병용금기(taboo) mock은 이 질문에서 쓰이지 않는다 — 실제로
        # 호출되는 쪽(caution)에 데이터를 넣는다.
        caution = SimpleNamespace(category="임부금기", extra="1등급", detail="태아 위해 가능성")
        monkeypatch.setattr(chat_router, "_search_dur_taboo", lambda _name: [])
        monkeypatch.setattr(chat_router, "_search_dur_cautions", lambda _name: [caution])

        r = client.post(
            "/chat/ask", json={"patient_id": pt.id, "question": "타이레놀 임부금기 있어?"}, headers=headers
        )

        assert r.status_code == 200
        # _extract_dur_candidate_drug_names가 "임부금기"도 후보로 같이 뽑아 캐션 mock이
        # 두 번 불려서(기존 test_chat_router_context.py 테스트들도 이 노이즈 때문에 정확한
        # 리스트 대신 any()로 확인한다) 목록 전체가 아니라 원하는 항목이 있는지만 확인한다.
        assert {
            "item_name": "타이레놀",
            "dur_category": "임부금기",
            "dur_extra": "1등급",
            "dur_detail": "태아 위해 가능성",
        } in r.json()["source_refs"]

    def test_ask_stream_done_event_includes_source_refs(self, client: TestClient, session: Session, monkeypatch):
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        _mock_llm(monkeypatch)
        monkeypatch.setattr("rag.vectorstore.similarity_search", lambda *a, **k: self._fake_docs())

        r = client.post(
            "/chat/ask/stream", json={"patient_id": pt.id, "question": "이 약 먹어도 되나요?"}, headers=headers
        )
        assert r.status_code == 200
        done = next(e for e in _parse_sse(r.text) if e.get("done"))
        assert done["source_refs"] == [
            {"item_name": "타이레놀정500밀리그람(아세트아미노펜)", "field": "주의사항"}
        ]

    def test_ask_stream_creates_langfuse_generation_observation(
        self, client: TestClient, session: Session, monkeypatch
    ):
        """스트리밍 답변도 Langfuse에서 LLM 생성 구간을 별도 generation으로 확인할 수 있어야 한다."""
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        _mock_llm(monkeypatch)
        monkeypatch.setattr("rag.vectorstore.similarity_search", lambda *a, **k: self._fake_docs())

        observations = []

        @contextmanager
        def fake_observation(**kwargs):
            observations.append(kwargs)
            observation = MagicMock()
            yield observation

        monkeypatch.setattr(chat_router, "optional_observation", fake_observation)

        r = client.post(
            "/chat/ask/stream", json={"patient_id": pt.id, "question": "이 약 먹어도 되나요?"}, headers=headers
        )

        assert r.status_code == 200
        assert any(
            item.get("name") == "chat-stream-llm-answer" and item.get("as_type") == "generation"
            for item in observations
        )

    def test_preset_question_has_no_source_refs(self, client: TestClient, session: Session):
        """preset/dynamic 매칭은 RAG 조회 자체를 안 하므로(_CHAT_LLM_AVAILABLE=False,
        stub 기본값) source_refs가 빈 배열이어야 한다."""
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["source_refs"] == []


class TestAskStreamLlmGating:
    """버그1(/ask/stream): preset/dynamic 고정 답변이 매칭되면 LLM을 태우지 않고 바로
    고정 답변을 스트리밍해야 한다. LLM은 freeform 자유입력일 때만 호출."""

    def test_preset_question_does_not_call_llm_even_when_available(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "이건 LLM이 만든 답변이면 안 됩니다")
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}

        r = client.post("/chat/ask/stream", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 200

        chat_cls.assert_not_called()  # LLM으로 새어나가면 안 됨
        events = _parse_sse(r.text)
        done = next(e for e in events if e.get("done"))
        assert done["answer_source"] == "preset"
        deltas = "".join(e["delta"] for e in events if "delta" in e)
        assert deltas == PRESET_QUESTIONS[0]["answer"]

    def test_dynamic_question_does_not_call_llm_even_when_available(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "LLM이 만든 답변이면 안 됩니다")
        pt = _make_patient(session)
        session.add(
            PatientMedication(
                patient_id=pt.id, medication_name="암로디핀정5밀리그램", source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        dyn_id = client.get(
            "/chat/questions", params={"patient_id": pt.id, "drug_name": "암로디핀정5밀리그램"}, headers=headers
        ).json()[0]["id"]

        r = client.post("/chat/ask/stream", json={"patient_id": pt.id, "question_id": dyn_id}, headers=headers)
        assert r.status_code == 200

        chat_cls.assert_not_called()
        events = _parse_sse(r.text)
        assert next(e for e in events if e.get("done"))["answer_source"] == "preset"
        deltas = "".join(e["delta"] for e in events if "delta" in e)
        assert "암로디핀정5밀리그램" in deltas

    def test_freeform_question_calls_llm(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "자유질문 답변")
        pt = _make_patient(session)
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}

        r = client.post(
            "/chat/ask/stream", json={"patient_id": pt.id, "question": "이 앱은 뭐하는 앱이야?"}, headers=headers
        )
        assert r.status_code == 200

        chat_cls.assert_called()  # freeform은 여전히 LLM 호출(회귀 방지)
        events = _parse_sse(r.text)
        assert next(e for e in events if e.get("done"))["answer_source"].startswith("llm")
        deltas = "".join(e["delta"] for e in events if "delta" in e)
        assert "자유질문" in deltas
