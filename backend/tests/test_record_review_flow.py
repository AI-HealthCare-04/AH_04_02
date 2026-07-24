"""
test_record_review_flow.py — 보호자·기관 처방전 검토 흐름 (2026-07-25 추가)

POST /records/{id}/request-correction, POST /records/{id}/mark-reviewed,
PATCH /records/{id}/medications/{med_id}/correct 3개 엔드포인트와
MedicalRecord.caregiver_review_status 상태 전이를 검증한다.
"""
from __future__ import annotations

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import (
    Caregiver,
    CaregiverPatient,
    MedicalRecord,
    MedicationFieldFlag,
    OcrResult,
    Patient,
    RecordCorrectionNotice,
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


def _make_caregiver(session: Session, name: str = "보호자") -> Caregiver:
    cg = Caregiver(password_hash="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _make_patient(session: Session, name: str = "환자") -> Patient:
    pt = Patient(password_hash="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _link(session: Session, cg: Caregiver, pt: Patient) -> None:
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()


def _make_completed_record(session: Session, patient_id: int, review_status: str = "pending") -> tuple[MedicalRecord, OcrResult]:
    rec = MedicalRecord(patient_id=patient_id, image_path="t.jpg", status="completed", caregiver_review_status=review_status)
    session.add(rec)
    session.commit()
    session.refresh(rec)
    ocr = OcrResult(record_id=rec.id, drug_name="암로핀정 5mg", dosage="1정", dose_amount="5mg", frequency="1회")
    session.add(ocr)
    session.commit()
    session.refresh(ocr)
    return rec, ocr


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


# ── POST /records/{id}/request-correction ──────────────────────────────────

class TestRequestCorrection:
    def test_caregiver_flags_field(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id)

        r = client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "1정이 아니라 2정이에요"}]},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["caregiver_review_status"] == "needs_correction"
        flags = body["medications"][0]["field_flags"]
        assert len(flags) == 1
        assert flags[0]["field_name"] == "dosage"
        assert flags[0]["corrected"] is False

        session.refresh(rec)
        assert rec.caregiver_review_status == "needs_correction"
        notices = session.exec(select(RecordCorrectionNotice)).all()
        assert len(notices) == 1
        assert notices[0].recipient_role == "patient"
        assert notices[0].recipient_id == pt.id
        assert notices[0].event == "correction_requested"

    def test_patient_role_forbidden(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        rec, ocr = _make_completed_record(session, pt.id)
        r = client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "틀렸어요"}]},
            headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"},
        )
        assert r.status_code == 403

    def test_unrelated_caregiver_403(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        other = _make_caregiver(session, "타인")
        rec, ocr = _make_completed_record(session, pt.id)
        r = client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "틀렸어요"}]},
            headers={"Authorization": f"Bearer {_token(other.id, 'caregiver')}"},
        )
        assert r.status_code == 403

    def test_unknown_field_name_rejected(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id)
        r = client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "id", "reason": "안돼요"}]},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        assert r.status_code == 422

    def test_empty_reason_rejected(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id)
        r = client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "   "}]},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        assert r.status_code == 422

    def test_not_yet_completed_record_409(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id)
        rec.status = "review_required"
        session.add(rec)
        session.commit()
        r = client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "틀렸어요"}]},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        assert r.status_code == 409


# ── POST /records/{id}/mark-reviewed ────────────────────────────────────────

