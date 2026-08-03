"""GET /monitoring/caregivers/{caregiver_id}/patients — N+1 쿼리 회귀 테스트 (2026-08-03).

환자 K명을 관리하는 보호자가 이 엔드포인트를 호출할 때, _bulk_patient_diagnoses /
_bulk_patient_medication_and_today_status가 환자별로 따로 쿼리를 날리지 않고 K와
무관하게 고정된 횟수만 실행하는지 실측으로 검증한다. 값 자체(진단명·복약상태·오늘상태)의
정확성도 함께 확인해 bulk-select로 바꾸면서 결과가 달라지지 않았는지 검증한다.
"""
from datetime import date, datetime

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import (
    Caregiver,
    CaregiverPatient,
    MedicalRecord,
    MedicationSchedule,
    NotificationLog,
    OcrResult,
    Patient,
)
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


def _headers(caregiver_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(caregiver_id, 'caregiver')}"}


def _make_caregiver(session: Session) -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _build_patients(session: Session, caregiver: Caregiver, k: int) -> list[Patient]:
    """환자 k명을 만들고, 각각 다음을 섞어서 구성한다(실제 사용 패턴과 유사하게):
    - 활성 일정 1개 + 비활성 일정 1개 (medication_status="active" 유도)
    - 짝수 인덱스 환자만 오늘 놓친 알림(missed) 기록 (today_status="missed" 유도)
    - 진단명 2건(중복 1건 포함, soft-delete/빈 문자열 케이스도 1건씩 섞음)
    """
    today_str = date.today().isoformat()
    patients = []
    for i in range(k):
        pt = Patient(hashed_password="x")
        pt.name = f"환자{i}"
        session.add(pt)
        session.commit()
        session.refresh(pt)
        session.add(CaregiverPatient(caregiver_id=caregiver.id, patient_id=pt.id))

        active_sched = MedicationSchedule(patient_id=pt.id, drug_name=f"약A{i}", time_slot="08:00", active=True)
        inactive_sched = MedicationSchedule(patient_id=pt.id, drug_name=f"약B{i}", time_slot="20:00", active=False)
        session.add(active_sched)
        session.add(inactive_sched)
        session.commit()
        session.refresh(active_sched)

        if i % 2 == 0:
            session.add(
                NotificationLog(
                    schedule_id=active_sched.id, patient_id=pt.id, due_date=today_str,
                    time_slot="08:00", kind="missed", status="sent",
                )
            )

        record = MedicalRecord(patient_id=pt.id, image_path=f"/tmp/{i}.png")
        deleted_record = MedicalRecord(
            patient_id=pt.id, image_path=f"/tmp/{i}-deleted.png", deleted_at=datetime.now()
        )
        session.add(record)
        session.add(deleted_record)
        session.commit()
        session.refresh(record)
        session.refresh(deleted_record)

        session.add(OcrResult(record_id=record.id, drug_name="약A", diagnosis="고혈압"))
        session.add(OcrResult(record_id=record.id, drug_name="약A", diagnosis="고혈압"))  # 중복 — 제거되어야 함
        session.add(OcrResult(record_id=record.id, drug_name="약C", diagnosis=""))  # 빈 문자열 — 제외되어야 함
        session.add(OcrResult(record_id=deleted_record.id, drug_name="약D", diagnosis="당뇨병"))  # soft-delete — 제외되어야 함
        session.commit()

        patients.append(pt)
    session.commit()
    return patients


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


class TestQueryCountDoesNotScaleWithPatientCount:
    @pytest.mark.parametrize("k", [3, 10, 20])
    def test_fixed_query_count_regardless_of_patient_count(
        self, client: TestClient, session: Session, engine, k: int
    ):
        cg = _make_caregiver(session)
        _build_patients(session, cg, k)

        response, query_count = _count_select_queries(
            engine,
            lambda: client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id)),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == k

        # bulk-select 패턴 적용 후 예상 쿼리 수: get_current_caregiver 인증 조회(1) +
        # links(1) + patients(1) + diagnoses(1) + schedules(1) + missed(1, 활성 일정이
        # 있을 때만) = 6. 환자 수(k)와 무관하게 고정.
        assert query_count == 6, f"k={k}일 때 쿼리 수가 {query_count}회 — 환자 수와 무관하게 6회여야 함"

    def test_query_count_identical_for_3_and_20_patients(self, session: Session, engine):
        """가장 직접적인 회귀 신호 — 환자 3명과 20명에서 쿼리 수가 완전히 같아야 N+1이 없다는 뜻."""
        counts = {}
        for k in (3, 20):
            app.dependency_overrides[get_session] = lambda: session
            client = TestClient(app, raise_server_exceptions=True)
            cg = _make_caregiver(session)
            _build_patients(session, cg, k)
            _, query_count = _count_select_queries(
                engine,
                lambda: client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id)),
            )
            counts[k] = query_count
            app.dependency_overrides.clear()

        assert counts[3] == counts[20], f"쿼리 수가 환자 수에 비례해 늘어남: {counts}"


class TestBulkResultsMatchOriginalPerPatientBehavior:
    """bulk-select로 바꾸면서 값 자체가 달라지지 않았는지 확인 — 순수 성능 개선이어야 한다."""

    def test_diagnoses_dedup_and_excludes_soft_deleted_and_empty(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        _build_patients(session, cg, 3)

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
        for p in r.json():
            assert p["diagnoses"] == "고혈압", p  # 중복 제거 + 빈 문자열 제외 + soft-delete 제외

    def test_medication_status_active_when_any_active_schedule(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        _build_patients(session, cg, 3)

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
        for p in r.json():
            assert p["medication_status"] == "active", p

    def test_today_status_alternates_missed_ok_by_index_parity(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        _build_patients(session, cg, 4)

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
        by_name = {p["name"]: p["today_status"] for p in r.json()}
        assert by_name["환자0"] == "missed"
        assert by_name["환자1"] == "ok"
        assert by_name["환자2"] == "missed"
        assert by_name["환자3"] == "ok"

    def test_patient_with_no_schedules_or_records_gets_none_and_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = Patient(hashed_password="x")
        pt.name = "빈환자"
        session.add(pt)
        session.commit()
        session.refresh(pt)
        session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
        session.commit()

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
        body = r.json()
        assert len(body) == 1
        assert body[0]["diagnoses"] is None
        assert body[0]["medication_status"] == "none"
        assert body[0]["today_status"] == "ok"

    def test_patient_with_only_inactive_schedule_is_paused(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = Patient(hashed_password="x")
        pt.name = "중단환자"
        session.add(pt)
        session.commit()
        session.refresh(pt)
        session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
        session.add(MedicationSchedule(patient_id=pt.id, drug_name="약Z", time_slot="08:00", active=False))
        session.commit()

        r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))
        body = r.json()
        assert body[0]["medication_status"] == "paused"
        assert body[0]["today_status"] == "ok"  # 활성 일정이 없으니 놓칠 것도 없음