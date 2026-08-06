"""
test_records_router_patch_medication.py — REQ-047 오타 제안 단위 테스트

PATCH /records/{record_id}/medications/{medication_id} 엔드포인트 검증:
1. 사전에 정확히 있는 이름 → typo_suggestion 없음
2. 오타 입력 → typo_suggestion에 유사 후보
3. DB에 typo_suggestion 저장 안 됨
4. MATCH_THRESHOLD 미만 매칭 → typo_suggestion None
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, MedicalRecord, OcrResult, Patient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


# ── fixtures ────────────────────────────────────────────────────────────────

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


def _make_caregiver(session: Session) -> Caregiver:
    cg = Caregiver(password_hash="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _make_patient(session: Session) -> Patient:
    pt = Patient(password_hash="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _setup(session: Session):
    """보호자-환자 연결 + review_required 처방전 + OcrResult 하나 생성."""
    cg = _make_caregiver(session)
    pt = _make_patient(session)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    rec = MedicalRecord(patient_id=pt.id, image_path="t.jpg", status="review_required")
    session.add(rec)
    session.commit()
    session.refresh(rec)
    ocr = OcrResult(record_id=rec.id, drug_name="원본약", confidence=0.9, review_required=True)
    session.add(ocr)
    session.commit()
    session.refresh(ocr)
    return cg, pt, rec, ocr


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


def _patch(client, record_id, medication_id, drug_name, token):
    return client.patch(
        f"/records/{record_id}/medications/{medication_id}",
        json={"drug_name": drug_name, "dosage": "500mg", "frequency": "1일 1회"},
        headers={"Authorization": f"Bearer {token}"},
    )


# ── 테스트 케이스 ─────────────────────────────────────────────────────────

def test_exact_match_no_typo_suggestion(client, session):
    """사전에 정확히 있는 이름 입력 → typo_suggestion 없음."""
    cg, _, rec, ocr = _setup(session)
    token = _token(cg.id, "caregiver")

    # match_drug가 입력과 동일한 이름 반환 (exact match)
    with patch("routers.records_router.match_drug", return_value=("메트포르민정500mg", 1.0)):
        r = _patch(client, rec.id, ocr.id, "메트포르민정500mg", token)

    assert r.status_code == 200
    body = r.json()
    assert body["drug_name"] == "메트포르민정500mg"
    assert body["typo_suggestion"] is None


def test_typo_input_returns_suggestion(client, session):
    """오타 입력(메트포르인정500mg) → typo_suggestion에 올바른 후보."""
    cg, _, rec, ocr = _setup(session)
    token = _token(cg.id, "caregiver")

    with patch("routers.records_router.match_drug", return_value=("메트포르민정500mg", 0.85)):
        r = _patch(client, rec.id, ocr.id, "메트포르인정500mg", token)

    assert r.status_code == 200
    body = r.json()
    assert body["drug_name"] == "메트포르인정500mg"      # 저장된 값은 입력 그대로
    assert body["typo_suggestion"] == "메트포르민정500mg"  # 제안은 사전 후보


def test_typo_suggestion_not_saved_to_db(client, session):
    """typo_suggestion은 응답 전용 — DB OcrResult에는 저장되지 않는다."""
    cg, _, rec, ocr = _setup(session)
    token = _token(cg.id, "caregiver")

    with patch("routers.records_router.match_drug", return_value=("메트포르민정500mg", 0.85)):
        r = _patch(client, rec.id, ocr.id, "메트포르인정500mg", token)

    assert r.status_code == 200
    assert r.json()["typo_suggestion"] == "메트포르민정500mg"

    # DB에서 직접 조회 — OcrResult에 typo_suggestion 컬럼 자체가 없어야 함
    session.refresh(ocr)
    assert not hasattr(ocr, "typo_suggestion")
    # matched_drug_name은 저장됨 (drug_matcher 결과)
    assert ocr.matched_drug_name == "메트포르민정500mg"
    assert ocr.match_score == 0.85


def test_low_score_no_typo_suggestion(client, session):
    """MATCH_THRESHOLD(0.7) 미만 점수 → typo_suggestion None."""
    cg, _, rec, ocr = _setup(session)
    token = _token(cg.id, "caregiver")

    with patch("routers.records_router.match_drug", return_value=("전혀다른약", 0.3)):
        r = _patch(client, rec.id, ocr.id, "완전없는약이름xyz", token)

    assert r.status_code == 200
    body = r.json()
    assert body["typo_suggestion"] is None
    assert body["needs_review"] is True   # 낮은 score → needs_review=True


def test_patch_updates_db_fields(client, session):
    """PATCH 후 DB의 drug_name/dosage/frequency가 실제로 갱신된다."""
    cg, _, rec, ocr = _setup(session)
    token = _token(cg.id, "caregiver")

    with patch("routers.records_router.match_drug", return_value=("암로디핀정5mg", 1.0)):
        r = client.patch(
            f"/records/{rec.id}/medications/{ocr.id}",
            json={"drug_name": "암로디핀정5mg", "dosage": "5mg", "frequency": "1일 1회", "total_days": "30일"},
            headers={"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"},
        )

    assert r.status_code == 200
    session.refresh(ocr)
    assert ocr.drug_name == "암로디핀정5mg"
    assert ocr.dosage == "5mg"
    assert ocr.total_days == "30일"


def test_patch_wrong_record_404(client, session):
    """medication_id가 다른 record 소속이면 404."""
    cg, _, rec, ocr = _setup(session)

    # 별도 record 생성
    rec2 = MedicalRecord(patient_id=rec.patient_id, image_path="t2.jpg", status="review_required")
    session.add(rec2)
    session.commit()
    session.refresh(rec2)

    with patch("routers.records_router.match_drug", return_value=("약", 1.0)):
        r = _patch(client, rec2.id, ocr.id, "약", _token(cg.id, "caregiver"))

    assert r.status_code == 404


def test_patch_completed_record_409(client, session):
    """status가 review_required가 아닌 처방전은 409."""
    cg, _, rec, ocr = _setup(session)
    rec.status = "completed"
    session.add(rec)
    session.commit()

    with patch("routers.records_router.match_drug", return_value=("약", 1.0)):
        r = _patch(client, rec.id, ocr.id, "약", _token(cg.id, "caregiver"))

    assert r.status_code == 409


def test_patch_unrelated_caregiver_403(client, session):
    """연결되지 않은 보호자 → 403."""
    _, _, rec, ocr = _setup(session)

    other = Caregiver(password_hash="x")
    other.name = "타인"
    session.add(other)
    session.commit()
    session.refresh(other)

    with patch("routers.records_router.match_drug", return_value=("약", 1.0)):
        r = _patch(client, rec.id, ocr.id, "약", _token(other.id, "caregiver"))

    assert r.status_code == 403