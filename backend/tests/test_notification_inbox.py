"""GET /monitoring/patients/{patient_id}/notifications — 알림함(웹 인박스) 테스트
(2026-07-23 신규).

복약 알림/놓침 감지는 이미 NotificationLog에 쌓이고 있었지만, 웹에서 모아 볼 화면이
없었다(푸시만 전제한 설계) — 이 엔드포인트가 그 원본 로그를 그대로 노출한다.
"""
from datetime import date, datetime, timedelta

import pytest
from conftest import make_test_engine
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, MedicationSchedule, NotificationLog, Patient
from sqlmodel import Session


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


def _make_patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def test_lists_notifications_with_drug_name_newest_first(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="암로디핀정5mg", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    older = NotificationLog(
        schedule_id=sched.id, patient_id=pt.id, due_date="2026-07-01", time_slot="08:00",
        kind="reminder", status="sent", fired_at=datetime(2026, 7, 1, 8, 0),
    )
    newer = NotificationLog(
        schedule_id=sched.id, patient_id=pt.id, due_date="2026-07-20", time_slot="08:00",
        kind="missed", status="sent", fired_at=datetime(2026, 7, 20, 9, 0),
    )
    session.add(older)
    session.add(newer)
    session.commit()

    r = client.get(f"/monitoring/patients/{pt.id}/notifications", headers=_headers(pt.id))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["kind"] == "missed"  # 최신순
    assert body[0]["drug_name"] == "암로디핀정5mg"
    assert body[1]["kind"] == "reminder"


def test_excludes_notifications_outside_days_window(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="약A", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    old = NotificationLog(
        schedule_id=sched.id, patient_id=pt.id, due_date="2020-01-01", time_slot="08:00",
        kind="reminder", status="sent", fired_at=datetime.now() - timedelta(days=90),
    )
    session.add(old)
    session.commit()

    r = client.get(
        f"/monitoring/patients/{pt.id}/notifications", params={"days": 30}, headers=_headers(pt.id)
    )
    assert r.json() == []


def test_unrelated_caregiver_forbidden(client: TestClient, session: Session):
    pt = _make_patient(session)
    outsider = Caregiver(hashed_password="x")
    outsider.name = "무관자"
    session.add(outsider)
    session.commit()
    session.refresh(outsider)

    r = client.get(
        f"/monitoring/patients/{pt.id}/notifications",
        headers={"Authorization": f"Bearer {create_access_token(outsider.id, 'caregiver')}"},
    )
    assert r.status_code == 403


def test_linked_caregiver_can_view(client: TestClient, session: Session):
    pt = _make_patient(session)
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()

    sched = MedicationSchedule(patient_id=pt.id, drug_name="약B", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)
    session.add(
        NotificationLog(
            schedule_id=sched.id, patient_id=pt.id, due_date=date.today().isoformat(),
            time_slot="08:00", kind="reminder", status="sent",
        )
    )
    session.commit()

    r = client.get(
        f"/monitoring/patients/{pt.id}/notifications",
        headers={"Authorization": f"Bearer {create_access_token(cg.id, 'caregiver')}"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
