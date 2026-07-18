"""
chat_router.py — patient_id 기반 엔드포인트 소유권 검증 테스트 (issue #21 잔여 범위)

POST /chat/ask, GET /chat/history 두 엔드포인트가 모두:
  - 소유자(보호자) 토큰 → 정상 응답
  - 소유자(환자 본인) 토큰 → 정상 응답
  - 타인 토큰 → 403
  - 무인증 → 401/403 (HTTPBearer에 의해)
를 보장하는지 확인한다. test_records_router_auth.py와 동일한 패턴.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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


def _make_caregiver(session: Session, name: str = "보호자A") -> Caregiver:
    cg = Caregiver(password_hash="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _make_patient(session: Session, name: str = "환자A") -> Patient:
    pt = Patient(password_hash="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _link(session: Session, cg: Caregiver, pt: Patient) -> None:
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


# ──────────────────────────────────────────────────────────────
# POST /chat/ask
# ──────────────────────────────────────────────────────────────

class TestAsk:
    def test_owner_caregiver_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "askOwnerCg")
        pt = _make_patient(session, "askPatA")
        _link(session, cg, pt)
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 200

    def test_owner_patient_ok(self, client: TestClient, session: Session):
        pt = _make_patient(session, "askPatB")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 200

    def test_other_caregiver_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "askOwnerCg2")
        cg_other = _make_caregiver(session, "askOtherCg")
        pt = _make_patient(session, "askPatC")
        _link(session, cg_owner, pt)
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 403

    def test_other_patient_403(self, client: TestClient, session: Session):
        pt_owner = _make_patient(session, "askPatD")
        pt_other = _make_patient(session, "askPatE")
        headers = {"Authorization": f"Bearer {_token(pt_other.id, 'patient')}"}
        r = client.post("/chat/ask", json={"patient_id": pt_owner.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 403

    def test_no_auth_401(self, client: TestClient, session: Session):
        pt = _make_patient(session, "askPatF")
        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": "q1"})
        assert r.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────
# GET /chat/history
# ──────────────────────────────────────────────────────────────

class TestHistory:
    def test_owner_caregiver_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "histOwnerCg")
        pt = _make_patient(session, "histPatA")
        _link(session, cg, pt)
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.get(f"/chat/history?patient_id={pt.id}", headers=headers)
        assert r.status_code == 200

    def test_owner_patient_ok(self, client: TestClient, session: Session):
        pt = _make_patient(session, "histPatB")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        r = client.get(f"/chat/history?patient_id={pt.id}", headers=headers)
        assert r.status_code == 200

    def test_other_caregiver_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "histOwnerCg2")
        cg_other = _make_caregiver(session, "histOtherCg")
        pt = _make_patient(session, "histPatC")
        _link(session, cg_owner, pt)
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.get(f"/chat/history?patient_id={pt.id}", headers=headers)
        assert r.status_code == 403

    def test_other_patient_403(self, client: TestClient, session: Session):
        pt_owner = _make_patient(session, "histPatD")
        pt_other = _make_patient(session, "histPatE")
        headers = {"Authorization": f"Bearer {_token(pt_other.id, 'patient')}"}
        r = client.get(f"/chat/history?patient_id={pt_owner.id}", headers=headers)
        assert r.status_code == 403

    def test_no_auth_401(self, client: TestClient, session: Session):
        pt = _make_patient(session, "histPatF")
        r = client.get(f"/chat/history?patient_id={pt.id}")
        assert r.status_code in (401, 403)
