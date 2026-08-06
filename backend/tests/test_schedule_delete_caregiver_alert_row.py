"""
test_schedule_delete_caregiver_alert_row.py — DELETE /monitoring/schedules/{id}가
schedule_caregiver_alerts 행까지 정리하는지 검증 (2026-07-24 추가, PR#93 리뷰 반영)

schedule_caregiver_alerts.schedule_id도 medication_schedules.id를 참조하는 FK인데
delete_schedule()이 이 테이블은 정리하지 않고 있었다 — MedicationRecord/NotificationLog/
레거시 MedicationLog와 같은 이유로, 알림 대상을 명시적으로 고른(또는 새 기본값으로
전원이 깔린) 일정을 지우면 FK 위반이 나거나 고아 행이 남을 수 있었다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, MedicationSchedule, Patient, ScheduleCaregiverAlert
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


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def test_delete_schedule_removes_caregiver_alert_rows(client: TestClient, session: Session):
    pt = Patient(hashed_password="x")
    session.add(pt)
    session.commit()
    session.refresh(pt)

    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()

    sched = MedicationSchedule(patient_id=pt.id, drug_name="암로디핀정5mg", time_slot="09:00", caregiver_alert=True)
    session.add(sched)
    session.commit()
    session.refresh(sched)

    session.add(ScheduleCaregiverAlert(schedule_id=sched.id, caregiver_id=cg.id))
    session.commit()

    r = client.delete(f"/monitoring/schedules/{sched.id}", headers=_headers(pt.id))
    assert r.status_code == 200
    assert session.get(MedicationSchedule, sched.id) is None
    assert session.exec(
        select(ScheduleCaregiverAlert).where(ScheduleCaregiverAlert.schedule_id == sched.id)
    ).all() == []
