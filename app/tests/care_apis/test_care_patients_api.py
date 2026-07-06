import itertools

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app

_phone_number_seq = itertools.count(1)


async def _signup_and_login(client: AsyncClient, *, email: str, name: str, role: str) -> str:
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": name,
        "gender": "FEMALE",
        "role": role,
        "birth_date": "1990-01-01",
        "phone_number": f"010{next(_phone_number_seq):08d}",
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


class TestCarePatientsAPI(TestCase):
    async def test_caregiver_can_link_and_list_multiple_patients(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            caregiver_token = await _signup_and_login(
                client, email="caregiver@example.com", name="보호자", role="GUARDIAN"
            )
            patient1_token = await _signup_and_login(
                client, email="patient1@example.com", name="환자1", role="MEDICATION_SUBJECT"
            )
            patient2_token = await _signup_and_login(
                client, email="patient2@example.com", name="환자2", role="MEDICATION_SUBJECT"
            )

            caregiver_headers = {"Authorization": f"Bearer {caregiver_token}"}
            patient1_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {patient1_token}"})
            patient2_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {patient2_token}"})
            patient1_id = patient1_me.json()["id"]
            patient2_id = patient2_me.json()["id"]

            link_response_1 = await client.post(
                "/api/v1/care/patients", json={"patient_id": patient1_id}, headers=caregiver_headers
            )
            link_response_2 = await client.post(
                "/api/v1/care/patients", json={"patient_id": patient2_id}, headers=caregiver_headers
            )
            list_response = await client.get("/api/v1/care/patients", headers=caregiver_headers)

        assert link_response_1.status_code == status.HTTP_201_CREATED
        assert link_response_2.status_code == status.HTTP_201_CREATED
        assert list_response.status_code == status.HTTP_200_OK
        assert {p["id"] for p in list_response.json()} == {patient1_id, patient2_id}

    async def test_link_same_patient_twice_conflicts(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            caregiver_token = await _signup_and_login(
                client, email="caregiver2@example.com", name="보호자2", role="CAREGIVER"
            )
            patient_token = await _signup_and_login(
                client, email="patient3@example.com", name="환자3", role="MEDICATION_SUBJECT"
            )
            caregiver_headers = {"Authorization": f"Bearer {caregiver_token}"}
            patient_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {patient_token}"})
            patient_id = patient_me.json()["id"]

            await client.post("/api/v1/care/patients", json={"patient_id": patient_id}, headers=caregiver_headers)
            response = await client.post(
                "/api/v1/care/patients", json={"patient_id": patient_id}, headers=caregiver_headers
            )
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_patient_cannot_link_another_patient(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            patient_a_token = await _signup_and_login(
                client, email="patient_a@example.com", name="환자A", role="MEDICATION_SUBJECT"
            )
            patient_b_token = await _signup_and_login(
                client, email="patient_b@example.com", name="환자B", role="MEDICATION_SUBJECT"
            )
            patient_a_headers = {"Authorization": f"Bearer {patient_a_token}"}
            patient_b_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {patient_b_token}"})
            patient_b_id = patient_b_me.json()["id"]

            response = await client.post(
                "/api/v1/care/patients", json={"patient_id": patient_b_id}, headers=patient_a_headers
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_unlink_patient(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            caregiver_token = await _signup_and_login(
                client, email="caregiver3@example.com", name="보호자3", role="SOCIAL_WORKER"
            )
            patient_token = await _signup_and_login(
                client, email="patient4@example.com", name="환자4", role="MEDICATION_SUBJECT"
            )
            caregiver_headers = {"Authorization": f"Bearer {caregiver_token}"}
            patient_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {patient_token}"})
            patient_id = patient_me.json()["id"]

            await client.post("/api/v1/care/patients", json={"patient_id": patient_id}, headers=caregiver_headers)
            unlink_response = await client.delete(f"/api/v1/care/patients/{patient_id}", headers=caregiver_headers)
            list_response = await client.get("/api/v1/care/patients", headers=caregiver_headers)

        assert unlink_response.status_code == status.HTTP_200_OK
        assert list_response.json() == []
