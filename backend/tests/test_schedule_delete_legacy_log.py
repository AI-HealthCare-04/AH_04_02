"""
test_schedule_delete_legacy_log.py — DELETE /monitoring/schedules/{id}가 레거시
MedicationLog까지 정리하는지 검증 (2026-07-23 추가, PR#71 리뷰 반영)

medication_logs → medication_records 이관(849bd15b19a5) 이후로 새 MedicationLog는
더 이상 생성되지 않지만, 이관 이전부터 있던 오래된 일정에는 여전히 MedicationLog 행이
남아있을 수 있다. delete_schedule()이 MedicationRecord/NotificationLog만 정리하고
MedicationLog는 건드리지 않아 이런 일정을 지우면 FK 위반(500)이 났다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import MedicationLog, MedicationSchedule, Patient
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


def _headers(patient_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(patient_id, 'patient')}"}


def test_delete_schedule_with_legacy_medication_log_does_not_500(client: TestClient, session: Session):
    pt = Patient(hashed_password="x")
    session.add(pt)
    session.commit()
    session.refresh(pt)

    sched = MedicationSchedule(patient_id=pt.id, drug_name="암로디핀정5mg", time_slot="09:00")
    session.add(sched)
    session.commit()
    session.refresh(sched)

    # 이관 이전 데이터를 흉내: 이 일정을 참조하는 레거시 MedicationLog 행
    session.add(MedicationLog(schedule_id=sched.id, status="taken"))
    session.commit()

    r = client.delete(f"/monitoring/schedules/{sched.id}", headers=_headers(pt.id))
    assert r.status_code == 200
    assert session.get(MedicationSchedule, sched.id) is None
