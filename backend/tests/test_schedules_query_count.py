"""GET /monitoring/schedules — N+1 쿼리 회귀 테스트 (2026-08-04).

스케줄이 N개여도 effective_alert_caregiver_ids를 스케줄마다 반복 호출하지 않고,
bulk_effective_alert_caregiver_ids로 환자 단위 한 번만 계산하는지 실측으로 검증한다.
값 자체(alert_caregiver_ids)의 정확성도 함께 확인해 bulk-select로 바꾸면서 결과가
달라지지 않았는지 검증한다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, MedicationSchedule, Patient, ScheduleCaregiverAlert
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture(name="engine")
def engine_fixture():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@pytest.fixture(name="session")
def session_fixture(engine):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def _make_patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_caregiver(session: Session, name: str) -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _build_schedules(session: Session, patient: Patient, n: int, linked_caregivers: list[Caregiver]) -> list[MedicationSchedule]:
    """스케줄 n개를 만든다. 실제 사용 패턴과 유사하게 섞어서 구성:
    - 1/3은 caregiver_alert=False (kill switch, 항상 빈 목록)
    - 1/3은 ScheduleCaregiverAlert로 명시적 선택(첫 번째 caregiver만)
    - 나머지는 명시적 선택 없음 → linked_caregiver_ids 폴백
    """
    schedules = []
    for i in range(n):
        if i % 3 == 0:
            sched = MedicationSchedule(patient_id=patient.id, drug_name=f"약{i}", time_slot="08:00", caregiver_alert=False)
            session.add(sched)
            session.commit()
            session.refresh(sched)
        elif i % 3 == 1:
            sched = MedicationSchedule(patient_id=patient.id, drug_name=f"약{i}", time_slot="08:00")
            session.add(sched)
            session.commit()
            session.refresh(sched)
            session.add(ScheduleCaregiverAlert(schedule_id=sched.id, caregiver_id=linked_caregivers[0].id))
            session.commit()
        else:
            sched = MedicationSchedule(patient_id=patient.id, drug_name=f"약{i}", time_slot="08:00")
            session.add(sched)
            session.commit()
            session.refresh(sched)
        schedules.append(sched)
    return schedules


def _count_select_queries(engine, fn):
    count = 0

    def _listener(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        if statement.strip().upper().startswith("SELECT"):
            count += 1

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _listener)
    return result, count


class TestQueryCountDoesNotScaleWithScheduleCount:
    @pytest.mark.parametrize("n", [3, 10, 20])
    def test_fixed_query_count_regardless_of_schedule_count(
        self, client: TestClient, session: Session, engine, n: int
    ):
        pt = _make_patient(session)
        cg1 = _make_caregiver(session, "보호자1")
        cg2 = _make_caregiver(session, "보호자2")
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=cg2.id, patient_id=pt.id))
        session.commit()
        _build_schedules(session, pt, n, [cg1, cg2])

        response, query_count = _count_select_queries(
            engine,
            lambda: client.get("/monitoring/schedules", params={"patient_id": pt.id, "active_only": False}, headers=_headers(pt.id)),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == n

        # bulk-select 패턴 적용 후 예상 쿼리 수: 인증 조회(1) + schedules(1) +
        # ScheduleCaregiverAlert bulk(1) + linked_caregiver_ids(1, 환자 1명이라 한 번만) = 4.
        # 스케줄 수(n)와 무관하게 고정.
        assert query_count == 4, f"n={n}일 때 쿼리 수가 {query_count}회 — 스케줄 수와 무관하게 4회여야 함"

    def test_query_count_identical_for_3_and_20_schedules(self, session: Session, engine):
        """가장 직접적인 회귀 신호 — 스케줄 3건과 20건에서 쿼리 수가 완전히 같아야 N+1이 없다는 뜻."""
        counts = {}
        for n in (3, 20):
            pt = _make_patient(session)
            cg1 = _make_caregiver(session, f"보호자1-{n}")
            session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
            session.commit()
            _build_schedules(session, pt, n, [cg1])

            app.dependency_overrides[get_session] = lambda: session
            client = TestClient(app, raise_server_exceptions=True)
            _, query_count = _count_select_queries(
                engine,
                lambda: client.get("/monitoring/schedules", params={"patient_id": pt.id, "active_only": False}, headers=_headers(pt.id)),
            )
            counts[n] = query_count
            app.dependency_overrides.clear()

        assert counts[3] == counts[20], f"쿼리 수가 스케줄 수에 비례해 늘어남: {counts}"


class TestBulkResultsMatchOriginalPerScheduleBehavior:
    """bulk-select로 바꾸면서 값 자체가 달라지지 않았는지 확인 — 순수 성능 개선이어야 한다."""

    def test_caregiver_alert_false_is_always_empty(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg1 = _make_caregiver(session, "보호자1")
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.commit()
        session.add(MedicationSchedule(patient_id=pt.id, drug_name="약", time_slot="08:00", caregiver_alert=False))
        session.commit()

        r = client.get("/monitoring/schedules", params={"patient_id": pt.id, "active_only": False}, headers=_headers(pt.id))
        assert r.json()[0]["alert_caregiver_ids"] == []

    def test_explicit_selection_is_used_as_is(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg1 = _make_caregiver(session, "보호자1")
        cg2 = _make_caregiver(session, "보호자2")
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=cg2.id, patient_id=pt.id))
        session.commit()
        sched = MedicationSchedule(patient_id=pt.id, drug_name="약", time_slot="08:00")
        session.add(sched)
        session.commit()
        session.refresh(sched)
        session.add(ScheduleCaregiverAlert(schedule_id=sched.id, caregiver_id=cg1.id))
        session.commit()

        r = client.get("/monitoring/schedules", params={"patient_id": pt.id, "active_only": False}, headers=_headers(pt.id))
        assert r.json()[0]["alert_caregiver_ids"] == [cg1.id]

    def test_no_explicit_selection_falls_back_to_all_linked(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg1 = _make_caregiver(session, "보호자1")
        cg2 = _make_caregiver(session, "보호자2")
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=cg2.id, patient_id=pt.id))
        session.commit()
        session.add(MedicationSchedule(patient_id=pt.id, drug_name="약", time_slot="08:00"))
        session.commit()

        r = client.get("/monitoring/schedules", params={"patient_id": pt.id, "active_only": False}, headers=_headers(pt.id))
        assert set(r.json()[0]["alert_caregiver_ids"]) == {cg1.id, cg2.id}

    def test_no_schedules_returns_empty_list(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        r = client.get("/monitoring/schedules", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert r.status_code == 200
        assert r.json() == []

    def test_revoked_caregiver_excluded_from_fallback(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        cg1 = _make_caregiver(session, "보호자1")
        revoked = _make_caregiver(session, "해제된보호자")
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=revoked.id, patient_id=pt.id, status="revoked"))
        session.commit()
        session.add(MedicationSchedule(patient_id=pt.id, drug_name="약", time_slot="08:00"))
        session.commit()

        r = client.get("/monitoring/schedules", params={"patient_id": pt.id, "active_only": False}, headers=_headers(pt.id))
        assert r.json()[0]["alert_caregiver_ids"] == [cg1.id]