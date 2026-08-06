"""PATCH /monitoring/caregivers/{caregiver_id}/patients/{patient_id}/notifications
(2026-07-30 신규).

여러 환자를 관리하는 보호자·기관이 "이 환자 알림은 이 기기로 안 받고 싶다"를
(보호자, 환자) 관계 단위로 끄고 켤 수 있게 하는 엔드포인트. NotificationSetting(환자
단위, 모든 보호자가 공유)과 달리 CaregiverPatient.notifications_enabled에 저장된다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient
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
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _patient(session: Session, name: str = "환자") -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _linked_caregiver(session: Session, patient: Patient, name: str = "보호자") -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=patient.id))
    session.commit()
    return cg


def _headers(caregiver_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(caregiver_id, 'caregiver')}"}


def test_defaults_to_enabled_on_new_link(client: TestClient, session: Session):
    pt = _patient(session)
    cg = _linked_caregiver(session, pt)

    r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
    assert r.status_code == 200
    assert r.json()[0]["notifications_enabled"] is True


def test_disable_then_reflected_in_patient_list(client: TestClient, session: Session):
    pt = _patient(session)
    cg = _linked_caregiver(session, pt)

    r = client.patch(
        f"/monitoring/caregivers/{cg.id}/patients/{pt.id}/notifications",
        json={"enabled": False},
        headers=_headers(cg.id),
    )
    assert r.status_code == 200
    assert r.json()["notifications_enabled"] is False

    listed = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
    assert listed.json()[0]["notifications_enabled"] is False

    session.refresh(session.exec(select(CaregiverPatient)).one())
    link = session.exec(select(CaregiverPatient)).one()
    assert link.notifications_enabled is False


def test_forbidden_for_other_caregiver(client: TestClient, session: Session):
    pt = _patient(session)
    cg = _linked_caregiver(session, pt)
    other = Caregiver(hashed_password="x")
    other.name = "무관 보호자"
    session.add(other)
    session.commit()
    session.refresh(other)

    r = client.patch(
        f"/monitoring/caregivers/{cg.id}/patients/{pt.id}/notifications",
        json={"enabled": False},
        headers=_headers(other.id),
    )
    assert r.status_code == 403


def test_404_when_not_linked(client: TestClient, session: Session):
    pt = _patient(session)
    cg = Caregiver(hashed_password="x")
    cg.name = "연결 안 된 보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)

    r = client.patch(
        f"/monitoring/caregivers/{cg.id}/patients/{pt.id}/notifications",
        json={"enabled": False},
        headers=_headers(cg.id),
    )
    assert r.status_code == 404


def test_404_when_link_revoked(client: TestClient, session: Session):
    pt = _patient(session)
    cg = _linked_caregiver(session, pt)
    link = session.exec(select(CaregiverPatient)).one()
    link.status = "revoked"
    session.add(link)
    session.commit()

    r = client.patch(
        f"/monitoring/caregivers/{cg.id}/patients/{pt.id}/notifications",
        json={"enabled": False},
        headers=_headers(cg.id),
    )
    assert r.status_code == 404
