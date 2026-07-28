"""POST /trust/relations/{trust_id}/dismiss-alert — REQ-007a 30일 억제 테스트.

시나리오:
1. dismiss 호출 → caregiver_alert_dismissed_at이 DB에 저장됨
2. dismiss 후 _should_alert_now(patient)가 False를 반환함 (30일 이내)
"""
from datetime import datetime, timedelta

import pytest
from conftest import make_test_engine
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient
from routers.care_router import _should_alert_now
from sqlmodel import Session

URL = "/trust/relations/{}/dismiss-alert"


@pytest.fixture(name="session")
def session_fixture():
    engine = make_test_engine()
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _setup(session: Session) -> tuple[Caregiver, Patient, CaregiverPatient]:
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(cg)
    session.refresh(pt)
    link = CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id, status="active")
    session.add(link)
    session.commit()
    session.refresh(link)
    return cg, pt, link


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


def test_dismiss_stores_dismissed_at(client: TestClient, session: Session):
    """dismiss 호출 시 patient.caregiver_alert_dismissed_at이 DB에 저장된다."""
    cg, pt, link = _setup(session)
    assert pt.caregiver_alert_dismissed_at is None  # 초기값 확인

    before = datetime.now()
    r = client.post(
        URL.format(link.id),
        headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
    )
    after = datetime.now()

    assert r.status_code == 200, r.text
    body = r.json()
    assert "caregiver_alert_dismissed_at" in body
    assert "next_alert_at" in body

    # DB에서 직접 확인
    session.refresh(pt)
    assert pt.caregiver_alert_dismissed_at is not None
    dismissed = pt.caregiver_alert_dismissed_at
    assert before <= dismissed <= after

    # next_alert_at = dismissed_at + 30일
    next_alert = datetime.fromisoformat(body["next_alert_at"])
    assert abs((next_alert - dismissed).days - 30) <= 1


def test_dismiss_suppresses_alert_for_30_days(client: TestClient, session: Session):
    """dismiss 직후 _should_alert_now()가 False를 반환한다 (30일 억제)."""
    cg, pt, link = _setup(session)

    # dismiss 전: dismissed_at=None → should_alert=True
    assert _should_alert_now(pt) is True

    r = client.post(
        URL.format(link.id),
        headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
    )
    assert r.status_code == 200

    session.refresh(pt)
    # dismiss 직후: should_alert=False (30일 이내)
    assert _should_alert_now(pt) is False

    # 29일 후에도 여전히 False
    pt.caregiver_alert_dismissed_at = datetime.now() - timedelta(days=29)
    assert _should_alert_now(pt) is False

    # 30일 초과 시 다시 True
    pt.caregiver_alert_dismissed_at = datetime.now() - timedelta(days=31)
    assert _should_alert_now(pt) is True
