"""
records_router.py — record_id 기반 엔드포인트 소유권 검증 테스트

4개 엔드포인트가 모두:
  - 소유자(보호자) 토큰 → 정상 응답
  - 타인 토큰 → 403
  - 무인증 → 403 (HTTPBearer에 의해)
를 보장하는지 확인한다.
"""
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
    OcrResult,
    Patient,
    PatientMedication,
)
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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


def _make_caregiver(session: Session, name: str = "보호자A") -> Caregiver:
    cg = Caregiver(password_hash="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _make_patient(session: Session, name: str = "환자A") -> Patient:
    pt = Patient(password_hash="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _link(session: Session, cg: Caregiver, pt: Patient) -> None:
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()


def _make_record(session: Session, patient_id: int, status: str = "review_required") -> MedicalRecord:
    rec = MedicalRecord(patient_id=patient_id, image_path="test.jpg", status=status)
    session.add(rec)
    session.commit()
    session.refresh(rec)
    ocr = OcrResult(record_id=rec.id, drug_name="테스트약", confidence=0.9, review_required=True)
    session.add(ocr)
    session.commit()
    return rec


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


# ──────────────────────────────────────────────────────────────
# GET /records/{record_id}
# ──────────────────────────────────────────────────────────────

class TestGetRecord:
    def test_owner_caregiver_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "ownerA")
        pt = _make_patient(session, "patA")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id, status="completed")
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.get(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["record_id"] == rec.id

    def test_owner_patient_ok(self, client: TestClient, session: Session):
        pt = _make_patient(session, "patB")
        rec = _make_record(session, pt.id, status="completed")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        r = client.get(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 200

    def test_other_caregiver_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "ownerB")
        cg_other = _make_caregiver(session, "otherB")
        pt = _make_patient(session, "patC")
        _link(session, cg_owner, pt)
        rec = _make_record(session, pt.id, status="completed")
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.get(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 403

    def test_other_patient_403(self, client: TestClient, session: Session):
        pt_owner = _make_patient(session, "patD")
        pt_other = _make_patient(session, "patE")
        rec = _make_record(session, pt_owner.id, status="completed")
        headers = {"Authorization": f"Bearer {_token(pt_other.id, 'patient')}"}
        r = client.get(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 403

    def test_no_auth_401(self, client: TestClient, session: Session):
        pt = _make_patient(session, "patF")
        rec = _make_record(session, pt.id)
        r = client.get(f"/records/{rec.id}")
        assert r.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────
# POST /records/{record_id}/medications
# ──────────────────────────────────────────────────────────────

class TestAddMedication:
    def test_owner_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "cgAdd")
        pt = _make_patient(session, "ptAdd")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id)
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.post(f"/records/{rec.id}/medications", headers=headers)
        assert r.status_code == 200

    def test_other_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "cgAddOwner")
        cg_other = _make_caregiver(session, "cgAddOther")
        pt = _make_patient(session, "ptAddOther")
        _link(session, cg_owner, pt)
        rec = _make_record(session, pt.id)
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.post(f"/records/{rec.id}/medications", headers=headers)
        assert r.status_code == 403


# ──────────────────────────────────────────────────────────────
# DELETE /records/{record_id}/medications/{medication_id}
# ──────────────────────────────────────────────────────────────

class TestRemoveMedication:
    def _setup(self, session: Session):
        cg = _make_caregiver(session, "cgDel")
        pt = _make_patient(session, "ptDel")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id)
        # 두 번째 약 추가해서 삭제 가능하게
        ocr2 = OcrResult(record_id=rec.id, drug_name="약2", confidence=0.9, review_required=True)
        session.add(ocr2)
        session.commit()
        session.refresh(ocr2)
        return cg, pt, rec, ocr2

    def test_owner_ok(self, client: TestClient, session: Session):
        cg, pt, rec, ocr2 = self._setup(session)
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.delete(f"/records/{rec.id}/medications/{ocr2.id}", headers=headers)
        assert r.status_code == 200

    def test_other_403(self, client: TestClient, session: Session):
        cg_owner, pt, rec, ocr2 = self._setup(session)
        cg_other = _make_caregiver(session, "cgDelOther")
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.delete(f"/records/{rec.id}/medications/{ocr2.id}", headers=headers)
        assert r.status_code == 403


# ──────────────────────────────────────────────────────────────
# DELETE /records/{record_id}
# ──────────────────────────────────────────────────────────────

