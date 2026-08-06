"""
monitoring_router.py — /monitoring/today, /monitoring/logs의 "missed" read-side 병합
테스트 (2026-07-19 신규, REQ-037 Phase1, 담당: 김영혜)

[2026-07-20 REQ-037 Phase2] 체크인 기록을 MedicationRecord로 일원화했다 — 실제 체크는
MedicationRecord(status taken/skipped, taken_at)로 시뮬레이션한다.
core/scheduler.py가 놓침을 감지하면 MedicationRecord가 아니라 NotificationLog(kind="missed")에
기록한다 — 그 스키마를 안 건드리고, 이 두 엔드포인트가 조회 시점에 NotificationLog를 함께
참고해 "missed" 상태를 합성해 보여주는지 검증한다.
"""
from datetime import date, datetime, timedelta

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import (
    Caregiver,
    CaregiverPatient,
    MedicationLog,
    MedicationRecord,
    MedicationSchedule,
    NotificationLog,
    Patient,
)
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


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def _caregiver_headers(caregiver_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(caregiver_id, 'caregiver')}"}


def _make_linked_caregiver(session: Session, patient: Patient, name: str = "보호자") -> Caregiver:
    cg = Caregiver(relation_type="guardian")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=patient.id))
    session.commit()
    return cg


class TestPatientListTodayStatus:
    """[2026-07-23 추가] GET /monitoring/caregivers/{id}/patients의 today_status —
    환자 관리 테이블에서 여러 환자 중 오늘 누가 약을 놓쳤는지 한눈에 보기 위한 필드."""

    def test_no_active_schedules_is_ok(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg = _make_linked_caregiver(session, pt)

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_caregiver_headers(cg.id))
        assert r.json()[0]["today_status"] == "ok"

    def test_missed_today_reports_missed(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg = _make_linked_caregiver(session, pt)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약A", time_slot="08:00")
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

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_caregiver_headers(cg.id))
        assert r.json()[0]["today_status"] == "missed"

    def test_missed_on_inactive_schedule_is_ok(self, client: TestClient, session: Session):
        """비활성화된 일정의 과거 놓침 기록이 남아있어도, 지금은 안 쓰는 일정이라 오늘
        상태 판정에 영향을 주면 안 된다."""
        pt = _make_patient(session)
        cg = _make_linked_caregiver(session, pt)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약B", time_slot="08:00", active=False)
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

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_caregiver_headers(cg.id))
        assert r.json()[0]["today_status"] == "ok"

    def test_missed_yesterday_does_not_affect_today(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg = _make_linked_caregiver(session, pt)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약C", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        session.add(
            NotificationLog(
                schedule_id=sched.id, patient_id=pt.id, due_date=yesterday_str,
                time_slot="08:00", kind="missed", status="sent",
            )
        )
        session.commit()

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_caregiver_headers(cg.id))
        assert r.json()[0]["today_status"] == "ok"


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
        session.add(
            MedicationRecord(schedule_id=sched.id, status="taken", taken_at=datetime.now())
        )
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
        session.add(
            MedicationRecord(schedule_id=sched.id, status="skipped", taken_at=datetime.now())
        )
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


