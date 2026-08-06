"""test_invitation_accept_existing_patient.py — 보호자/기관 → 환자 초대(relation_type="patient")를
이미 계정이 있는 환자가 로그인한 채로 수락하는 경로 검증 (2026-07-23 추가).

이전엔 이 종류의 초대를 수락하면 무조건 새 환자 계정을 만들었다 — 초대받은 사람이 이미
계정이 있어도 이름/이메일/비밀번호/전화번호를 다시 입력해 중복 계정을 만들어야 했다.
이제 로그인된 환자 본인 토큰 + payload.patient_id로 수락하면 새 계정을 만들지 않고 그
계정을 초대한 보호자에게 그대로 연결한다.
"""
import pytest
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Patient
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


def _signup_and_login_caregiver(client: TestClient, email: str) -> tuple[int, str]:
    caregiver = client.post(
        "/monitoring/caregivers",
        json={"name": "행복요양원", "email": email, "password": "caregiverpw123", "relation_type": "guardian"},
    ).json()
    token = client.post("/auth/login", json={"identifier": email, "password": "caregiverpw123"}).json()["access_token"]
    return caregiver["id"], token


def _signup_and_login_patient(client: TestClient, email: str) -> tuple[int, str]:
    patient = client.post(
        "/monitoring/patients", json={"name": "환자", "email": email, "password": "patientpw123"}
    ).json()
    token = client.post("/auth/login", json={"identifier": email, "password": "patientpw123"}).json()["access_token"]
    return patient["id"], token


def test_existing_patient_accepts_without_creating_a_new_account(client: TestClient, session: Session):
    caregiver_id, caregiver_token = _signup_and_login_caregiver(client, "org1@test.com")
    patient_id, patient_token = _signup_and_login_patient(client, "patient1@test.com")

    invite = client.post(
        "/invitations",
        json={"relation_type": "patient", "inviter_caregiver_id": caregiver_id},
        headers={"Authorization": f"Bearer {caregiver_token}"},
    ).json()

    r = client.post(
        f"/invitations/{invite['token']}/accept",
        json={"patient_id": patient_id},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"patient_id": patient_id, "status": "accepted"}

    all_patients = session.exec(select(Patient)).all()
    assert len(all_patients) == 1  # 새 계정이 만들어지지 않았어야 함

    linked = client.get(
        f"/monitoring/patients/{patient_id}/caregivers",
        headers={"Authorization": f"Bearer {patient_token}"},
    ).json()
    assert any(c["id"] == caregiver_id for c in linked)

    # [2026-07-24 추가] 초대를 보낸 보호자 쪽에도 "연결됐다" 알림이 남아야 한다.
    notices = client.get(
        "/trust/relations/notices", headers={"Authorization": f"Bearer {caregiver_token}"}
    ).json()
    assert len(notices) == 1
    assert notices[0]["event"] == "linked"
    assert notices[0]["patient_id"] == patient_id


def test_cannot_accept_with_someone_elses_patient_id(client: TestClient, session: Session):
    caregiver_id, caregiver_token = _signup_and_login_caregiver(client, "org2@test.com")
    _victim_id, _ = _signup_and_login_patient(client, "victim@test.com")
    _attacker_id, attacker_token = _signup_and_login_patient(client, "attacker@test.com")

    invite = client.post(
        "/invitations",
        json={"relation_type": "patient", "inviter_caregiver_id": caregiver_id},
        headers={"Authorization": f"Bearer {caregiver_token}"},
    ).json()

    r = client.post(
        f"/invitations/{invite['token']}/accept",
        json={"patient_id": _victim_id},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert r.status_code == 403


def test_cannot_accept_with_patient_id_while_unauthenticated(client: TestClient, session: Session):
    caregiver_id, caregiver_token = _signup_and_login_caregiver(client, "org3@test.com")
    patient_id, _ = _signup_and_login_patient(client, "patient3@test.com")

    invite = client.post(
        "/invitations",
        json={"relation_type": "patient", "inviter_caregiver_id": caregiver_id},
        headers={"Authorization": f"Bearer {caregiver_token}"},
    ).json()

    r = client.post(f"/invitations/{invite['token']}/accept", json={"patient_id": patient_id})
    assert r.status_code == 403
