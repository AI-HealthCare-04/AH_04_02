"""
배포 환경 — 로그인이 필요한 실제 조회 화면(오늘의 복약/등록내역/일정) 부하 테스트.

locustfile_deploy.py(공개 엔드포인트 전용)와 분리했다. 이 파일은 실제 로그인
계정이 필요하다 — 절대 코드에 하드코딩하지 말고, 실행 전에 환경변수로만
넘긴다(git에 커밋되는 파일에 실제 계정 정보가 남으면 안 되므로).

모든 태스크는 조회(GET)만 한다 — 실제 계정의 진짜 데이터를 건드리는
쓰기 작업(복약 체크, 일정 생성/삭제 등)은 절대 넣지 않는다.

사용법 (레포 루트에서, 보호자·환자 계정 둘 다 그대로 지원):
  export LOCUST_TEST_IDENTIFIER="실제 이메일 또는 전화번호"
  export LOCUST_TEST_PASSWORD="실제 비밀번호"
  uv run locust -f locustfile_deploy_auth.py --headless -u 4 -r 1 -t 30s \
      --host https://yakcong.duckdns.org

로그인 응답의 role을 보고 자동으로 분기한다 — 보호자 계정이면
/monitoring/caregivers/{id}/patients로 첫 번째 환자를 찾고, 환자 본인
계정이면 그 조회 없이 자기 자신의 id를 그대로 patient_id로 쓴다.
"""

import os

from locust import HttpUser, task, between

IDENTIFIER = os.environ.get("LOCUST_TEST_IDENTIFIER")
PASSWORD = os.environ.get("LOCUST_TEST_PASSWORD")

if not IDENTIFIER or not PASSWORD:
    raise SystemExit(
        "LOCUST_TEST_IDENTIFIER / LOCUST_TEST_PASSWORD 환경변수가 없습니다. "
        "실행 전에 export로 실제 테스트 계정 정보를 넣어주세요 (파일에 직접 적지 마세요)."
    )


class AuthenticatedCaregiverUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://yakcong.duckdns.org"

    def on_start(self):
        r = self.client.post(
            "/api/auth/login",
            json={"identifier": IDENTIFIER, "password": PASSWORD},
            name="/api/auth/login",
        )
        r.raise_for_status()
        body = r.json()
        subject_id = body["caregiver_id"]  # 필드명은 고정이지만 role에 따라 caregiver/patient id
        role = body["role"]  # "caregiver" | "patient"
        self.client.headers["Authorization"] = f"Bearer {body['access_token']}"

        if role == "patient":
            # [2026-08-05 추가] /monitoring/caregivers/{id}/patients는 보호자 전용
            # (get_current_caregiver) — 환자 계정으로 로그인했으면 자기 자신이 곧
            # patient_id라 이 조회 자체가 필요 없다.
            self.patient_id = subject_id
        else:
            patients = self.client.get(
                f"/api/monitoring/caregivers/{subject_id}/patients",
                name="/api/monitoring/caregivers/[id]/patients",
            ).json()
            self.patient_id = patients[0]["id"] if patients else None

    @task(2)
    def view_today(self):
        if self.patient_id is None:
            return
        self.client.get(
            "/api/monitoring/today",
            params={"patient_id": self.patient_id},
            name="/api/monitoring/today",
        )

    @task(2)
    def view_records(self):
        if self.patient_id is None:
            return
        self.client.get(
            "/api/records", params={"patient_id": self.patient_id}, name="/api/records"
        )

    @task(1)
    def view_schedules(self):
        if self.patient_id is None:
            return
        self.client.get(
            "/api/monitoring/schedules",
            params={"patient_id": self.patient_id},
            name="/api/monitoring/schedules",
        )
