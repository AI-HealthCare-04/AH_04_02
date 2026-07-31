"""GET /monitoring/patients/{patient_id}/notifications — 알림함(웹 인박스) 테스트
(2026-07-23 신규).

복약 알림/놓침 감지는 이미 NotificationLog에 쌓이고 있었지만, 웹에서 모아 볼 화면이
없었다(푸시만 전제한 설계) — 이 엔드포인트가 그 원본 로그를 그대로 노출한다.
"""
from datetime import date, datetime, timedelta

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, MedicationSchedule, NotificationLog, Patient
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


# ── POST /monitoring/patients/{patient_id}/notifications/acknowledge [2026-07-30 신규] ──
# NavBar 종 아이콘 배지가 "알림함에 한 번도 표시된 적 없는" 복약 알림만 안 읽음으로
# 세도록, acknowledged_at을 응답에 노출하고 일괄 표시 처리하는 엔드포인트를 검증한다.

def _make_log(session: Session, patient_id: int, sched_id: int) -> NotificationLog:
    log = NotificationLog(
        schedule_id=sched_id, patient_id=patient_id, due_date=date.today().isoformat(),
        time_slot="08:00", kind="reminder", status="sent",
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def test_new_log_is_unacknowledged_by_default(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="약C", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)
    _make_log(session, pt.id, sched.id)

    r = client.get(f"/monitoring/patients/{pt.id}/notifications", headers=_headers(pt.id))
    assert r.json()[0]["acknowledged_at"] is None


def test_acknowledge_marks_all_unread_logs(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched1 = MedicationSchedule(patient_id=pt.id, drug_name="약D-1", time_slot="08:00")
    sched2 = MedicationSchedule(patient_id=pt.id, drug_name="약D-2", time_slot="20:00")
    session.add(sched1)
    session.add(sched2)
    session.commit()
    session.refresh(sched1)
    session.refresh(sched2)
    log1 = _make_log(session, pt.id, sched1.id)
    log2 = _make_log(session, pt.id, sched2.id)

    r = client.post(f"/monitoring/patients/{pt.id}/notifications/acknowledge", headers=_headers(pt.id))
    assert r.status_code == 200
    assert r.json()["acknowledged"] == 2

    session.refresh(log1)
    session.refresh(log2)
    assert log1.acknowledged_at is not None
    assert log2.acknowledged_at is not None


def test_acknowledge_does_not_touch_already_acknowledged_logs(client: TestClient, session: Session):
    # 이미 표시된 로그의 acknowledged_at을 새 시각으로 덮어쓰지 않는지까지는 별도로 보진
    # 않지만(현재 구현은 where acknowledged_at is null만 대상으로 삼아 자동으로 보장됨),
    # 두 번째 호출이 이번엔 셀 게 없다는 것만 확인한다.
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="약E", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)
    _make_log(session, pt.id, sched.id)

    client.post(f"/monitoring/patients/{pt.id}/notifications/acknowledge", headers=_headers(pt.id))
    r = client.post(f"/monitoring/patients/{pt.id}/notifications/acknowledge", headers=_headers(pt.id))
    assert r.json()["acknowledged"] == 0


def test_acknowledge_forbidden_for_unrelated_caregiver(client: TestClient, session: Session):
    pt = _make_patient(session)
    outsider = Caregiver(hashed_password="x")
    outsider.name = "무관자"
    session.add(outsider)
    session.commit()
    session.refresh(outsider)

    r = client.post(
        f"/monitoring/patients/{pt.id}/notifications/acknowledge",
        headers={"Authorization": f"Bearer {create_access_token(outsider.id, 'caregiver')}"},
    )
    assert r.status_code == 403