class TestDeleteRecord:
    def test_owner_ok_and_soft_deleted(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "cgDelRec")
        pt = _make_patient(session, "ptDelRec")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id, status="completed")
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.delete(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 200

        # 목록/상세 조회에서 제외되는지 (soft-delete)
        assert client.get("/records", params={"patient_id": pt.id}, headers=headers).json() == []
        r_get = client.get(f"/records/{rec.id}", headers=headers)
        assert r_get.status_code == 404

    def test_other_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "cgDelRecOwner")
        cg_other = _make_caregiver(session, "cgDelRecOther")
        pt = _make_patient(session, "ptDelRecOther")
        _link(session, cg_owner, pt)
        rec = _make_record(session, pt.id)
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.delete(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 403

    def test_deleting_record_deactivates_its_schedules(self, client: TestClient, session: Session):
        """[2026-07-20 추가] 리뷰에서 발견 — record_id로 연결된 자동 생성 일정이 삭제 후에도
        active로 남아 대시보드/스케줄러 알림에 계속 떴다. 삭제 시 같이 비활성화되는지 확인."""
        cg = _make_caregiver(session, "cgDelSched")
        pt = _make_patient(session, "ptDelSched")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id, status="completed")

        linked = MedicationSchedule(patient_id=pt.id, drug_name="테스트약", time_slot="09:00", record_id=rec.id)
        unrelated = MedicationSchedule(patient_id=pt.id, drug_name="직접등록약", time_slot="09:00")
        session.add(linked)
        session.add(unrelated)
        session.commit()
        session.refresh(linked)
        session.refresh(unrelated)

        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.delete(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 200

        session.refresh(linked)
        session.refresh(unrelated)
        assert linked.active is False
        assert unrelated.active is True  # 이 처방전과 무관한 일정은 그대로 유지

    def test_deactivate_medications_false_keeps_schedule_active(self, client: TestClient, session: Session):
        """[2026-08-05 추가] Records.tsx의 "등록된 약도 함께 제거" 체크를 해제하고 삭제하면
        처방전 기록만 지워지고 연결된 복약 일정은 active로 그대로 남아야 한다."""
        cg = _make_caregiver(session, "cgDelKeepSched")
        pt = _make_patient(session, "ptDelKeepSched")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id, status="completed")

        linked = MedicationSchedule(patient_id=pt.id, drug_name="테스트약", time_slot="09:00", record_id=rec.id)
        session.add(linked)
        session.commit()
        session.refresh(linked)

        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.delete(
            f"/records/{rec.id}", params={"deactivate_medications": False}, headers=headers
        )
        assert r.status_code == 200

        session.refresh(linked)
        assert linked.active is True

        # 처방전 기록 자체는 정상적으로 soft-delete된다
        r_get = client.get(f"/records/{rec.id}", headers=headers)
        assert r_get.status_code == 404

    def test_deleting_record_soft_deletes_prescription_medications(self, client: TestClient, session: Session):
        """처방전 기반 내약이 남으면 다음 로그인 때 삭제가 안 된 것처럼 보인다."""
        cg = _make_caregiver(session, "cgDelPrescriptionMed")
        pt = _make_patient(session, "ptDelPrescriptionMed")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id, status="completed")

        medication = PatientMedication(
            patient_id=pt.id,
            medication_name="처방전기반약",
            prescription_id=rec.id,
            source_type="prescription_ocr",
        )
        unrelated = PatientMedication(
            patient_id=pt.id,
            medication_name="직접등록약",
            source_type="manual",
        )
        session.add(medication)
        session.add(unrelated)
        session.commit()
        session.refresh(medication)
        session.refresh(unrelated)

        linked_schedule = MedicationSchedule(
            patient_id=pt.id,
            patient_medication_id=medication.id,
            drug_name="처방전기반약",
            time_slot="09:00",
        )
        session.add(linked_schedule)
        session.commit()
        session.refresh(linked_schedule)

        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.delete(f"/records/{rec.id}", headers=headers)
        assert r.status_code == 200

        session.refresh(medication)
        session.refresh(unrelated)
        session.refresh(linked_schedule)
        assert medication.deleted_at is not None
        assert medication.is_active is False
        assert linked_schedule.active is False
        assert unrelated.deleted_at is None
        assert unrelated.is_active is True

    def test_already_deleted_404(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "cgDelRecTwice")
        pt = _make_patient(session, "ptDelRecTwice")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id)
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        assert client.delete(f"/records/{rec.id}", headers=headers).status_code == 200
        assert client.delete(f"/records/{rec.id}", headers=headers).status_code == 404


# ──────────────────────────────────────────────────────────────
# POST /records/{record_id}/confirm  (RAG 없이 stub)
# ──────────────────────────────────────────────────────────────

class TestConfirmMedications:
    def test_other_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "cgConOwner")
        cg_other = _make_caregiver(session, "cgConOther")
        pt = _make_patient(session, "ptCon")
        _link(session, cg_owner, pt)
        rec = _make_record(session, pt.id)
        payload = {"medications": []}
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.post(f"/records/{rec.id}/confirm", json=payload, headers=headers)
        assert r.status_code == 403

    def test_owner_reaches_rag(self, client: TestClient, session: Session):
        """소유자 토큰은 인가 통과 → RAG 실패(ValueError)로 500 계열이 아닌 4xx가 아닌 것만 확인."""
        cg = _make_caregiver(session, "cgConOk")
        pt = _make_patient(session, "ptConOk")
        _link(session, cg, pt)
        rec = _make_record(session, pt.id)
        payload = {"medications": []}
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.post(f"/records/{rec.id}/confirm", json=payload, headers=headers)
        # 403은 아니어야 함 (인가 통과). RAG는 테스트 환경에선 실패해도 OK.
        assert r.status_code != 403
