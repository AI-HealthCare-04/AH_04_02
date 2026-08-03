"""GET /records — N+1 쿼리 회귀 테스트 (2026-08-03).

환자에게 처방전 기록 N건이 쌓여도, list_records가 기록별로 OcrResult/Caregiver를 따로
조회하지 않고 N과 무관하게 고정된 횟수만 실행하는지 실측으로 검증한다. 값 자체(진단명·
약품명·업로더 이름)의 정확성도 함께 확인해 bulk-select로 바꾸면서 결과가 달라지지
않았는지 검증한다.
"""
from datetime import datetime, timedelta

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, MedicalRecord, OcrResult, Patient
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


def _build_records(session: Session, patient: Patient, n: int) -> list[MedicalRecord]:
    """기록 n건을 만든다. 실제 사용 패턴과 유사하게 섞어서 구성:
    - 절반은 보호자A가 업로드, 절반은 본인 업로드(uploaded_by_caregiver_id=None)
    - 각 기록에 약 2개(진단명 포함)
    - created_at을 다르게 줘서 정렬이 흔들리지 않게 함
    """
    caregiver = _make_caregiver(session, "업로더보호자")
    records = []
    base_time = datetime.now()
    for i in range(n):
        record = MedicalRecord(
            patient_id=patient.id,
            image_path=f"/tmp/{i}.png",
            uploaded_by_caregiver_id=caregiver.id if i % 2 == 0 else None,
            created_at=base_time - timedelta(minutes=i),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        session.add(OcrResult(record_id=record.id, drug_name=f"약A{i}", diagnosis="고혈압"))
        session.add(OcrResult(record_id=record.id, drug_name=f"약B{i}", diagnosis=""))
        session.commit()
        records.append(record)
    return records, caregiver


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


class TestQueryCountDoesNotScaleWithRecordCount:
    @pytest.mark.parametrize("n", [3, 10, 20])
    def test_fixed_query_count_regardless_of_record_count(
        self, client: TestClient, session: Session, engine, n: int
    ):
        pt = _make_patient(session)
        _build_records(session, pt, n)

        response, query_count = _count_select_queries(
            engine,
            lambda: client.get("/records", params={"patient_id": pt.id}, headers=_headers(pt.id)),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == n

        # bulk-select 패턴 적용 후 예상 쿼리 수: 인증(require_actor_patient_access) 조회(1) +
        # records(1) + ocr_results bulk(1) + caregiver bulk(1, 업로더가 있을 때만) = 4.
        # 기록 수(n)와 무관하게 고정.
        assert query_count == 4, f"n={n}일 때 쿼리 수가 {query_count}회 — 기록 수와 무관하게 4회여야 함"

    def test_query_count_identical_for_3_and_20_records(self, session: Session, engine):
        """가장 직접적인 회귀 신호 — 기록 3건과 20건에서 쿼리 수가 완전히 같아야 N+1이 없다는 뜻."""
        counts = {}
        for n in (3, 20):
            pt = _make_patient(session)
            _build_records(session, pt, n)
            app.dependency_overrides[get_session] = lambda: session
            client = TestClient(app, raise_server_exceptions=True)
            _, query_count = _count_select_queries(
                engine,
                lambda: client.get("/records", params={"patient_id": pt.id}, headers=_headers(pt.id)),
            )
            counts[n] = query_count
            app.dependency_overrides.clear()

        assert counts[3] == counts[20], f"쿼리 수가 기록 수에 비례해 늘어남: {counts}"


class TestBulkResultsMatchOriginalPerRecordBehavior:
    """bulk-select로 바꾸면서 값 자체가 달라지지 않았는지 확인 — 순수 성능 개선이어야 한다."""

    def test_diagnosis_and_drug_names_from_first_and_all_ocr_items(
        self, client: TestClient, session: Session
    ):
        pt = _make_patient(session)
        _build_records(session, pt, 3)

        r = client.get("/records", params={"patient_id": pt.id}, headers=_headers(pt.id))
        body = r.json()
        assert len(body) == 3
        for entry in body:
            # diagnosis는 그 기록의 "첫 OCR 항목"(약A) 것을 그대로 씀 — 원래 함수와 동일 규칙
            assert entry["diagnosis"] == "고혈압"
            assert len(entry["drug_names"]) == 2

    def test_uploader_name_only_when_uploaded_by_caregiver(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        _build_records(session, pt, 4)

        r = client.get("/records", params={"patient_id": pt.id}, headers=_headers(pt.id))
        body = r.json()
        with_uploader = [e for e in body if e["uploaded_by_name"] is not None]
        without_uploader = [e for e in body if e["uploaded_by_name"] is None]
        assert len(with_uploader) == 2  # i % 2 == 0 인 것들
        assert len(without_uploader) == 2
        assert all(e["uploaded_by_name"] == "업로더보호자" for e in with_uploader)

    def test_deleted_and_other_patient_records_excluded(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        other_pt = _make_patient(session)
        _build_records(session, pt, 2)
        deleted = MedicalRecord(
            patient_id=pt.id, image_path="/tmp/deleted.png", deleted_at=datetime.now()
        )
        other_record = MedicalRecord(patient_id=other_pt.id, image_path="/tmp/other.png")
        session.add(deleted)
        session.add(other_record)
        session.commit()

        r = client.get("/records", params={"patient_id": pt.id}, headers=_headers(pt.id))
        assert len(r.json()) == 2

    def test_record_with_no_ocr_items_gets_empty_diagnosis_and_drugs(
        self, client: TestClient, session: Session
    ):
        pt = _make_patient(session)
        record = MedicalRecord(patient_id=pt.id, image_path="/tmp/empty.png")
        session.add(record)
        session.commit()

        r = client.get("/records", params={"patient_id": pt.id}, headers=_headers(pt.id))
        body = r.json()
        assert len(body) == 1
        assert body[0]["diagnosis"] == ""
        assert body[0]["drug_names"] == []
        assert body[0]["uploaded_by_name"] is None
