"""
test_update_email_normalization.py — PATCH /monitoring/patients·caregivers의 email
빈 문자열 처리 검증 (2026-07-23 추가, PR#71 리뷰 반영)

email은 Patient/Caregiver 둘 다 unique=True다. 예전엔 "email" in updates and
updates["email"] 조건이 빈 문자열일 때 그대로 falsy라 스킵되면서 setattr로
""가 그대로 저장됐다 — 서로 다른 두 계정이 이메일을 지우면 unique 제약 충돌이
날 수 있었다. 빈 문자열은 None으로 정규화해야 여러 계정이 동시에 지워도 안전하다
(표준 SQL에서 UNIQUE는 NULL끼리는 충돌하지 않는다).
"""
import pytest
from conftest import make_test_engine
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, Patient
from sqlmodel import Session


@pytest.fixture(name="session")
def session_fixture():
    engine = make_test_engine()
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


def test_clearing_patient_email_to_empty_string_stores_none(client: TestClient, session: Session):
    pt = Patient(hashed_password="x", email="old@example.com")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}

    r = client.patch(f"/monitoring/patients/{pt.id}", json={"email": ""}, headers=headers)
    assert r.status_code == 200

    session.refresh(pt)
    assert pt.email is None


def test_two_patients_can_both_clear_email_without_unique_conflict(client: TestClient, session: Session):
    pt1 = Patient(hashed_password="x", email="a@example.com")
    pt1.name = "환자1"
    pt2 = Patient(hashed_password="x", email="b@example.com")
    pt2.name = "환자2"
    session.add(pt1)
    session.add(pt2)
    session.commit()
    session.refresh(pt1)
    session.refresh(pt2)

    for pt in (pt1, pt2):
        headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
        r = client.patch(f"/monitoring/patients/{pt.id}", json={"email": ""}, headers=headers)
        assert r.status_code == 200

    session.refresh(pt1)
    session.refresh(pt2)
    assert pt1.email is None
    assert pt2.email is None


def test_clearing_caregiver_email_to_empty_string_stores_none(client: TestClient, session: Session):
    cg = Caregiver(relation_type="guardian", email="old@example.com")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    headers = {"Authorization": f"Bearer {create_access_token(cg.id, 'caregiver')}"}

    r = client.patch(f"/monitoring/caregivers/{cg.id}", json={"email": ""}, headers=headers)
    assert r.status_code == 200

    session.refresh(cg)
    assert cg.email is None
