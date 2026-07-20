"""
monitoring_router.py — /monitoring/today, /monitoring/logs의 "missed" read-side 병합
테스트 (2026-07-19 신규, REQ-037 Phase1, 담당: 김영혜)

core/scheduler.py가 놓침을 감지하면 MedicationLog가 아니라 NotificationLog(kind="missed")에
기록한다 — 레거시 MedicationLog 스키마를 안 건드리고, 이 두 엔드포인트가 조회 시점에
NotificationLog를 함께 참고해 "missed" 상태를 합성해 보여주는지 검증한다.
"""
from datetime import date, datetime, timedelta

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import MedicationLog, MedicationSchedule, NotificationLog, Patient
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


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


class TestTodayMissedMerge:
    def test_no_log_no_notification_is_pending(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        session.add(MedicationSchedule(patient_id=pt.id, drug_name="약A", time_slot="08:00"))
        session.commit()

        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.status_code == 200
        assert r.json()[0]["status"] == "pending"

    def test_missed_notification_without_log_reports_missed(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약B", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        today_str = date.today().isoformat()
        session.add(
            NotificationLog(
                schedule_id=sched.id, patient_id=pt.id, due_date=today_str,
                time_slot="08:00", kind="missed", status="sent",
            )
        )
        session.commit()

        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json()[0]["status"] == "missed"

    def test_real_log_takes_priority_over_missed_notification(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약C", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        today_str = date.today().isoformat()
        session.add(
            NotificationLog(
                schedule_id=sched.id, patient_id=pt.id, due_date=today_str,
                time_slot="08:00", kind="missed", status="sent",
            )
        )
        session.add(MedicationLog(schedule_id=sched.id, status="taken"))
        session.commit()

        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json()[0]["status"] == "taken"

    def test_reminder_kind_notification_does_not_count_as_missed(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약D", time_slot="08:00")
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

        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json()[0]["status"] == "pending"


class TestLogsMissedMerge:
    def test_missed_entry_appears_with_synthetic_id(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약E", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        notif = NotificationLog(
            schedule_id=sched.id, patient_id=pt.id, due_date=date.today().isoformat(),
            time_slot="08:00", kind="missed", status="sent",
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

        r = client.get("/monitoring/logs", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) == 1
        assert entries[0]["id"] == f"missed:{notif.id}"
        assert entries[0]["status"] == "missed"
        assert entries[0]["confirmed_by_type"] == "system"

    def test_missed_entry_suppressed_when_real_log_exists_same_day(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약F", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        session.add(
            NotificationLog(
                schedule_id=sched.id, patient_id=pt.id, due_date=date.today().isoformat(),
                time_slot="08:00", kind="missed", status="sent",
            )
        )
        session.add(MedicationLog(schedule_id=sched.id, status="skipped"))
        session.commit()

        r = client.get("/monitoring/logs", params={"patient_id": pt.id}, headers=_headers(pt.id))
        entries = r.json()
        assert len(entries) == 1
        assert entries[0]["status"] == "skipped"

    def test_old_missed_notification_outside_window_excluded(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약G", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        notif = NotificationLog(
            schedule_id=sched.id, patient_id=pt.id, due_date="2020-01-01",
            time_slot="08:00", kind="missed", status="sent",
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)
        notif.fired_at = datetime.now() - timedelta(days=999)
        session.add(notif)
        session.commit()

        r = client.get("/monitoring/logs", params={"patient_id": pt.id, "days": 30}, headers=_headers(pt.id))
        assert r.json() == []
