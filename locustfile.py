"""
로컬 부하 테스트용 locustfile — https://locust.io/

[2026-08-05 추가] "Locust 한번 써보고 싶다"는 요청으로 추가한 최소 구성. 로컬
backend-dev-local(APP_ENV=local, SQLite, 데모 계정만 있는 서버)만 대상으로
한다 — 팀 공용 Aiven 개발 DB를 향해 돌리면 다른 팀원 작업에 영향을 줄 수
있어서 절대 host로 잡으면 안 된다.

사용법:
1) 로컬 백엔드를 먼저 띄운다 (레포 루트에서):
   cd backend && APP_ENV=local DATABASE_URL=sqlite:///./app.db \
       ../.venv/bin/python3 -m uvicorn main:app --port 8002
   (core/database.py의 _seed_demo_data가 demo@example.com/password1234 보호자 +
   환자 1명을 자동으로 만들어준다.)
2) 웹 UI로 실행 (레포 루트에서):
   uv run locust
   브라우저에서 http://localhost:8089 열고 Host를 http://localhost:8002로 지정.
3) 또는 헤드리스로 바로 실행:
   uv run locust --headless -u 10 -r 2 -t 30s
"""

from locust import HttpUser, task, between

DEMO_IDENTIFIER = "demo@example.com"
DEMO_PASSWORD = "password1234"


class CaregiverUser(HttpUser):
    # 실제 사용자가 화면 사이를 오가며 생기는 간격을 흉내낸다 — 요청을 쉴 새 없이
    # 쏘지 않고, 사람이 화면을 보는 시간(1~3초)을 흉내내는 정도로만 잡았다.
    wait_time = between(1, 3)
    host = "http://localhost:8002"

    def on_start(self):
        r = self.client.post(
            "/auth/login",
            json={"identifier": DEMO_IDENTIFIER, "password": DEMO_PASSWORD},
            name="/auth/login",
        )
        r.raise_for_status()
        body = r.json()
        self.caregiver_id = body["caregiver_id"]
        self.client.headers["Authorization"] = f"Bearer {body['access_token']}"

        patients = self.client.get(
            f"/monitoring/caregivers/{self.caregiver_id}/patients",
            name="/monitoring/caregivers/[id]/patients",
        ).json()
        # 데모 시드 데이터엔 환자가 항상 1명 있지만, 방어적으로 없으면 태스크를 스킵한다.
        self.patient_id = patients[0]["id"] if patients else None

    @task(3)
    def view_today(self):
        if self.patient_id is None:
            return
        self.client.get(
            "/monitoring/today",
            params={"patient_id": self.patient_id},
            name="/monitoring/today",
        )

    @task(2)
    def view_records(self):
        if self.patient_id is None:
            return
        self.client.get(
            "/records", params={"patient_id": self.patient_id}, name="/records"
        )

    @task(1)
    def view_schedules(self):
        if self.patient_id is None:
            return
        self.client.get(
            "/monitoring/schedules",
            params={"patient_id": self.patient_id},
            name="/monitoring/schedules",
        )
