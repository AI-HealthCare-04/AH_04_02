"""
records_router.py — _build_record_response()의 drug_name 표시값 선택 테스트
(2026-07-20 신규, 담당: 김영혜)

OCR 파싱(services/parsing_rules.py의 _drug_name_only)이 매칭용으로 "암로디핀정5mg"을
"암로디핀"으로 잘라 OcrResult.drug_name에 저장하는 건 의도된 동작이고 그대로 둔다.
다만 drug_matcher가 이미 찾아둔 정확한 전체 제품명(matched_drug_name)이 화면에는
전혀 안 쓰이고 있었다 — 확신 있게 매칭됐을 때(needs_review=False)만 이 값을 대표
표시값으로 쓰도록 응답 조립 단계만 고쳤다. 매칭이 불확실하면(needs_review=True) 사용자가
직접 확인/수정해야 하므로 원본 파싱값을 그대로 보여줘야 한다.
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


def _make_patient_with_caregiver(session: Session):
    cg = Caregiver(password_hash="x")
    cg.name = "보호자A"
    pt = Patient(password_hash="x")
    pt.name = "환자A"
    session.add(cg)
    session.add(pt)
    session.commit()
    session.refresh(cg)
    session.refresh(pt)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()
    return cg, pt


def _headers(caregiver_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(caregiver_id, 'caregiver')}"}


class TestDrugNameDisplayValue:
    def test_confident_match_shows_precise_matched_name(self, client: TestClient, session: Session):
        cg, pt = _make_patient_with_caregiver(session)
        rec = MedicalRecord(patient_id=pt.id, image_path="test.jpg", status="completed")
        session.add(rec)
        session.commit()
        session.refresh(rec)
        session.add(
            OcrResult(
                record_id=rec.id,
                drug_name="암로디핀",  # 파싱 단계에서 형태가 잘린 값
                matched_drug_name="암로디핀정5mg",  # drug_matcher가 찾은 정확한 제품명
                match_score=0.95,
                needs_review=False,
                confidence=0.9,
            )
        )
        session.commit()

        r = client.get(f"/records/{rec.id}", headers=_headers(cg.id))

        assert r.status_code == 200
        assert r.json()["medications"][0]["drug_name"] == "암로디핀정5mg"

    def test_uncertain_match_keeps_raw_parsed_name_for_user_review(self, client: TestClient, session: Session):
        """needs_review=True(매칭 불확실)면 사용자가 직접 고쳐야 하니 원본 파싱값을 보여준다."""
        cg, pt = _make_patient_with_caregiver(session)
        rec = MedicalRecord(patient_id=pt.id, image_path="test.jpg", status="review_required")
        session.add(rec)
        session.commit()
        session.refresh(rec)
        session.add(
            OcrResult(
                record_id=rec.id,
                drug_name="암로디민",  # OCR 오타
                matched_drug_name="암로디핀정5mg",  # 유사도로 억지로 매칭됐지만 확신 없음
                match_score=0.55,
                needs_review=True,
                confidence=0.5,
                review_required=True,
            )
        )
        session.commit()

        r = client.get(f"/records/{rec.id}", headers=_headers(cg.id))

        assert r.json()["medications"][0]["drug_name"] == "암로디민"

    def test_no_matched_name_falls_back_to_raw_drug_name(self, client: TestClient, session: Session):
        cg, pt = _make_patient_with_caregiver(session)
        rec = MedicalRecord(patient_id=pt.id, image_path="test.jpg", status="completed")
        session.add(rec)
        session.commit()
        session.refresh(rec)
        session.add(
            OcrResult(
                record_id=rec.id,
                drug_name="미등재약품",
                matched_drug_name="",
                needs_review=False,
                confidence=0.9,
            )
        )
        session.commit()

        r = client.get(f"/records/{rec.id}", headers=_headers(cg.id))

        assert r.json()["medications"][0]["drug_name"] == "미등재약품"
