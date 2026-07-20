"""
chat_router.py — POST /chat/ask/stream (REQ-021 SSE) 테스트 (2026-07-19 신규, 담당: 김영혜)

테스트 환경은 CHAT_PROVIDER가 기본값(stub)이라 _CHAT_LLM_AVAILABLE이 항상 False다 —
실제 LLM 스트리밍(astream 토큰 단위 분할)까지는 재현하지 않지만, /ask와 동일한
question_id/question 해석 규칙, IDOR 보호, SSE 폴백 응답 형태, ChatMessage 저장을
결정적으로 검증한다.
"""
import json

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, ChatMessage, Patient, PatientMedication
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


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

        listed = client.get("/chat/questions", params={"patient_id": pt.id}, headers=headers)
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