class TestMarkReviewed:
    def test_caregiver_marks_reviewed(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, _ocr = _make_completed_record(session, pt.id)

        r = client.post(
            f"/records/{rec.id}/mark-reviewed",
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        assert r.status_code == 200
        assert r.json()["caregiver_review_status"] == "reviewed"
        session.refresh(rec)
        assert rec.caregiver_review_status == "reviewed"

    def test_patient_role_forbidden(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        rec, _ocr = _make_completed_record(session, pt.id)
        r = client.post(
            f"/records/{rec.id}/mark-reviewed",
            headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"},
        )
        assert r.status_code == 403


# ── PATCH /records/{id}/medications/{med_id}/correct ───────────────────────

class TestCorrectMedicationField:
    def test_patient_corrects_flagged_field(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id, review_status="needs_correction")
        session.add(MedicationFieldFlag(ocr_result_id=ocr.id, field_name="dosage", reason="1정이 아니라 2정이에요"))
        session.commit()

        r = client.patch(
            f"/records/{rec.id}/medications/{ocr.id}/correct",
            json={"field_name": "dosage", "value": "2정"},
            headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["medications"][0]["dosage"] == "2정"
        assert body["medications"][0]["field_flags"][0]["corrected"] is True

        session.refresh(ocr)
        assert ocr.dosage == "2정"

    def test_rejects_field_without_active_flag(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id, review_status="needs_correction")
        session.add(MedicationFieldFlag(ocr_result_id=ocr.id, field_name="dosage", reason="틀렸어요"))
        session.commit()

        # frequency엔 플래그가 없으니 고칠 수 없어야 함 — UI 잠금이 우회되더라도 서버가 막는다.
        r = client.patch(
            f"/records/{rec.id}/medications/{ocr.id}/correct",
            json={"field_name": "frequency", "value": "2회"},
            headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"},
        )
        assert r.status_code == 409
        session.refresh(ocr)
        assert ocr.frequency == "1회"  # 안 바뀜

    def test_already_corrected_flag_rejects_second_edit(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id, review_status="needs_correction")
        session.add(MedicationFieldFlag(ocr_result_id=ocr.id, field_name="dosage", reason="틀렸어요"))
        session.commit()
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        first = client.patch(
            f"/records/{rec.id}/medications/{ocr.id}/correct",
            json={"field_name": "dosage", "value": "2정"},
            headers=headers,
        )
        assert first.status_code == 200

        second = client.patch(
            f"/records/{rec.id}/medications/{ocr.id}/correct",
            json={"field_name": "dosage", "value": "3정"},
            headers=headers,
        )
        assert second.status_code == 409

    def test_all_flags_corrected_notifies_caregiver(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id, review_status="needs_correction")
        session.add(MedicationFieldFlag(ocr_result_id=ocr.id, field_name="dosage", reason="틀렸어요"))
        session.add(MedicationFieldFlag(ocr_result_id=ocr.id, field_name="frequency", reason="틀렸어요"))
        session.commit()
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        client.patch(f"/records/{rec.id}/medications/{ocr.id}/correct", json={"field_name": "dosage", "value": "2정"}, headers=headers)
        notices_after_first = session.exec(select(RecordCorrectionNotice)).all()
        assert len(notices_after_first) == 0  # 아직 미수정 플래그(frequency) 남아있음

        client.patch(f"/records/{rec.id}/medications/{ocr.id}/correct", json={"field_name": "frequency", "value": "2회"}, headers=headers)
        notices_after_second = session.exec(select(RecordCorrectionNotice)).all()
        assert len(notices_after_second) == 1
        assert notices_after_second[0].recipient_role == "caregiver"
        assert notices_after_second[0].recipient_id == cg.id
        assert notices_after_second[0].event == "correction_completed"

    def test_unknown_field_name_rejected(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        rec, ocr = _make_completed_record(session, pt.id, review_status="needs_correction")
        r = client.patch(
            f"/records/{rec.id}/medications/{ocr.id}/correct",
            json={"field_name": "id", "value": "999"},
            headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"},
        )
        assert r.status_code == 422


# ── 처방전이 completed로 넘어갈 때 caregiver_review_status 초기값 ───────────

class TestInitialReviewStatusOnConfirm:
    def test_linked_caregiver_sets_pending(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec = MedicalRecord(patient_id=pt.id, image_path="t.jpg", status="review_required")
        session.add(rec)
        session.commit()
        session.refresh(rec)
        ocr = OcrResult(record_id=rec.id, drug_name="테스트약", confidence=0.9)
        session.add(ocr)
        session.commit()

        r = client.post(
            f"/records/{rec.id}/confirm",
            json={"medications": []},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        assert r.status_code == 200
        session.refresh(rec)
        assert rec.status == "completed"
        assert rec.caregiver_review_status == "pending"

    def test_no_caregiver_sets_none(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        rec = MedicalRecord(patient_id=pt.id, image_path="t.jpg", status="review_required")
        session.add(rec)
        session.commit()
        session.refresh(rec)
        ocr = OcrResult(record_id=rec.id, drug_name="테스트약", confidence=0.9)
        session.add(ocr)
        session.commit()

        r = client.post(
            f"/records/{rec.id}/confirm",
            json={"medications": []},
            headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"},
        )
        assert r.status_code == 200
        session.refresh(rec)
        assert rec.status == "completed"
        assert rec.caregiver_review_status == "none"


# ── GET /records/notices, POST /records/notices/{id}/read ──────────────────

class TestCorrectionNotices:
    def test_patient_sees_correction_requested(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id)
        client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "틀렸어요"}]},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )

        r = client.get("/records/notices", headers={"Authorization": f"Bearer {_token(pt.id, 'patient')}"})
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["event"] == "correction_requested"
        assert body[0]["record_id"] == rec.id

        # 다른 사람에게는 안 보임
        other = _make_caregiver(session, "타인")
        r_other = client.get("/records/notices", headers={"Authorization": f"Bearer {_token(other.id, 'caregiver')}"})
        assert r_other.json() == []

    def test_mark_read_removes_from_list(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        rec, ocr = _make_completed_record(session, pt.id)
        client.post(
            f"/records/{rec.id}/request-correction",
            json={"flags": [{"ocr_result_id": ocr.id, "field_name": "dosage", "reason": "틀렸어요"}]},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        notice_id = client.get("/records/notices", headers=headers).json()[0]["id"]

        r = client.post(f"/records/notices/{notice_id}/read", headers=headers)
        assert r.status_code == 200
        assert client.get("/records/notices", headers=headers).json() == []
