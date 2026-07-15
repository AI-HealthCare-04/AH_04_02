"""
test_account_withdrawal.py — REQ-035 (2026-07-15 추가)

탈퇴 요청(즉시 비활성화 + 30일 뒤 삭제 예약) → 로그인 차단 → 30일 이내 취소 흐름을 검증한다.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from core.database import get_session
from main import app
from models import Patient, PrivacyPurgeAudit


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


def _signup_and_login(client: TestClient, email: str = "withdraw@test.com", password: str = "pw123456") -> str:
    r = client.post("/monitoring/patients", json={"name": "탈퇴테스트", "email": email, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestWithdrawRequest:
    def test_withdraw_wrong_password_rejected(self, client: TestClient):
        token = _signup_and_login(client)
        r = client.post("/auth/withdraw", json={"password": "wrong"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_withdraw_requires_auth(self, client: TestClient):
        r = client.post("/auth/withdraw", json={"password": "pw123456"})
        assert r.status_code == 401  # Authorization 헤더 자체가 없으면 인증 실패

    def test_withdraw_deactivates_and_schedules_purge_and_creates_pending_audit(
        self, client: TestClient, session: Session
    ):
        token = _signup_and_login(client)
        r = client.post(
            "/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text

        patient = session.exec(select(Patient).where(Patient.email == "withdraw@test.com")).first()
        assert patient.deactivated_at is not None
        assert patient.deletion_scheduled_at is not None
        assert patient.deletion_scheduled_at > patient.deactivated_at + timedelta(days=29)

        audit = session.exec(select(PrivacyPurgeAudit).where(PrivacyPurgeAudit.subject_id == patient.id)).first()
        assert audit is not None
        assert audit.status == "pending"

    def test_double_withdraw_rejected(self, client: TestClient):
        """[2026-07-15 갱신, PR #48 팀원 리뷰 반영] 탈퇴 후 같은 access_token은 이제
        get_current_actor 단계에서 바로 401로 막힌다(예전엔 핸들러까지 도달해 400)."""
        token = _signup_and_login(client)
        r1 = client.post(
            "/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert r2.status_code == 401

    def test_refresh_token_rejected_after_withdraw(self, client: TestClient):
        """[2026-07-15 추가, PR #48 팀원 리뷰 반영 — HIGH] 탈퇴 후에도 refresh_token
        쿠키로 새 access_token을 계속 발급받을 수 있던 문제."""
        token = _signup_and_login(client)  # 로그인 응답의 Set-Cookie가 client 쿠키 저장소에 남음
        client.post("/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"})

        r = client.get("/auth/token/refresh")
        assert r.status_code == 401

    def test_login_blocked_after_withdraw(self, client: TestClient):
        token = _signup_and_login(client)
        client.post("/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"})

        r = client.post("/auth/login", json={"identifier": "withdraw@test.com", "password": "pw123456"})
        assert r.status_code == 400


class TestWithdrawCancel:
    def test_cancel_wrong_password_rejected(self, client: TestClient):
        token = _signup_and_login(client)
        client.post("/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"})

        r = client.post(
            "/auth/withdraw/cancel", json={"identifier": "withdraw@test.com", "password": "wrong"}
        )
        assert r.status_code == 400

    def test_cancel_when_not_withdrawn_rejected(self, client: TestClient):
        _signup_and_login(client)
        r = client.post(
            "/auth/withdraw/cancel", json={"identifier": "withdraw@test.com", "password": "pw123456"}
        )
        assert r.status_code == 400

    def test_cancel_within_grace_period_restores_login_and_marks_audit_cancelled(
        self, client: TestClient, session: Session
    ):
        token = _signup_and_login(client)
        client.post("/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"})

        r = client.post(
            "/auth/withdraw/cancel", json={"identifier": "withdraw@test.com", "password": "pw123456"}
        )
        assert r.status_code == 200, r.text

        patient = session.exec(select(Patient).where(Patient.email == "withdraw@test.com")).first()
        assert patient.deactivated_at is None
        assert patient.deletion_scheduled_at is None

        audit = session.exec(select(PrivacyPurgeAudit).where(PrivacyPurgeAudit.subject_id == patient.id)).first()
        assert audit.status == "cancelled"  # 취소돼도 감사기록 자체는 삭제하지 않고 보존

        r = client.post("/auth/login", json={"identifier": "withdraw@test.com", "password": "pw123456"})
        assert r.status_code == 200

    def test_cancel_after_deadline_rejected(self, client: TestClient, session: Session):
        token = _signup_and_login(client)
        client.post("/auth/withdraw", json={"password": "pw123456"}, headers={"Authorization": f"Bearer {token}"})

        # 유예기간이 이미 지난 것처럼 시각을 강제로 되돌린다
        patient = session.exec(select(Patient).where(Patient.email == "withdraw@test.com")).first()
        patient.deactivated_at = datetime.now() - timedelta(days=31)
        patient.deletion_scheduled_at = datetime.now() - timedelta(days=1)
        session.add(patient)
        session.commit()

        r = client.post(
            "/auth/withdraw/cancel", json={"identifier": "withdraw@test.com", "password": "pw123456"}
        )
        assert r.status_code == 400
