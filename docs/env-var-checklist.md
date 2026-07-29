# 환경변수 변경 체크리스트

`.env`를 커밋하지 않는다는 규칙(`docs/team-rules.md` 11번)은 있지만, "값이 바뀌면
서버에도 반영하라"는 절차가 없어서 실제로 문제가 반복됐다 — 2026-07-28, 도메인을
바꾸면서 서버 쪽 `CORS_ALLOWED_ORIGINS`를 업데이트하지 않아 로그인이 갑자기 안 되던
사고가 그 예다.

## 왜 자동으로 반영이 안 되는가

`.github/workflows/ci.yml`의 배포 스텝은 `git pull origin dev && docker compose up -d
--build`만 한다 — **코드만 가져오고 `.env`는 절대 건드리지 않는다** (`.env`가
`.gitignore`돼 있어서 애초에 git에 없다). 즉 EC2의 `backend/.env`/`frontend/.env.local`은
누군가 **직접 SSH로 들어가서 손으로 고쳐야만** 바뀐다 — 로컬에서 `.env.example`이나
로컬 `.env`만 고치고 "배포됐겠지" 하면 안 된다.

## 체크리스트 — 이럴 때 서버도 같이 고쳐야 한다

- [ ] **`CORS_ALLOWED_ORIGINS`(backend)** — 프론트 도메인이 바뀌거나 새 도메인(터널 등)이
      추가되면, EC2의 `backend/.env`도 같이 갱신하고 백엔드 컨테이너를 재시작한다
      (`docker compose restart backend` 또는 재배포로 반영). 안 하면 로그인부터
      전부 CORS로 막힌다(2026-07-28 사고 원인).
- [ ] **`VITE_MONITORING_API_URL`(frontend)** — 백엔드 도메인/포트가 바뀌면 프론트
      **빌드 시점**에 이 값이 박히므로(`frontend/src/api/monitoringClient.ts` 참고),
      EC2에서 반드시 재빌드(`docker compose up -d --build`)까지 실행해야 한다 —
      컨테이너 재시작만으론 반영 안 됨.
- [ ] **`VITE_PROXY_TARGET`** — 백엔드 컨테이너 이름/포트가 바뀌면 같이 갱신 (`vite.config.ts`
      의 `/api` 프록시가 이 값을 씀).
- [ ] **새 필수 환경변수를 추가했을 때** — `.env.example`에 추가하는 것과 별개로, EC2의
      실제 `.env`에도 값을 채워 넣어야 한다. `core/database.py`처럼 `APP_ENV=production`
      인데 값이 없으면 아예 기동을 거부하도록 만든 모듈이 있어 배포 자체가 실패할 수
      있다 — 배포 전에 미리 채워두면 그 자리에서 알 수 있다.
- [ ] **`VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/`VAPID_CONTACT_EMAIL`** — 팀 전체가 같은
      값을 써야 하는 값(개인별로 다르면 기기 구독이 꼬인다) — 로테이션하면 EC2 값도
      함께 바꾸고, 기존에 구독된 기기는 재구독이 필요할 수 있음을 공지한다.
- [ ] **DB 관련 값(`DATABASE_URL`, `DATABASE_SSL_REQUIRED`, `DATABASE_SSL_CA`)** — 팀
      공용 Aiven MySQL 자격 정보가 바뀌면 로컬 각자 `.env` + EC2 `.env` 전부 갱신 필요
      (`docs/shared-dev-db-setup.md` 참고).
- [ ] **⚠️ `PII_ENCRYPTION_KEY` / `PII_HASH_SECRET`** — 절대 임의로 재발급(로테이션)하면
      안 됩니다. 이 값이 바뀌면 기존에 암호화되어 저장된 개인정보(이름, 전화번호 등)를
      영영 복호화할 수 없게 됩니다. 서버 인스턴스를 새로 만들거나 재설정할 때는 반드시
      기존 값을 그대로 가져와서 사용하세요.

  > **EC2 인스턴스를 교체·폐기하기 전에 반드시:** 현재 `PII_ENCRYPTION_KEY`와
  > `PII_HASH_SECRET` 값을 비밀번호 관리자 등 안전한 곳에 **먼저 백업**하세요.
  > 인스턴스를 폐기한 뒤에는 이 값을 가져올 곳 자체가 사라집니다 — 잃어버리면
  > 기존 DB에 저장된 모든 개인정보를 복호화할 방법이 없습니다.

## 반영 후 확인

- [ ] EC2에 SSH로 들어가 실제 컨테이너 환경변수를 확인한다: `docker compose exec backend
      env | grep <바뀐_변수명>` — `.env` 파일만 고치고 컨테이너를 안 띄우면 반영 안 된 채로
      착각하기 쉽다.
- [ ] 값이 프론트 빌드 타임 변수(`VITE_*`)라면 `docker compose up -d --build`로
      **재빌드**했는지 확인한다(단순 `restart`로는 새 값이 안 들어감).
- [ ] 실제 배포 도메인에서 로그인 등 기본 플로우 한 번 확인 — CI 테스트는 이 계층(CORS,
      실제 도메인 간 통신)을 검증하지 않는다.

---

새로운 "이것도 서버에 따로 반영해야 하더라" 사례를 발견하면 이 목록에 항목을 추가한다.
