"""
배포 환경(yakcong.duckdns.org) 대상 부하 테스트용 locustfile.

[2026-08-05 추가] locustfile.py(로컬용)와 분리한 이유: 배포 환경은 팀 공용
Aiven MySQL을 쓰는 단일 EC2(t3.medium, 오토스케일링 없음)라, 실제 계정으로
로그인해서 인증이 필요한 엔드포인트까지 두드리면 계정 잠금(REQ-039, 5회
실패시 30분 잠금) 위험이나 DB 부하 위험이 있다. 그래서 이 파일은 인증이
필요 없는 두 엔드포인트만 대상으로 한다:
  - GET /api/                       (main.py 헬스체크)
  - GET /api/push/vapid-public-key  (로그인 여부와 무관한 공개 엔드포인트)

주의: nginx가 `/api/*`만 백엔드로 보내고 그 외는 프론트(Vite dev server)로
보낸다 — `/api/` 접두사 없이 호출하면 프론트 SPA가 200을 반환해서 마치
성공한 것처럼 보이지만 실제로는 백엔드에 전혀 도달하지 않는다.

사용법 (레포 루트에서):
  uv run locust -f locustfile_deploy.py --headless -u 4 -r 1 -t 30s \
      --host https://yakcong.duckdns.org
"""

from locust import HttpUser, task, between


class PublicEndpointUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://yakcong.duckdns.org"

    @task(1)
    def health_check(self):
        self.client.get("/api/", name="/api/ (health)")

    @task(1)
    def vapid_public_key(self):
        self.client.get("/api/push/vapid-public-key", name="/api/push/vapid-public-key")
