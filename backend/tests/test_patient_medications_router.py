"""
test_patient_medications_router.py — /patients/{patient_id}/medications 등 신규 API 테스트 (2026-07-14 추가)
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
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
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _make_patient(session: Session, name: str = "환자") -> Patient:
    p = Patient(hashed_password="x")
    p.name = name
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _make_caregiver(session: Session, name: str = "보호자") -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _link(session: Session, cg: Caregiver, pt: Patient) -> None:
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    session.commit()


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


def _auth(subject_id: int, role: str) -> dict:
    return {"Authorization": f"Bearer {_token(subject_id, role)}"}


class TestCreateMedication:
    def test_owner_patient_can_register_medication(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        r = client.post(
            f"/patients/{pt.id}/medications",
            json={"medication_name": "암로디핀정5밀리그램", "source_type": "manual"},
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 200
        assert r.json()["medication_name"] == "암로디핀정5밀리그램"
        assert r.json()["verification_status"] == "user_confirmed"  # manual 기본값

    def test_owner_caregiver_can_register_medication_for_linked_patient(self, client: TestClient, session: Session):
        cg = _make_caregiver(session)
        pt = _make_patient(session)
        _link(session, cg, pt)
        r = client.post(
            f"/patients/{pt.id}/medications",
            json={"medication_name": "메트포르민"},
            headers=_auth(cg.id, "caregiver"),
        )
        assert r.status_code == 200

    def test_unauthenticated_registration_fails(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        r = client.post(f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"})
        assert r.status_code in (401, 403)

    def test_other_patient_cannot_register_for_someone_else(self, client: TestClient, session: Session):
        pt = _make_patient(session, "환자A")
        other = _make_patient(session, "환자B")
        r = client.post(
            f"/patients/{pt.id}/medications",
            json={"medication_name": "암로디핀"},
            headers=_auth(other.id, "patient"),
        )
        assert r.status_code == 403

    def test_ai_ocr_source_defaults_to_unverified_and_preserves_raw_text(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        r = client.post(
            f"/patients/{pt.id}/medications",
            json={
                "medication_name": "메트포르민",
                "source_type": "prescription_ocr",
                "source_raw_text": "메트포르민 500mg (OCR 원문)",
            },
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 200
        assert r.json()["verification_status"] == "unverified"
        assert r.json()["source_raw_text"] == "메트포르민 500mg (OCR 원문)"

    def test_unmatched_drug_master_leaves_drug_id_and_item_seq_null(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        r = client.post(
            f"/patients/{pt.id}/medications",
            json={"medication_name": "유사약품X", "source_type": "api_search"},
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 200
        assert r.json()["drug_id"] is None
        assert r.json()["item_seq"] is None


class TestGetAndListMedications:
    def test_other_patient_gets_404_for_someone_elses_medication_id(self, client: TestClient, session: Session):
        pt = _make_patient(session, "환자A")
        other = _make_patient(session, "환자B")
        med_id = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        ).json()["id"]

        # other가 자기 자신의 patient_id 경로로 A의 medication_id를 조회 -> 404 (소유권 없음)
        r = client.get(f"/patients/{other.id}/medications/{med_id}", headers=_auth(other.id, "patient"))
        assert r.status_code == 404

    def test_other_patient_gets_403_via_actor_access_check(self, client: TestClient, session: Session):
        pt = _make_patient(session, "환자A")
        other = _make_patient(session, "환자B")
        med_id = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        ).json()["id"]

        # other가 A의 patient_id 경로 자체로 접근 -> 403 (본인 아님)
        r = client.get(f"/patients/{pt.id}/medications/{med_id}", headers=_auth(other.id, "patient"))
        assert r.status_code == 403


class TestUpdateAndDeleteMedication:
    def test_update_medication_name_does_not_overwrite_source_raw_text(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        med_id = client.post(
            f"/patients/{pt.id}/medications",
            json={"medication_name": "메트포르민", "source_type": "prescription_ocr", "source_raw_text": "OCR 원문 그대로"},
            headers=_auth(pt.id, "patient"),
        ).json()["id"]

        r = client.patch(
            f"/patients/{pt.id}/medications/{med_id}",
            json={"medication_name": "메트포르민(사용자 확인)", "verification_status": "user_confirmed"},
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 200
        assert r.json()["medication_name"] == "메트포르민(사용자 확인)"
        assert r.json()["source_raw_text"] == "OCR 원문 그대로"  # AI 원문은 절대 덮어쓰지 않음

    def test_soft_delete_hides_from_list_and_get(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        med_id = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        ).json()["id"]

        r = client.delete(f"/patients/{pt.id}/medications/{med_id}", headers=_auth(pt.id, "patient"))
        assert r.status_code == 200

        r_get = client.get(f"/patients/{pt.id}/medications/{med_id}", headers=_auth(pt.id, "patient"))
        assert r_get.status_code == 404

        r_list = client.get(f"/patients/{pt.id}/medications", headers=_auth(pt.id, "patient"))
        assert r_list.json() == []


class TestSchedulesAndRecords:
    def test_create_schedule_for_medication(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        med_id = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        ).json()["id"]

        r = client.post(
            f"/patients/{pt.id}/medications/{med_id}/schedules",
            json={"time_slot": "08:00", "meal_relation": "식후", "days_of_week": ["mon", "wed", "fri"]},
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 200
        assert r.json()["time_slot"] == "08:00"
        assert r.json()["days_of_week"] == ["mon", "wed", "fri"]

    def test_create_and_list_medication_records(self, client: TestClient, session: Session):
        pt = _make_patient(session)
        med_id = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        ).json()["id"]
        schedule_id = client.post(
            f"/patients/{pt.id}/medications/{med_id}/schedules",
            json={"time_slot": "08:00"},
            headers=_auth(pt.id, "patient"),
        ).json()["id"]

        r = client.post(
            f"/patients/{pt.id}/medication-records",
            json={"patient_medication_id": med_id, "schedule_id": schedule_id, "status": "taken"},
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 200

        r_list = client.get(f"/patients/{pt.id}/medication-records", headers=_auth(pt.id, "patient"))
        assert r_list.status_code == 200
        assert len(r_list.json()) == 1

    def test_medication_record_rejects_other_patients_medication_id(self, client: TestClient, session: Session):
        pt = _make_patient(session, "환자A")
        other = _make_patient(session, "환자B")
        med_id = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        ).json()["id"]

        r = client.post(
            f"/patients/{other.id}/medication-records",
            json={"patient_medication_id": med_id, "status": "taken"},
            headers=_auth(other.id, "patient"),
        )
        assert r.status_code == 404


class TestTransactionRollback:
    def test_failed_medication_record_insert_does_not_partially_commit(self, client: TestClient, session: Session):
        """존재하지 않는 patient_medication_id로 복약기록을 만들려는 시도가 세션에
        아무 흔적도 남기지 않는지 확인 — _get_owned_medication()이 404를 던지는 시점에
        session.add()/commit()이 아직 호출 전이라 롤백할 것조차 없어야 정상이다."""
        pt = _make_patient(session)
        before_count = len(
            client.get(f"/patients/{pt.id}/medication-records", headers=_auth(pt.id, "patient")).json()
        )

        r = client.post(
            f"/patients/{pt.id}/medication-records",
            json={"patient_medication_id": 999999, "status": "taken"},
            headers=_auth(pt.id, "patient"),
        )
        assert r.status_code == 404

        after_count = len(
            client.get(f"/patients/{pt.id}/medication-records", headers=_auth(pt.id, "patient")).json()
        )
        assert after_count == before_count == 0

        # 세션이 여전히 정상 동작하는지(이전 실패로 세션이 깨지지 않았는지) 확인
        r2 = client.post(
            f"/patients/{pt.id}/medications", json={"medication_name": "암로디핀"}, headers=_auth(pt.id, "patient")
        )
        assert r2.status_code == 200
