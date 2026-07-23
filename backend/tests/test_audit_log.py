"""audit_logs — 복약 일정·환자 정보 변경 이력 최소 버전 테스트 (2026-07-23 신규).

"어제 8시였던 복약 시간이 오늘 9시로 바뀌었는데 왜 바뀌었는지" 환자가 확인할 방법이
있어야 한다는 요구로 PATCH /monitoring/patients/{id}, PATCH /monitoring/schedules/{id}에
기록을 남기게 했다. name/phone은 암호화 PII라 값 대신 "***"만 남긴다.
"""
import json

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import AuditLog, CaregiverPatient, MedicationSchedule, Patient
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


def _make_patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def test_schedule_time_change_is_logged(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="약A", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    r = client.patch(
        f"/monitoring/schedules/{sched.id}", json={"time_slot": "09:00"}, headers=_headers(pt.id)
    )
    assert r.status_code == 200

    log = session.exec(
        select(AuditLog)
        .where(AuditLog.table_name == "medication_schedules")
        .where(AuditLog.record_id == sched.id)
    ).first()
    assert log is not None
    assert log.actor_role == "patient"
    assert log.actor_id == pt.id
    assert json.loads(log.before) == {"time_slot": "08:00"}
    assert json.loads(log.after) == {"time_slot": "09:00"}


def test_no_op_update_does_not_log(client: TestClient, session: Session):
    """같은 값으로 덮어쓰면(실제 변경이 없으면) 로그를 남기지 않는다."""
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="약B", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    r = client.patch(
        f"/monitoring/schedules/{sched.id}", json={"time_slot": "08:00"}, headers=_headers(pt.id)
    )
    assert r.status_code == 200

    logs = session.exec(
        select(AuditLog).where(AuditLog.table_name == "medication_schedules")
    ).all()
    assert logs == []


def test_patient_name_change_redacts_value(client: TestClient, session: Session):
    """name은 암호화 PII라 실제 값 대신 '***'만 남긴다."""
    pt = _make_patient(session)

    r = client.patch(f"/monitoring/patients/{pt.id}", json={"name": "새이름"}, headers=_headers(pt.id))
    assert r.status_code == 200

    log = session.exec(
        select(AuditLog).where(AuditLog.table_name == "patients").where(AuditLog.record_id == pt.id)
    ).first()
    assert log is not None
    assert log.before is not None
    assert log.after is not None
    assert json.loads(log.before) == {"name": "***"}
    assert json.loads(log.after) == {"name": "***"}
    # 원래 이름("환자")도 새 이름("새이름")도 로그에 그대로 남으면 안 된다
    assert "환자" not in log.before
    assert "새이름" not in log.after


def test_caregiver_editing_schedule_records_caregiver_as_actor(client: TestClient, session: Session):
    from models import Caregiver

    pt = _make_patient(session)
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()

    sched = MedicationSchedule(patient_id=pt.id, drug_name="약C", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    r = client.patch(
        f"/monitoring/schedules/{sched.id}",
        json={"time_slot": "09:00"},
        headers={"Authorization": f"Bearer {create_access_token(cg.id, 'caregiver')}"},
    )
    assert r.status_code == 200

    log = session.exec(
        select(AuditLog).where(AuditLog.table_name == "medication_schedules")
    ).first()
    assert log is not None
    assert log.actor_role == "caregiver"
    assert log.actor_id == cg.id