class TestCheckInWritesMedicationRecord:
    """[2026-07-20 REQ-037 Phase2] 체크인이 MedicationRecord로 기록되고, confirmed_by_*가
    보존되는지 검증한다."""

    def test_check_creates_medication_record_with_self_report(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약H", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)

        r = client.post(
            f"/monitoring/schedules/{sched.id}/check",
            json={"status": "taken"},
            headers=_headers(pt.id),
        )
        assert r.status_code == 200

        from sqlmodel import select as _select

        row = session.exec(
            _select(MedicationRecord).where(MedicationRecord.schedule_id == sched.id)
        ).one()
        assert row.status == "taken"
        assert row.taken_at is not None
        assert row.patient_medication_id is None
        assert row.confirmed_by_type == "patient"
        assert row.confirmed_by_caregiver_id is None
        assert row.verification_method == "self_report"

    def test_recheck_updates_same_row_not_duplicate(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약I", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)

        from sqlmodel import select as _select

        client.post(
            f"/monitoring/schedules/{sched.id}/check", json={"status": "taken"}, headers=_headers(pt.id)
        )
        client.post(
            f"/monitoring/schedules/{sched.id}/check", json={"status": "skipped"}, headers=_headers(pt.id)
        )

        rows = session.exec(
            _select(MedicationRecord).where(MedicationRecord.schedule_id == sched.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].status == "skipped"

    def test_today_reflects_check(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약J", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)

        client.post(
            f"/monitoring/schedules/{sched.id}/check", json={"status": "taken"}, headers=_headers(pt.id)
        )
        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json()[0]["status"] == "taken"

        # 체크 취소하면 다시 pending
        client.delete(f"/monitoring/schedules/{sched.id}/check", headers=_headers(pt.id))
        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json()[0]["status"] == "pending"

    def test_confirmed_by_caregiver_id_comes_from_authenticated_actor_not_payload(
        self, client: TestClient, session: Session
    ):
        """[2026-07-20 보안수정] payload.confirmed_by_caregiver_id를 그대로 믿으면, 이 환자와
        무관한 임의의(존재하기만 하는) caregiver_id를 넣어 그 사람 이름이 확인자로 남는
        신원 사칭이 가능했다 — 실제로는 항상 인증된 actor 자신의 id만 쓰여야 한다."""
        pt = _make_patient(session)
        real_caregiver = _make_linked_caregiver(session, pt, name="진짜보호자")
        unrelated_caregiver = Caregiver(relation_type="guardian")
        unrelated_caregiver.name = "무관한사람"
        session.add(unrelated_caregiver)
        session.commit()
        session.refresh(unrelated_caregiver)

        sched = MedicationSchedule(patient_id=pt.id, drug_name="약K", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)

        r = client.post(
            f"/monitoring/schedules/{sched.id}/check",
            json={"status": "taken", "confirmed_by_caregiver_id": unrelated_caregiver.id},
            headers=_caregiver_headers(real_caregiver.id),
        )
        assert r.status_code == 200

        from sqlmodel import select as _select

        row = session.exec(
            _select(MedicationRecord).where(MedicationRecord.schedule_id == sched.id)
        ).one()
        assert row.confirmed_by_caregiver_id == real_caregiver.id
        assert row.confirmed_by_type == "caregiver"


class TestNonCheckInStatusesFilteredOut:
    """[2026-07-20 REQ-037 Phase2] MedicationRecord.status는 5종
    (scheduled/taken/missed/skipped/duplicate_suspected)이라, /today·/logs는 사용자가 실제로
    체크한 taken/skipped만 노출해야 한다(그 외 상태가 프론트 타입을 깨뜨리면 안 됨)."""

    def test_scheduled_status_not_exposed(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약K", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        # patient_medications 플로우가 만들 수 있는 비체크인 상태들
        session.add(
            MedicationRecord(schedule_id=sched.id, status="scheduled", taken_at=datetime.now())
        )
        session.add(
            MedicationRecord(
                schedule_id=sched.id, status="duplicate_suspected", taken_at=datetime.now()
            )
        )
        session.commit()

        # /today: 체크가 아니므로 pending으로 보여야 한다
        r = client.get("/monitoring/today", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json()[0]["status"] == "pending"

        # /logs: 노출 안 됨
        r = client.get("/monitoring/logs", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.json() == []

    def test_only_taken_skipped_appear_in_logs(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약L", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        now = datetime.now()
        session.add(MedicationRecord(schedule_id=sched.id, status="taken", taken_at=now))
        session.add(MedicationRecord(schedule_id=sched.id, status="scheduled", taken_at=now))
        session.commit()

        r = client.get("/monitoring/logs", params={"patient_id": pt.id}, headers=_headers(pt.id))
        entries = r.json()
        assert len(entries) == 1
        assert entries[0]["status"] == "taken"


class TestScheduleDelete:
    def test_delete_schedule_removes_dependent_logs_first(self, client: TestClient, session: Session):
        """복약 체크/알림 기록이 붙은 일정도 사용자가 삭제하면 실제로 삭제되어야 한다."""
        pt = _make_patient(session)
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약M", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        session.add(MedicationRecord(schedule_id=sched.id, status="taken", taken_at=datetime.now()))
        session.add(MedicationLog(schedule_id=sched.id, status="taken"))
        session.add(
            NotificationLog(
                schedule_id=sched.id,
                patient_id=pt.id,
                due_date=date.today().isoformat(),
                time_slot="08:00",
                kind="reminder",
                status="sent",
            )
        )
        session.commit()

        r = client.delete(f"/monitoring/schedules/{sched.id}", headers=_headers(pt.id))

        assert r.status_code == 200
        assert session.get(MedicationSchedule, sched.id) is None
        assert session.exec(select(MedicationRecord)).all() == []
        assert session.exec(select(MedicationLog)).all() == []
        assert session.exec(select(NotificationLog)).all() == []
