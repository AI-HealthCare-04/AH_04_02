"""GET /monitoring/patients/{patient_id}/notifications ? ???(? ???) ???
(2026-07-23 ??).

?? ??/?? ??? ?? NotificationLog? ??? ????, ??? ?? ? ???
???(??? ??? ??) ? ? ?????? ? ?? ??? ??? ????.
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
    pt.name = "??"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def test_lists_notifications_with_drug_name_newest_first(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="?????5mg", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    # [2026-07-31 ????] ?? ??(2026-07-01 ?)? ????? ???, ?? ??
    # ???(days=30)? "??" ???? ?? ???? ???? ? ?? ? ??? ???
    # ??? ???? time-bomb???(??? CI?? ???) ? ??
    # test_excludes_notifications_outside_days_window?? datetime.now() ?? ??
    # ????? ???, ?? ??? ???? ?? ??? ?? ???? ??.
    older_fired_at = datetime.now() - timedelta(days=20)
    newer_fired_at = datetime.now() - timedelta(days=5)
    older = NotificationLog(
        schedule_id=sched.id, patient_id=pt.id, due_date=older_fired_at.date().isoformat(), time_slot="08:00",
        kind="reminder", status="sent", fired_at=older_fired_at,
    )
    newer = NotificationLog(
        schedule_id=sched.id, patient_id=pt.id, due_date=newer_fired_at.date().isoformat(), time_slot="08:00",
        kind="missed", status="sent", fired_at=newer_fired_at,
    )
    session.add(older)
    session.add(newer)
    session.commit()

    r = client.get(f"/monitoring/patients/{pt.id}/notifications", headers=_headers(pt.id))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["kind"] == "missed"  # ???
    assert body[0]["drug_name"] == "?????5mg"
    assert body[1]["kind"] == "reminder"


def test_excludes_notifications_outside_days_window(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="?A", time_slot="08:00")
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
    outsider.name = "???"
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
    cg.name = "???"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()

    sched = MedicationSchedule(patient_id=pt.id, drug_name="?B", time_slot="08:00")
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


# ?? POST /monitoring/patients/{patient_id}/notifications/acknowledge [2026-07-30 ??] ??
# NavBar ? ??? ??? "???? ? ?? ??? ? ??" ?? ??? ? ????
# ???, acknowledged_at? ??? ???? ?? ?? ???? ?????? ????.

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
    sched = MedicationSchedule(patient_id=pt.id, drug_name="?C", time_slot="08:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)
    _make_log(session, pt.id, sched.id)

    r = client.get(f"/monitoring/patients/{pt.id}/notifications", headers=_headers(pt.id))
    assert r.json()[0]["acknowledged_at"] is None


def test_acknowledge_marks_all_unread_logs(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched1 = MedicationSchedule(patient_id=pt.id, drug_name="?D-1", time_slot="08:00")
    sched2 = MedicationSchedule(patient_id=pt.id, drug_name="?D-2", time_slot="20:00")
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
    # ?? ??? ??? acknowledged_at? ? ???? ???? ?????? ??? ??
    # ???(?? ??? where acknowledged_at is null? ???? ?? ???? ???),
    # ? ?? ??? ??? ? ? ??? ?? ????.
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="?E", time_slot="08:00")
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
    outsider.name = "???"
    session.add(outsider)
    session.commit()
    session.refresh(outsider)

    r = client.post(
        f"/monitoring/patients/{pt.id}/notifications/acknowledge",
        headers={"Authorization": f"Bearer {create_access_token(outsider.id, 'caregiver')}"},
    )
    assert r.status_code == 403


def test_delete_notification_hides_only_requested_log(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="test-drug", time_slot="08:00")
    other_sched = MedicationSchedule(patient_id=pt.id, drug_name="other-drug", time_slot="20:00")
    session.add(sched)
    session.add(other_sched)
    session.commit()
    session.refresh(sched)
    session.refresh(other_sched)
    target = _make_log(session, pt.id, sched.id)
    remaining = _make_log(session, pt.id, other_sched.id)

    response = client.delete(
        f"/monitoring/patients/{pt.id}/notifications/{target.id}", headers=_headers(pt.id)
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": target.id}
    deleted = session.get(NotificationLog, target.id)
    assert deleted is not None
    assert deleted.deleted_at is not None
    assert session.get(NotificationLog, remaining.id).deleted_at is None

    inbox = client.get(
        f"/monitoring/patients/{pt.id}/notifications", headers=_headers(pt.id)
    )
    assert inbox.status_code == 200
    assert [item["id"] for item in inbox.json()] == [remaining.id]


def test_clear_notifications_preserves_unacknowledged_logs(client: TestClient, session: Session):
    pt = _make_patient(session)
    sched = MedicationSchedule(patient_id=pt.id, drug_name="test-drug", time_slot="08:00")
    other_sched = MedicationSchedule(patient_id=pt.id, drug_name="other-drug", time_slot="20:00")
    session.add(sched)
    session.add(other_sched)
    session.commit()
    session.refresh(sched)
    session.refresh(other_sched)
    acknowledged = _make_log(session, pt.id, sched.id)
    unread = _make_log(session, pt.id, other_sched.id)
    acknowledged.acknowledged_at = datetime.now()
    session.add(acknowledged)
    session.commit()

    response = client.delete(
        f"/monitoring/patients/{pt.id}/notifications", headers=_headers(pt.id)
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    assert session.get(NotificationLog, acknowledged.id).deleted_at is not None
    assert session.get(NotificationLog, unread.id).deleted_at is None


def test_bulk_delete_notifications_removes_only_selected_owned_logs(client: TestClient, session: Session):
    pt = _make_patient(session)
    other_pt = _make_patient(session)
    schedules = []
    for patient, name in ((pt, "first"), (pt, "second"), (other_pt, "other")):
        schedule = MedicationSchedule(patient_id=patient.id, drug_name=name, time_slot="08:00")
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
        schedules.append(schedule)
    first = _make_log(session, pt.id, schedules[0].id)
    second = _make_log(session, pt.id, schedules[1].id)
    other = _make_log(session, other_pt.id, schedules[2].id)

    response = client.post(
        f"/monitoring/patients/{pt.id}/notifications/delete",
        headers=_headers(pt.id),
        json={"notification_ids": [first.id, other.id, first.id]},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    assert session.get(NotificationLog, first.id).deleted_at is not None
    assert session.get(NotificationLog, second.id).deleted_at is None
    assert session.get(NotificationLog, other.id).deleted_at is None
