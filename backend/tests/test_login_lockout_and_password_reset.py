"""
test_login_lockout_and_password_reset.py — REQ-039 (2026-07-15 추가)

로그인 5회 연속 실패 시 계정 잠금 + 임시번호 자동 발송, 임시번호로 재설정 전용
로그인(verify) 후 새 비밀번호 설정(confirm)까지의 전체 흐름을 검증한다.
"""
from datetime import datetime, timedelta

import pytest
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, PasswordResetCode
from routers.auth_router import (
    LOCKOUT_DURATION_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
    MAX_RESET_CODE_VERIFY_ATTEMPTS,
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

    def test_lockout_still_active_before_duration_elapses(self, client: TestClient, session: Session, sent_codes):
        """[2026-07-15 추가, PR #48 팀원 리뷰 반영] 자동 해제가 너무 일찍 풀리면 안 된다."""
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        caregiver.locked_at = datetime.now() - timedelta(minutes=LOCKOUT_DURATION_MINUTES - 1)
        session.add(caregiver)
        session.commit()

        r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "correct-pw123"})
        assert r.status_code == 400

    def test_lockout_auto_unlocks_after_duration_elapses(self, client: TestClient, session: Session, sent_codes):
        """[2026-07-15 추가, PR #48 팀원 리뷰 반영 — HIGH] 영구 잠금이면 (1) 이메일 없는
        계정은 복구 불가, (2) identifier만 아는 공격자가 비인증 DoS로 계정을 잠글 수
        있었다 — 유예시간이 지나면 자동으로 풀려서 정상 비밀번호로 다시 로그인돼야 한다."""
        _signup_caregiver(client)
        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "wrong"})

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        caregiver.locked_at = datetime.now() - timedelta(minutes=LOCKOUT_DURATION_MINUTES + 1)
        session.add(caregiver)
        session.commit()

        r = client.post("/auth/login", json={"identifier": "lockout@test.com", "password": "correct-pw123"})
        assert r.status_code == 200, r.text

        caregiver = session.exec(select(Caregiver).where(Caregiver.email == "lockout@test.com")).first()
        assert caregiver.locked_at is None
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


class TestResetCodeAccumulationAndBruteForce:
    """[2026-07-15 추가, PR #48 팀원 리뷰 반영 — CRITICAL] 재발급할 때마다 이전 코드가
    쌓여서 동시에 여러 개가 유효했고, verify에 시도 횟수 제한이 없어 브루트포스가
    가능했다. 재발급 시 이전 코드 무효화 + verify 시도 횟수 제한을 검증한다."""

    def test_reissuing_code_invalidates_previous_unused_code(self, client: TestClient, session: Session, sent_codes):
        _signup_caregiver(client)
        r = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        assert r.status_code == 200
        first_code = sent_codes[0][1]

        # 쿨다운 없이 바로 재발급되도록, 첫 코드의 발급 시각을 쿨다운 지난 과거로 돌린다
        from routers.auth_router import RESET_CODE_REQUEST_COOLDOWN_SECONDS

        codes = session.exec(select(PasswordResetCode)).all()
        for c in codes:
            c.created_at = datetime.now() - timedelta(seconds=RESET_CODE_REQUEST_COOLDOWN_SECONDS + 1)
            session.add(c)
        session.commit()

        r = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        assert r.status_code == 200
        assert len(sent_codes) == 2
        second_code = sent_codes[1][1]

        # 동시에 유효한 코드가 최대 1개만 있어야 한다 — 첫 코드는 더 이상 안 먹힌다
        r_old = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": first_code})
        assert r_old.status_code == 400

        r_new = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": second_code})
        assert r_new.status_code == 200, r_new.text

    def test_rapid_repeated_requests_within_cooldown_do_not_issue_a_new_code(
        self, client: TestClient, session: Session, sent_codes
    ):
        _signup_caregiver(client)
        r1 = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        assert r1.status_code == 200
        r2 = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        assert r2.status_code == 200

        # 쿨다운 안이라 두 번째 요청은 새 코드를 만들지 않았어야 한다(이메일도 재발송 안 됨)
        assert len(sent_codes) == 1
        codes = session.exec(select(PasswordResetCode)).all()
        assert len(codes) == 1

    def test_verify_attempts_are_capped_and_code_is_invalidated_after_max_attempts(
        self, client: TestClient, sent_codes
    ):
        _signup_caregiver(client)
        client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        real_code = sent_codes[0][1]

        for _ in range(MAX_RESET_CODE_VERIFY_ATTEMPTS):
            r = client.post(
                "/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": "000000"}
            )
            assert r.status_code == 400

        # 시도 횟수를 다 써서 코드가 무효화됐으니, 이제 정답 코드를 넣어도 거부돼야 한다
        r = client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": real_code})
        assert r.status_code == 400

    def test_burning_codes_via_verify_does_not_bypass_the_request_rate_limit(
        self, client: TestClient, session: Session, sent_codes
    ):
        """[2026-07-15 추가, 자체 검증 라운드 1 지적 반영] 쿨다운은 "아직 살아있는 코드가
        있을 때"만 막는다 — verify를 일부러 틀려 코드를 스스로 무효화시키면(위
        test_verify_attempts_are_capped...) 쿨다운을 우회해 계속 새 코드/이메일을 받을 수
        있었다. 발급된 코드 수 자체를 세는 진짜 요청 횟수 제한(MAX_RESET_CODE_REQUESTS_
        PER_WINDOW)이 이 우회를 막는지 검증한다."""
        _signup_caregiver(client)

        from routers.auth_router import MAX_RESET_CODE_REQUESTS_PER_WINDOW

        for _ in range(MAX_RESET_CODE_REQUESTS_PER_WINDOW):
            r = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
            assert r.status_code == 200
            # 코드를 스스로 무효화(잘못된 시도 소진)해서 다음 request의 쿨다운 체크를 우회.
            # attempts >= MAX가 "그다음" 호출에서 무효화시키므로, 실제로 무효화되려면
            # MAX번이 아니라 MAX+1번 틀려야 한다(verify_password_reset의 체크 순서 참고).
            for _ in range(MAX_RESET_CODE_VERIFY_ATTEMPTS + 1):
                client.post("/auth/password-reset/verify", json={"identifier": "lockout@test.com", "code": "000000"})

        codes_before = len(session.exec(select(PasswordResetCode)).all())
        assert codes_before == MAX_RESET_CODE_REQUESTS_PER_WINDOW

        # 한도를 다 썼으니, 코드를 또 무효화한 뒤에도 더 이상 새 코드가 발급되면 안 된다
        r = client.post("/auth/password-reset/request", json={"identifier": "lockout@test.com"})
        assert r.status_code == 200  # 계정 존재 여부를 숨기려고 응답 자체는 항상 200
        assert len(session.exec(select(PasswordResetCode)).all()) == codes_before  # 새로 안 만들어짐
        assert len(sent_codes) == MAX_RESET_CODE_REQUESTS_PER_WINDOW  # 이메일도 추가 발송 안 됨
