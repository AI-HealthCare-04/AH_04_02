"""
test_auth_signup_login.py — 회원가입→로그인 흐름, 중복가입, 잘못된 비밀번호 (2026-07-14 추가)

여러 로컬 환경이 공통 DB를 쓰도록 정리하면서 "가입한 계정으로 같은 DB에서 로그인되는지"가
핵심 요구사항이었다 — 이 테스트들이 그 계약을 명시적으로 고정한다.
"""
import pytest
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from routers.auth_router import MAX_FAILED_LOGIN_ATTEMPTS
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


def test_signup_then_login_succeeds_in_same_db(client: TestClient):
    r = client.post(
        "/monitoring/patients", json={"name": "환자1", "email": "patient1@test.com", "password": "pw123456"}
    )
    assert r.status_code == 200

    r2 = client.post("/auth/login", json={"identifier": "patient1@test.com", "password": "pw123456"})
    assert r2.status_code == 200
    assert r2.json()["role"] == "patient"
    assert "access_token" in r2.json()


class TestAuthFlow:
    def test_signup_normalizes_and_login_with_different_case_whitespace_succeeds(self, client: TestClient):
        r = client.post(
            "/monitoring/caregivers",
            json={"name": "보호자1", "email": " Guardian@Test.COM ", "password": "pw123456", "relation_type": "guardian"},
        )
        assert r.status_code == 200
        assert r.json()["email"] == "guardian@test.com"  # 정규화되어 저장됨

        r2 = client.post("/auth/login", json={"identifier": "guardian@test.com", "password": "pw123456"})
        assert r2.status_code == 200
        assert r2.json()["role"] == "caregiver"

        # 가입 때 쓴 원본 표기(공백/대문자)로도 로그인돼야 한다
        r3 = client.post("/auth/login", json={"identifier": " Guardian@Test.COM ", "password": "pw123456"})
        assert r3.status_code == 200

    def test_login_wrong_password_fails_with_generic_message(self, client: TestClient):
        client.post(
            "/monitoring/patients", json={"name": "환자2", "email": "patient2@test.com", "password": "correct-pw"}
        )
        r = client.post("/auth/login", json={"identifier": "patient2@test.com", "password": "wrong-pw"})
        assert r.status_code == 400
        assert "올바르지 않습니다" in r.json()["detail"]

    def test_login_nonexistent_identifier_fails_with_same_generic_message(self, client: TestClient):
        r = client.post("/auth/login", json={"identifier": "nobody@test.com", "password": "whatever"})
        assert r.status_code == 400
        assert "올바르지 않습니다" in r.json()["detail"]

    def test_duplicate_patient_signup_rejected_with_409(self, client: TestClient):
        r1 = client.post(
            "/monitoring/patients", json={"name": "환자3", "email": "dup@test.com", "password": "pw123456"}
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/monitoring/patients", json={"name": "환자3-again", "email": "dup@test.com", "password": "pw654321"}
        )
        assert r2.status_code == 409

    def test_duplicate_patient_signup_rejected_even_with_different_case(self, client: TestClient):
        r1 = client.post(
            "/monitoring/patients", json={"name": "환자4", "email": "casedup@test.com", "password": "pw123456"}
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/monitoring/patients", json={"name": "환자4-again", "email": " CaseDup@Test.com ", "password": "pw654321"}
        )
        assert r2.status_code == 409

    def test_duplicate_caregiver_signup_rejected_with_409(self, client: TestClient):
        r1 = client.post(
            "/monitoring/caregivers",
            json={"name": "보호자2", "email": "cgdup@test.com", "password": "pw123456", "relation_type": "guardian"},
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/monitoring/caregivers",
            json={"name": "보호자2-again", "email": "cgdup@test.com", "password": "pw654321", "relation_type": "guardian"},
        )
        assert r2.status_code == 409

    def test_removed_dead_signup_endpoint_returns_404(self, client: TestClient):
        """[2026-07-14] POST /auth/signup는 monitoring_router.py와 중복되는 죽은 코드라 제거함."""
        r = client.post("/auth/signup", json={"email": "x@test.com", "password": "pw", "name": "x"})
        assert r.status_code == 404

    def test_caregiver_signup_rejects_relation_type_outside_guardian_or_organization(self, client: TestClient):
        """[2026-07-16 추가] relation_type이 그냥 VARCHAR라 검증 없이는 임의 값이 저장됐다 —
        실제로 프론트가 보내는 값(guardian/organization)만 허용하도록 Literal 검증 추가."""
        r = client.post(
            "/monitoring/caregivers",
            json={
                "name": "잘못된값테스트",
                "email": "badrole@test.com",
                "password": "pw123456",
                "relation_type": "life_support_worker",
            },
        )
        assert r.status_code == 422

    def test_caregiver_signup_accepts_organization_relation_type(self, client: TestClient):
        r = client.post(
            "/monitoring/caregivers",
            json={
                "name": "행복요양원",
                "email": "org-ok@test.com",
                "password": "pw123456",
                "relation_type": "organization",
            },
        )
        assert r.status_code == 200
        assert r.json()["relation_type"] == "organization"

    def test_repeated_correct_login_to_one_role_does_not_lock_sibling_account_same_phone(
        self, client: TestClient
    ):
        """[2026-07-22 추가, 팀원 리뷰 반영 — HIGH 회귀 테스트] 전화번호가 이제 역할(관계)당
        유니크라 같은 사람이 환자 본인 계정과 보호자 계정을 같은 전화번호로 가질 수 있다.
        login()이 후보를 순회하며 비밀번호를 확인하는 과정에서, 대상이 아닌 형제 계정까지
        "비밀번호가 안 맞다"는 이유로 실패 횟수를 올리면 안 된다 — 환자 계정에 정확한
        비밀번호로 여러 번 로그인해도 형제 보호자 계정은 절대 잠기면 안 된다."""
        phone = "010-9999-0000"
        r = client.post(
            "/monitoring/patients",
            json={"name": "환자", "phone": phone, "password": "patientpw123"},
        )
        assert r.status_code == 200

        r = client.post(
            "/monitoring/caregivers",
            json={"name": "보호자", "phone": phone, "password": "guardianpw123", "relation_type": "guardian"},
        )
        assert r.status_code == 200

        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            r = client.post("/auth/login", json={"identifier": phone, "password": "patientpw123"})
            assert r.status_code == 200
            assert r.json()["role"] == "patient"

        # 형제 보호자 계정은 한 번도 잘못된 비밀번호로 시도된 적이 없으므로 여전히
        # 자기 비밀번호로 정상 로그인할 수 있어야 한다 (잠겨있으면 400이 난다).
        r = client.post("/auth/login", json={"identifier": phone, "password": "guardianpw123"})
        assert r.status_code == 200
        assert r.json()["role"] == "caregiver"
