"""DELETE /trust/relations/{trust_id} — REQ-004 돌봄관계 해제 테스트.

care_level에 따라 즉시 해제(independent/guardian_check)와
승인 대기(third_party_needed) 두 경로를 검증한다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import CareLevelAssessment, Caregiver, CaregiverPatient, Patient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _make_patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_caregiver(session: Session) -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _link(session: Session, cg: Caregiver, pt: Patient) -> CaregiverPatient:
    link = CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


def _assess(session: Session, pt: Patient, care_level: str) -> None:
    session.add(CareLevelAssessment(patient_id=pt.id, care_level=care_level))
    session.commit()


def _cg_headers(cg: Caregiver) -> dict:
    return {"Authorization": f"Bearer {create_access_token(cg.id, 'caregiver')}"}


# ── 즉시 해제 ──────────────────────────────────────────────

class TestImmediateRevocation:
    def test_independent_immediately_revoked(self, client: TestClient, session: Session):
        cg, pt = _make_caregiver(session), _make_patient(session)
        link = _link(session, cg, pt)
        _assess(session, pt, "independent")

        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "revoked"
        assert body["revoked_at"] is not None
        assert body["revocation_requested_by"] is None

    def test_guardian_check_immediately_revoked(self, client: TestClient, session: Session):
        cg, pt = _make_caregiver(session), _make_patient(session)
        link = _link(session, cg, pt)
        _assess(session, pt, "guardian_check")

        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "revoked"
        assert body["revoked_at"] is not None

    def test_no_assessment_defaults_to_immediate_revocation(self, client: TestClient, session: Session):
        """평가 이력 없으면 independent로 간주 → 즉시 해제"""
        cg, pt = _make_caregiver(session), _make_patient(session)
        link = _link(session, cg, pt)
        # CareLevelAssessment 없음

        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))

        assert r.status_code == 200
        assert r.json()["status"] == "revoked"

    def test_immediate_revoke_last_link_returns_should_alert_now_true(
        self, client: TestClient, session: Session
    ):
        """즉시 해제로 마지막 active 연결이 끊기면 should_alert_now=True (REQ-007a, 김영혜 지적)."""
        cg, pt = _make_caregiver(session), _make_patient(session)
        link = _link(session, cg, pt)
        _assess(session, pt, "independent")

        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "revoked"
        assert body["should_alert_now"] is True

    def test_immediate_revoke_with_remaining_link_returns_should_alert_now_false(
        self, client: TestClient, session: Session
    ):
        """즉시 해제 후 다른 active 연결이 남아있으면 should_alert_now=False."""
        cg1, cg2, pt = _make_caregiver(session), _make_caregiver(session), _make_patient(session)
        link1 = _link(session, cg1, pt)
        _link(session, cg2, pt)  # 두 번째 보호자 연결
        _assess(session, pt, "independent")

        r = client.delete(f"/trust/relations/{link1.id}", headers=_cg_headers(cg1))

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "revoked"
        assert body["should_alert_now"] is False


# ── 승인 대기 ──────────────────────────────────────────────

class TestRevocationPending:
    def test_third_party_needed_sets_pending_and_records_requester(
        self, client: TestClient, session: Session
    ):
        cg, pt = _make_caregiver(session), _make_patient(session)
        link = _link(session, cg, pt)
        _assess(session, pt, "third_party_needed")

        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "revocation_pending"
        assert body["revoked_at"] is None
        assert body["revocation_requested_by"] == cg.id


# ── 에러 케이스 ────────────────────────────────────────────

class TestDissolutionErrors:
    def test_nonexistent_trust_id_404(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        headers = _cg_headers(cg)

        r = client.delete("/trust/relations/99999", headers=headers)

        assert r.status_code == 404

    def test_already_revoked_409(self, client: TestClient, session: Session):
        cg, pt = _make_caregiver(session), _make_patient(session)
        link = _link(session, cg, pt)
        _assess(session, pt, "independent")

        client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))
        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg))

        assert r.status_code == 409

    def test_unrelated_caregiver_403(self, client: TestClient, session: Session):
        cg_owner, cg_other = _make_caregiver(session), _make_caregiver(session)
        pt = _make_patient(session)
        link = _link(session, cg_owner, pt)

        r = client.delete(f"/trust/relations/{link.id}", headers=_cg_headers(cg_other))

        assert r.status_code == 403