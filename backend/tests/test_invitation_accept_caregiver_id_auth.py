"""[2026-07-22 추가, 팀원 리뷰(fkmc10101-hub) 지적 반영 — HIGH 회귀 테스트]

POST /invitations/{token}/accept는 계정이 없는 사람도 써야 해서 인증을 강제하지 않는
공개 엔드포인트다. 하지만 payload.caregiver_id(이미 로그인한 계정으로 그대로 수락)를
아무 검증 없이 신뢰하면, 초대 토큰만 가진 누구나 임의의 caregiver_id를 넣어 그 계정을
남의 환자에 연결시킬 수 있었다(실제 재현: 완전 비인증 상태로 성공). 이제
get_current_caregiver_optional로 payload.caregiver_id가 실제 로그인된 그 계정인지
검증한다.
"""
import pytest
from conftest import make_test_engine
from core.database import get_session
from core.security import hash_token
from fastapi.testclient import TestClient
from main import app
from models import Invitation
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


def _make_pending_guardian_invitation(session: Session, token: str, patient_id: int) -> Invitation:
    """PR#65로 신규 생성 경로 자체가 삭제된 "환자→보호자류" 초대를, 그 이전부터 이미
    pending 상태로 남아있던 legacy 데이터처럼 직접 만든다(공유 dev DB에 실제로 이런
    데이터가 있다)."""
    invitation = Invitation(patient_id=patient_id, relation_type="guardian", token_hash=hash_token(token), status="pending")
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return invitation


def test_unauthenticated_request_cannot_spoof_caregiver_id(client: TestClient, session: Session):
    victim = client.post(
        "/monitoring/caregivers",
        json={"name": "피해자", "email": "victim@test.com", "password": "victimpw123", "relation_type": "guardian"},
    ).json()
    patient = client.post(
        "/monitoring/patients", json={"name": "환자", "email": "atk-patient@test.com", "password": "pw123456"}
    ).json()
    _make_pending_guardian_invitation(session, "attack-token", patient["id"])

    r = client.post("/invitations/attack-token/accept", json={"caregiver_id": victim["id"]})
    assert r.status_code == 403


def test_authenticated_as_a_different_caregiver_cannot_spoof_another_caregivers_id(
    client: TestClient, session: Session
):
    victim = client.post(
        "/monitoring/caregivers",
        json={"name": "피해자2", "email": "victim2@test.com", "password": "victimpw123", "relation_type": "guardian"},
    ).json()
    client.post(
        "/monitoring/caregivers",
        json={"name": "공격자", "email": "attacker@test.com", "password": "attackerpw123", "relation_type": "guardian"},
    )
    attacker_token = client.post(
        "/auth/login", json={"identifier": "attacker@test.com", "password": "attackerpw123"}
    ).json()["access_token"]
    patient = client.post(
        "/monitoring/patients", json={"name": "환자2", "email": "atk-patient2@test.com", "password": "pw123456"}
    ).json()
    _make_pending_guardian_invitation(session, "attack-token-2", patient["id"])

    r = client.post(
        "/invitations/attack-token-2/accept",
        json={"caregiver_id": victim["id"]},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert r.status_code == 403


def test_authenticated_as_the_matching_caregiver_can_accept_with_own_id(client: TestClient, session: Session):
    caregiver = client.post(
        "/monitoring/caregivers",
        json={"name": "진짜보호자", "email": "real@test.com", "password": "realpw123", "relation_type": "guardian"},
    ).json()
    token = client.post("/auth/login", json={"identifier": "real@test.com", "password": "realpw123"}).json()[
        "access_token"
    ]
    patient = client.post(
        "/monitoring/patients", json={"name": "환자3", "email": "patient3@test.com", "password": "pw123456"}
    ).json()
    _make_pending_guardian_invitation(session, "legit-token", patient["id"])

    r = client.post(
        "/invitations/legit-token/accept",
        json={"caregiver_id": caregiver["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["caregiver_id"] == caregiver["id"]
