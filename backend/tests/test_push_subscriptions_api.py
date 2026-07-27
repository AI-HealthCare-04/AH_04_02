"""GET /push/vapid-public-key, POST/DELETE /push-subscriptions 테스트 (2026-07-24 신규).

구독 생성/갱신/삭제가 로그인한 본인 계정(recipient_role/recipient_id)에만 묶이는지,
같은 endpoint로 다시 POST하면 새 행이 아니라 기존 행이 갱신되는지 검증한다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, Patient, PushSubscription
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
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _caregiver(session: Session) -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _headers(subject_id: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject_id, role)}"}


def test_vapid_public_key_is_public_and_reflects_config(client: TestClient, monkeypatch):
    from core import push

    monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "test-key")
    r = client.get("/push/vapid-public-key")
    assert r.status_code == 200
    assert r.json() == {"public_key": "test-key"}


def test_create_subscription_requires_auth(client: TestClient):
    r = client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "a", "auth": "b"},
    )
    assert r.status_code == 401


def test_create_subscription_stores_for_current_actor(client: TestClient, session: Session):
    pt = _patient(session)

    r = client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "a", "auth": "b"},
        headers=_headers(pt.id, "patient"),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "created"

    subs = session.exec(select(PushSubscription)).all()
    assert len(subs) == 1
    assert subs[0].recipient_role == "patient"
    assert subs[0].recipient_id == pt.id


def test_create_subscription_with_same_endpoint_updates_instead_of_duplicating(
    client: TestClient, session: Session
):
    pt = _patient(session)
    headers = _headers(pt.id, "patient")
    client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "old", "auth": "old"},
        headers=headers,
    )

    r = client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "new", "auth": "new"},
        headers=headers,
    )

    assert r.status_code == 200
    assert r.json()["status"] == "updated"
    subs = session.exec(select(PushSubscription)).all()
    assert len(subs) == 1
    assert subs[0].p256dh == "new"


def test_caregiver_and_patient_can_share_same_endpoint_string(client: TestClient, session: Session):
    """endpoint 유니크 제약은 (role, id, endpoint) 조합이라, 같은 endpoint 문자열이라도
    역할/계정이 다르면 별개 구독으로 취급돼야 한다(현실적으론 안 겹치겠지만 방어적으로)."""
    pt = _patient(session)
    cg = _caregiver(session)
    same_endpoint = "https://push.example.com/shared"

    client.post(
        "/push-subscriptions",
        json={"endpoint": same_endpoint, "p256dh": "a", "auth": "b"},
        headers=_headers(pt.id, "patient"),
    )
    r = client.post(
        "/push-subscriptions",
        json={"endpoint": same_endpoint, "p256dh": "c", "auth": "d"},
        headers=_headers(cg.id, "caregiver"),
    )

    assert r.status_code == 200
    assert r.json()["status"] == "created"
    assert len(session.exec(select(PushSubscription)).all()) == 2


def test_delete_subscription_removes_own(client: TestClient, session: Session):
    pt = _patient(session)
    headers = _headers(pt.id, "patient")
    client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "a", "auth": "b"},
        headers=headers,
    )

    r = client.request(
        "DELETE", "/push-subscriptions", params={"endpoint": "https://push.example.com/1"}, headers=headers
    )

    assert r.status_code == 200
    assert session.exec(select(PushSubscription)).all() == []


def test_delete_subscription_does_not_remove_other_accounts(client: TestClient, session: Session):
    pt = _patient(session)
    other = _patient(session)
    client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "a", "auth": "b"},
        headers=_headers(pt.id, "patient"),
    )

    r = client.request(
        "DELETE",
        "/push-subscriptions",
        params={"endpoint": "https://push.example.com/1"},
        headers=_headers(other.id, "patient"),
    )

    assert r.status_code == 200
    assert len(session.exec(select(PushSubscription)).all()) == 1


def test_delete_nonexistent_subscription_is_a_noop(client: TestClient, session: Session):
    pt = _patient(session)
    r = client.request(
        "DELETE",
        "/push-subscriptions",
        params={"endpoint": "https://push.example.com/never-registered"},
        headers=_headers(pt.id, "patient"),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
