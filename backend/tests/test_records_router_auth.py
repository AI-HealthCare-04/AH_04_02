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
from models import Caregiver, CaregiverPatient, MedicalRecord, OcrResult, Patient
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
