"""
test_login_lockout_and_password_reset.py — REQ-039 (2026-07-15 추가)

로그인 5회 연속 실패 시 계정 잠금 + 임시번호 자동 발송, 임시번호로 재설정 전용
로그인(verify) 후 새 비밀번호 설정(confirm)까지의 전체 흐름을 검증한다.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from core.database import get_session
from main import app
from models import Caregiver, PasswordResetCode
from routers.auth_router import MAX_FAILED_LOGIN_ATTEMPTS


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


@pytest.fixture(name="sent_codes")
def sent_codes_fixture(monkeypatch):
    """실제 이메일을 보내는 대신, 발송 시도된 (수신자, 임시번호)를 리스트로 가로챈다."""
    calls: list[tuple[str, str]] = []

    def _fake_send(to: str, code: str) -> None:
        calls.append((to, code))

    monkeypatch.setattr("routers.auth_router.send_password_reset_email", _fake_send)
    return calls


def _signup_caregiver(client: TestClient, email: str = "lockout@test.com", password: str = "correct-pw123") -> None:
    r = client.post(
        "/monitoring/caregivers",
        json={"name": "잠금테스트", "email": email, "password": password, "relation_type": "guardian"},
    )
    assert r.status_code == 200, r.text


class TestLoginLockout:
    def test_below_threshold_failures_do_not_lock(self, client: TestClient, session: Session, sent_codes):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS - 1):
            r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})
            assert r.status_code == 400
        assert sent_codes == []

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        assert caregiver.locked_at is None
        assert caregiver.failed_login_attempts == MAX_FAILED_LOGIN_ATTEMPTS - 1

    def test_reaching_threshold_locks_account_and_sends_reset_code(
        self, client: TestClient, session: Session, sent_codes
    ):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        assert caregiver.locked_at is not None
        assert caregiver.failed_login_attempts == MAX_FAILED_LOGIN_ATTEMPTS

        assert len(sent_codes) == 1
        assert sent_codes[0][0] == "lockout@test.com"

        reset_code_row = session.exec(
            select(PasswordResetCode).where(PasswordResetCode.subject_id == caregiver.id)
        ).first()
        assert reset_code_row is not None
        assert reset_code_row.used_at is None

    def test_locked_account_rejects_even_correct_password(self, client: TestClient, sent_codes):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})

        r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "correct-pw123"})
        assert r.status_code == 400

    def test_successful_login_resets_failed_attempts_counter(self, client: TestClient, session: Session, sent_codes):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS - 2):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})

        r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "correct-pw123"})
        assert r.status_code == 200

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        assert caregiver.failed_login_attempts == 0


class TestPasswordResetFlow:
    def test_full_flow_unlocks_account_and_changes_password(self, client: TestClient, session: Session, sent_codes):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})
        code = sent_codes[0][1]

        r = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": code})
        assert r.status_code == 200, r.text
        reset_token = r.json()["reset_token"]

        r = client.post(
            "/auth/password-reset/confirm", json={"reset_token": reset_token, "new_password": "brand-new-pw456"}
        )
        assert r.status_code == 200, r.text

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        assert caregiver.locked_at is None
        assert caregiver.failed_login_attempts == 0

        r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "brand-new-pw456"})
        assert r.status_code == 200

        # 옛 비밀번호로는 더 이상 로그인 불가
        r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "correct-pw123"})
        assert r.status_code == 400

    def test_code_is_single_use(self, client: TestClient, sent_codes):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})
        code = sent_codes[0][1]

        r1 = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": code})
        assert r1.status_code == 200

        r2 = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": code})
        assert r2.status_code == 400

    def test_wrong_code_rejected(self, client: TestClient, sent_codes):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})

        r = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": "000000"})
        assert r.status_code == 400

    def test_manual_request_for_unknown_identifier_returns_generic_message_and_sends_nothing(
        self, client: TestClient, sent_codes
    ):
        r = client.post("/auth/password-reset/request", json={"identifier": "nobody@test.com"})
        assert r.status_code == 200
        assert sent_codes == []

    def test_manual_request_for_known_identifier_sends_code_without_requiring_lock(
        self, client: TestClient, sent_codes
    ):
        _signup_caregiver(client)
        r = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        assert r.status_code == 200
        assert len(sent_codes) == 1

    def test_reset_token_cannot_be_used_as_access_token(self, client: TestClient, sent_codes, session: Session):
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})
        code = sent_codes[0][1]

        r = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": code})
        reset_token = r.json()["reset_token"]

        # get_current_actor가 요구하는 다른 보호된 엔드포인트에 reset_token을 access_token처럼 써보면 거부돼야 함
        r = client.post(
            "/auth/withdraw", json={"password": "correct-pw123"}, headers={"Authorization": f"Bearer {reset_token}"}
        )
        assert r.status_code == 401
