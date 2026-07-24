"""POST/PATCH/GET /monitoring/schedules — alert_caregiver_ids (2026-07-24 신규, 팀 요청).

"보호자에게도 알림" 토글이 실제로는 "가장 먼저 연결된 caregiver 1명"에게만 갔다(REQ 없음,
core/scheduler.py._recipients의 임의의 단순화) — 2번째·3번째 보호자·지원인력에게는 애초에
안 갔고, 화면 라벨도 실제 수신자를 보여주지 못했다. 이제 일정마다 알림 받을 caregiver를
id 목록으로 직접 고를 수 있고, 명시적으로 고른 적 없으면 API 응답도 연결된 caregiver
전원을 그대로 채워서 돌려준다(실제 발송 대상과 항상 일치 — core/schedule_alerts.py 참고).
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient, ScheduleCaregiverAlert
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


def _patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _linked_caregiver(session: Session, patient: Patient, name: str) -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=patient.id))
    session.commit()
    return cg


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def test_create_without_alert_caregiver_ids_defaults_to_all_linked(client: TestClient, session: Session):
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")
    cg2 = _linked_caregiver(session, pt, "보호자2")

    r = client.post(
        "/monitoring/schedules",
        json={"patient_id": pt.id, "drug_name": "테스트약", "time_slot": "08:00"},
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    body = r.json()
    assert set(body["alert_caregiver_ids"]) == {cg1.id, cg2.id}


def test_create_with_explicit_alert_caregiver_ids(client: TestClient, session: Session):
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")
    _linked_caregiver(session, pt, "보호자2")

    r = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "alert_caregiver_ids": [cg1.id],
        },
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == [cg1.id]


def test_create_with_empty_alert_caregiver_ids_alone_still_falls_back_to_all(client: TestClient, session: Session):
    """alert_caregiver_ids만 빈 배열로 보내고 caregiver_alert는 건드리지 않으면(기본값 True),
    "골랐는데 0명"인지 "아직 안 골랐다"인지 서버가 구분할 수 없으므로 안전한 쪽(연결된
    전원)으로 폴백한다 — "명시적으로 아무도 없음"을 표현하려면 caregiver_alert=False를
    같이 보내야 한다(Schedule.tsx가 실제로 그렇게 한다, 아래 테스트 참고)."""
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")

    r = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "alert_caregiver_ids": [],
        },
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == [cg1.id]


def test_caregiver_alert_false_with_empty_selection_means_no_one(client: TestClient, session: Session):
    """Schedule.tsx는 체크박스를 모두 해제하면 caregiver_alert도 함께 False로 보낸다
    (frontend/src/pages/Schedule.tsx의 save() 참고) — 이 조합이라야 확실하게 "아무에게도
    안 감"이 된다."""
    pt = _patient(session)
    _linked_caregiver(session, pt, "보호자1")

    r = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "caregiver_alert": False,
            "alert_caregiver_ids": [],
        },
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == []


def test_caregiver_alert_false_overrides_explicit_selection(client: TestClient, session: Session):
    """caregiver_alert=False가 kill switch — alert_caregiver_ids를 같이 보내도 무시된다."""
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")

    r = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "caregiver_alert": False,
            "alert_caregiver_ids": [cg1.id],
        },
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == []


def test_unlinked_caregiver_id_is_silently_filtered_out(client: TestClient, session: Session):
    """환자와 연결되지 않은(또는 이미 해제된) caregiver_id를 끼워 넣어도 저장되지 않는다."""
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")
    outsider = Caregiver(hashed_password="x")
    outsider.name = "무관자"
    session.add(outsider)
    session.commit()
    session.refresh(outsider)

    r = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "alert_caregiver_ids": [cg1.id, outsider.id],
        },
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == [cg1.id]


def test_update_replaces_previous_selection(client: TestClient, session: Session):
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")
    cg2 = _linked_caregiver(session, pt, "보호자2")

    created = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "alert_caregiver_ids": [cg1.id],
        },
        headers=_headers(pt.id),
    ).json()

    r = client.patch(
        f"/monitoring/schedules/{created['id']}",
        json={"alert_caregiver_ids": [cg2.id]},
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == [cg2.id]

    # DB에도 cg1 행이 남아있지 않아야 한다(교체, 누적 아님).
    rows = session.exec(
        select(ScheduleCaregiverAlert).where(ScheduleCaregiverAlert.schedule_id == created["id"])
    ).all()
    assert [row.caregiver_id for row in rows] == [cg2.id]


def test_update_without_alert_caregiver_ids_leaves_selection_untouched(client: TestClient, session: Session):
    """alert_caregiver_ids 필드 자체를 안 보내면(다른 필드만 수정) 기존 선택을 그대로 둔다."""
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")

    created = client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "alert_caregiver_ids": [cg1.id],
        },
        headers=_headers(pt.id),
    ).json()

    r = client.patch(
        f"/monitoring/schedules/{created['id']}",
        json={"memo": "메모만 수정"},
        headers=_headers(pt.id),
    )

    assert r.status_code == 200
    assert r.json()["alert_caregiver_ids"] == [cg1.id]


def test_list_schedules_includes_alert_caregiver_ids(client: TestClient, session: Session):
    pt = _patient(session)
    cg1 = _linked_caregiver(session, pt, "보호자1")
    client.post(
        "/monitoring/schedules",
        json={
            "patient_id": pt.id,
            "drug_name": "테스트약",
            "time_slot": "08:00",
            "alert_caregiver_ids": [cg1.id],
        },
        headers=_headers(pt.id),
    )

    r = client.get("/monitoring/schedules", params={"patient_id": pt.id}, headers=_headers(pt.id))

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["alert_caregiver_ids"] == [cg1.id]
