"""GET /monitoring/caregivers/{caregiver_id}/patients — PII 복호화 실패 방어 (2026-07-30 신규).

실제로 재현된 사고: 이 보호자가 관리하는 환자 여러 명 중 단 하나라도 다른
PII_ENCRYPTION_KEY로 암호화된 name_encrypted/phone_encrypted를 갖고 있으면(예: 팀원이
서로 다른 로컬 키로 만든 테스트 계정을 같은 보호자에게 실수로 연결), 그 환자를
PatientPublic으로 변환하는 시점에 InvalidToken이 터져서 목록 조회 자체가 500으로
죽고 나머지 정상 환자들도 전혀 안 보였다. 문제 있는 환자 하나만 건너뛰고 나머지는
정상 표시해야 한다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient
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
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _headers(caregiver_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(caregiver_id, 'caregiver')}"}


def test_patient_with_undecryptable_pii_is_skipped_not_500(client: TestClient, session: Session):
    cg = Caregiver(hashed_password="x")
    cg.name = "보호자"
    session.add(cg)
    session.commit()
    session.refresh(cg)

    good = Patient(hashed_password="x")
    good.name = "정상환자"
    session.add(good)

    broken = Patient(hashed_password="x")
    broken.name = "임시"  # 정상 키로 먼저 설정해서 property 초기화만 거치고
    session.add(broken)
    session.commit()
    session.refresh(good)
    session.refresh(broken)

    # .name setter를 우회해 다른 키로 암호화된 값을 직접 주입 — 실제 사고와 동일하게 재현.
    broken.name_encrypted = Fernet(Fernet.generate_key()).encrypt("깨진환자".encode()).decode()
    session.add(broken)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=good.id))
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=broken.id))
    session.commit()

    r = client.get(f"/monitoring/caregivers/{cg.id}/patients", headers=_headers(cg.id))

    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert names == ["정상환자"]
