"""
chat_router.py — 추천 질문(GET /chat/questions) 동적 생성 테스트 (2026-07-19 추가)

팀 회의에서 "앱을 켤 때마다 같은 기본 질문이 뜬다"고 보고된 현상 — 실제로는 캐시 버그가
아니라 PRESET_QUESTIONS가 완전히 정적인 리스트라 생기는 당연한 결과였다(원인 조사 결과는
docs/status-report 참고). 환자가 실제 등록한 약 기반으로 질문을 생성하도록 바꾼 뒤,
(1) 등록 약 있음/OCR만 있음/둘 다 없음 세 갈래 폴백과 (2) 새로 patient_id를 받게 된
GET /chat/questions의 IDOR 보호, (3) POST /ask가 동적 question_id를 정상 해석하는지를
검증한다.
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
    OcrResult,
    Patient,
    PatientMedication,
)
from routers.chat_router import PRESET_QUESTIONS, _build_dynamic_questions
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


def _make_patient(session: Session, name: str = "환자A") -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_caregiver(session: Session, name: str = "보호자A") -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


class TestBuildDynamicQuestions:
    def test_no_registered_medication_falls_back_to_static_preset(self, session: Session):
        pt = _make_patient(session, "빈환자")
        questions = _build_dynamic_questions(pt.id, session)
        assert questions == PRESET_QUESTIONS

    def test_registered_medication_generates_drug_specific_questions(self, session: Session):
        pt = _make_patient(session, "약등록환자")
        session.add(
            PatientMedication(
                patient_id=pt.id,
                medication_name="암로디핀정5밀리그램",
                source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()

        questions = _build_dynamic_questions(pt.id, session)
        assert len(questions) == 3
        assert all("암로디핀정5밀리그램" in q["text"] for q in questions)
        assert all("암로디핀정5밀리그램" in q["answer"] for q in questions)
        assert all(q["id"].startswith("dyn:") for q in questions)

    def test_inactive_or_deleted_medication_is_ignored(self, session: Session):
        pt = _make_patient(session, "탈퇴약환자")
        session.add(
            PatientMedication(
                patient_id=pt.id,
                medication_name="비활성약",
                source_type="manual",
                verification_status="user_confirmed",
                is_active=False,
            )
        )
        session.commit()

        questions = _build_dynamic_questions(pt.id, session)
        assert questions == PRESET_QUESTIONS  # 활성 등록 약이 없으니 정적 폴백

    def test_no_patient_medication_falls_back_to_latest_ocr_drug_name(self, session: Session):
        pt = _make_patient(session, "OCR환자")
        record = MedicalRecord(patient_id=pt.id, image_path="x.jpg", status="completed")
        session.add(record)
        session.commit()
        session.refresh(record)
        session.add(
            OcrResult(
                record_id=record.id,
                drug_name="타이레놀정500mg",
                dosage="500mg",
                frequency="1일 3회",
                diagnosis="두통",
            )
        )
        session.commit()

        questions = _build_dynamic_questions(pt.id, session)
        assert all("타이레놀정500mg" in q["text"] for q in questions)


class TestQuestionsEndpointAuth:
    def test_owner_caregiver_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "qOwnerCg")
        pt = _make_patient(session, "qPatA")
        session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
        session.commit()
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.get("/chat/questions", params={"patient_id": pt.id}, headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_other_caregiver_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "qOwnerCg2")
        cg_other = _make_caregiver(session, "qOtherCg")
        pt = _make_patient(session, "qPatB")
        session.add(CaregiverPatient(caregiver_id=cg_owner.id, patient_id=pt.id))
        session.commit()
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.get("/chat/questions", params={"patient_id": pt.id}, headers=headers)
        assert r.status_code == 403

    def test_no_auth_401(self, client: TestClient, session: Session):
        pt = _make_patient(session, "qPatC")
        r = client.get("/chat/questions", params={"patient_id": pt.id})
        assert r.status_code in (401, 403)


class TestAskWithDynamicQuestionId:
    def test_ask_resolves_dynamic_question_id(self, client: TestClient, session: Session):
        pt = _make_patient(session, "askDynPat")
        session.add(
            PatientMedication(
                patient_id=pt.id,
                medication_name="메트포르민정500mg",
                source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        listed = client.get("/chat/questions", params={"patient_id": pt.id}, headers=headers)
        dyn_id = listed.json()[0]["id"]
        assert dyn_id.startswith("dyn:")

        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": dyn_id}, headers=headers)
        assert r.status_code == 200
        assert "메트포르민정500mg" in r.json()["answer"]

    def test_ask_unknown_question_id_404s(self, client: TestClient, session: Session):
        pt = _make_patient(session, "askUnknownPat")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        r = client.post(
            "/chat/ask", json={"patient_id": pt.id, "question_id": "dyn:meal_timing:없는약"}, headers=headers
        )
        assert r.status_code == 404
