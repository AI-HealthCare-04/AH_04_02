"""[2026-07-22 추가, 팀원 리뷰(fkmc10101-hub) 지적 반영 — HIGH 재설계]

계정 전환 기능이 refresh_token(14일)을 응답 body/localStorage에 그대로 노출하던 것을
httpOnly 쿠키(switch_{role}_{subject_id}) 기반으로 다시 설계했다. 이 테스트는 그
계약을 고정한다: 응답 body에 refresh_token이 없는지, 쿠키 없이는 전환이 안 되는지,
"remember_device" 체크 여부에 따라 쿠키가 심어지는지, 회전·거절·삭제가 제대로
동작하는지 확인한다.
"""
import pytest
from conftest import make_test_engine
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
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


def _signup_patient(client: TestClient) -> None:
    r = client.post(
        "/monitoring/patients", json={"name": "환자", "email": "switch-patient@test.com", "password": "pw123456"}
    )
    assert r.status_code == 200, r.text


def test_login_response_never_contains_refresh_token(client: TestClient):
    _signup_patient(client)
    r = client.post(
        "/auth/login",
        json={"identifier": "switch-patient@test.com", "password": "pw123456", "remember_device": True},
    )
    assert r.status_code == 200
    assert "refresh_token" not in r.json()


def test_remember_device_false_does_not_set_switch_cookie(client: TestClient):
    _signup_patient(client)
    r = client.post(
        "/auth/login",
        json={"identifier": "switch-patient@test.com", "password": "pw123456", "remember_device": False},
    )
    subject_id = r.json()["caregiver_id"]
    assert f"switch_patient_{subject_id}" not in client.cookies

    r2 = client.post("/auth/switch", json={"role": "patient", "subject_id": subject_id})
    assert r2.status_code == 401


def test_remember_device_true_allows_switching_without_password(client: TestClient):
    _signup_patient(client)
    r = client.post(
        "/auth/login",
        json={"identifier": "switch-patient@test.com", "password": "pw123456", "remember_device": True},
    )
    subject_id = r.json()["caregiver_id"]
    assert f"switch_patient_{subject_id}" in client.cookies

    r2 = client.post("/auth/switch", json={"role": "patient", "subject_id": subject_id})
    assert r2.status_code == 200
    assert r2.json()["role"] == "patient"
    assert "refresh_token" not in r2.json()
    assert r2.json()["access_token"]


def test_switch_with_wrong_subject_id_is_rejected(client: TestClient):
    _signup_patient(client)
    client.post(
        "/auth/login",
        json={"identifier": "switch-patient@test.com", "password": "pw123456", "remember_device": True},
    )
    r = client.post("/auth/switch", json={"role": "patient", "subject_id": 999999})
    assert r.status_code == 401


def test_switch_rotates_and_old_cookie_value_cannot_be_reused(client: TestClient):
    _signup_patient(client)
    r = client.post(
        "/auth/login",
        json={"identifier": "switch-patient@test.com", "password": "pw123456", "remember_device": True},
    )
    subject_id = r.json()["caregiver_id"]
    old_cookie_value = client.cookies[f"switch_patient_{subject_id}"]

    r2 = client.post("/auth/switch", json={"role": "patient", "subject_id": subject_id})
    assert r2.status_code == 200

    # Replay the OLD (now-revoked) cookie value directly.
    client.cookies.set(f"switch_patient_{subject_id}", old_cookie_value)
    r3 = client.post("/auth/switch", json={"role": "patient", "subject_id": subject_id})
    assert r3.status_code == 401


def test_forget_switch_account_removes_the_cookie(client: TestClient):
    _signup_patient(client)
    r = client.post(
        "/auth/login",
        json={"identifier": "switch-patient@test.com", "password": "pw123456", "remember_device": True},
    )
    subject_id = r.json()["caregiver_id"]
    assert f"switch_patient_{subject_id}" in client.cookies

    r2 = client.post("/auth/switch/forget", json={"role": "patient", "subject_id": subject_id})
    assert r2.status_code == 200
    assert f"switch_patient_{subject_id}" not in client.cookies

    r3 = client.post("/auth/switch", json={"role": "patient", "subject_id": subject_id})
    assert r3.status_code == 401
