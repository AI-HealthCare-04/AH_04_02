# 공통 개발 DB 구조 + 환자 의약품 등록 기능 — 설정 가이드 (2026-07-14, 2026-07-15 Aiven 검증 반영)

여러 로컬 개발 환경에서 같은 회원/환자 의약품 데이터를 볼 수 있도록 DB 연결을
환경변수 기반으로 바꾸고, 환자 의약품 등록/조회 API를 새로 추가한 작업의 실행 가이드입니다.
**2026-07-15: 실제 Aiven MySQL 인스턴스(`health_companion_dev`)에 연결·마이그레이션·
회원가입→로그인 e2e까지 전부 검증 완료했습니다** (10번 섹션 참고).

## 1. 문제 원인

`backend/core/database.py`(PR #44 이전엔 `backend/database.py`)가
`DATABASE_URL = "sqlite:///./app.db"`를 하드코딩하고 있었습니다.
환경변수를 전혀 읽지 않아서, 팀원마다 로컬에서 서버를 띄우면 각자 독립적인 SQLite 파일이
생겼습니다 — 한 사람이 가입한 계정은 그 사람의 로컬 파일에만 존재하고, 다른 팀원의 서버는
그 파일의 존재 자체를 모릅니다. 인증 로직(bcrypt 해싱, JWT 발급, commit 등) 자체는 정상이었고,
"공유 DB가 애초에 존재하지 않는다"는 순수 인프라 문제였습니다.

부차적으로 이메일 대소문자/공백 정규화 부재, `Patient.email` 중복가입 허용, 죽은 코드였던
`POST /auth/signup` 등 3가지 인증 관련 버그도 함께 발견되어 이번 작업에서 같이 고쳤습니다.

## 2. 현재 DB 연결 구조

`backend/core/database.py`가 `APP_ENV`/`DATABASE_URL` 환경변수를 읽도록 바뀌었습니다
(PR #44에서 `backend/database.py` → `backend/core/database.py`로 이동, 이번 작업은 그 위에 맞춰 리베이스함).

| APP_ENV | DATABASE_URL 생략 시 | 스키마 관리 | 데모 데이터 시드 |
|---|---|---|---|
| `local`(기본값) | `sqlite:///./app.db` (기존과 동일) | `create_all()` 자동 | O |
| `development` | **에러로 서버 기동 거부** — 팀 공통 DB는 반드시 명시 | Alembic 마이그레이션 필요 | X |
| `test` | pytest가 in-memory SQLite로 오버라이드(`conftest.py`) | `create_all()` (isolated) | X |
| `production` | **에러로 서버 기동 거부** | Alembic 마이그레이션 필요 | X |

동기 SQLAlchemy(SQLModel)를 그대로 유지했습니다 — 비동기로 전환하지 않았습니다. MySQL 연결은
`mysql+pymysql://` (동기 드라이버)로 지원합니다.

**[2026-07-15 추가] `DATABASE_SSL_REQUIRED=true`** — Aiven 등 관리형 MySQL은 SSL 연결이
필수(`ssl-mode=REQUIRED`)인데, pymysql은 URL 쿼리스트링이 아니라 `connect_args`로 SSL을
켜야 한다. 이 플래그를 켜면 `connect_args={"ssl": {"ssl": {}}}`가 자동으로 적용된다.
로컬 SQLite/SSL 없는 MySQL엔 영향 없음(기본값 false).

서버 시작 시 `log_db_connection_info()`가 `APP_ENV`/host/port/database명을 로그로 남깁니다
(비밀번호 제외). `production`에서는 host/port/db명도 로그에 남기지 않고 "연결됨"만 표시합니다.

## 3. 변경한 파일

**신규**
- `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- `backend/alembic/versions/0ff9baa6bb2e_baseline_schema.py` — 기존 12개 테이블 스냅샷
- `backend/alembic/versions/6ec828d72e5f_add_patient_medications_and_medication_.py` — 신규 테이블/컬럼
- `backend/alembic/versions/bcdbae97c089_add_chatbot_name_to_notification_.py` — PR #44의
  `chatbot_name` 컬럼(NOT NULL)을 안전하게 추가(기존 행 있어도 `server_default='약콩이'`로 백필)
- `backend/routers/patient_medications_router.py` — 환자 의약품 API
- `backend/scripts/migrate_local_data.py` — 기존 로컬 DB → 공통 DB 이전 스크립트
- `backend/scripts/seed_dev.py` — 개발용 가상 데이터 시드
- `backend/tests/test_database_env.py`, `test_auth_signup_login.py`, `test_patient_medications_router.py`

**수정**
- `backend/core/database.py` — env 기반 DB 연결(APP_ENV/DATABASE_URL/DATABASE_SSL_REQUIRED),
  로그, local/test만 auto-create+seed (PR #44로 `backend/database.py`에서 이동)
- `backend/main.py` — 라우터 등록, 시작 로그 호출
- `backend/models.py` — `PatientMedication`/`MedicationRecord` 신규, `MedicationSchedule` 확장,
  `Patient.email` 유니크 인덱스 추가
- `backend/core/security.py` — `normalize_email()` 추가 (PR #44로 `backend/security.py`에서 이동)
- `backend/routers/auth_router.py` — 이메일 정규화 로그인, 로그인 실패 원인 서버 로그 분리,
  죽은 코드였던 `POST /auth/signup` 제거
- `backend/routers/monitoring_router.py` — 가입 시 이메일 정규화 + 중복가입 사전검사(409)
- `pyproject.toml`/`uv.lock` — `pymysql`, `alembic` 추가 (PR #44로 `requirements.txt`→uv 전환,
  `uv add pymysql alembic`으로 등록)
- `backend/.env.example` — `APP_ENV`/`DATABASE_URL`/`DATABASE_SSL_REQUIRED` 예시 추가
- `backend/tests/conftest.py` — 테스트가 진짜 로컬 `app.db`를 안 건드리도록 `APP_ENV=test`/
  `DATABASE_URL=sqlite://` 고정

> **참고**: PR #44(`core/`/`services/` 폴더 재구조화, uv 전환)가 먼저 dev에 병합돼서, 이 작업
> 전체를 그 구조 위에 리베이스했습니다 — `database.py`/`security.py`/`dependencies.py`/`auth.py`는
> 전부 `backend/core/` 아래로, `drug_reference.py` 등은 `backend/services/`로 옮겨져 있습니다.

## 4. 데이터베이스 스키마

**`patient_medications`** (신규) — 환자가 현재 복용/등록한 의약품.
`drug_id`/`item_seq`(식약처 품목일련번호)는 의약품 마스터 테이블이 아직 없어 FK 제약 없이
nullable로 둡니다 — 검색 결과가 하나로 확정되지 않으면 null로 남기고 `source_raw_text`(AI/OCR
원문)만 보존합니다. `verification_status`(unverified/matched/user_confirmed/pharmacist_confirmed)로
AI 추정 단계와 사용자 확정 단계를 구분합니다. `deleted_at`으로 soft delete.

**`medication_schedules`** (기존 테이블 확장) — `patient_medication_id`(nullable FK)/
`meal_relation`/`instructions`/`timezone`/`days_of_week`(JSON 문자열) 5개 컬럼 추가. 기존
`/monitoring/schedules` API와 데이터는 전혀 건드리지 않았습니다(전부 nullable 추가라 하위호환).

**`medication_records`** (신규) — 실제 복약 수행 기록. `patient_medication_id` 필수 FK,
`schedule_id`는 nullable FK. 기존 `medication_logs`(MedicationSchedule 기반 체크인)와는 별개
테이블로, 서로 다른 두 플로우를 침범하지 않습니다.

**`patients.email`** — 유니크 인덱스 추가(기존엔 제약 없어 중복가입이 조용히 허용됐음).

## 5. 회원가입/로그인 처리 흐름

1. 가입(`POST /monitoring/patients` 또는 `/monitoring/caregivers`): 이메일 `strip()+lower()` 정규화
   → 정규화된 값으로 사전 중복검사(있으면 409) → bcrypt 해싱 → `add`→`commit`→`refresh`
2. 로그인(`POST /auth/login`): 식별자에 `@`가 있으면 이메일로 보고 동일하게 정규화해서 조회,
   아니면 전화번호로 보고 `phone_hash`로 조회 → `verify_password()` → 성공 시 JWT 발급(role 포함)
3. 로그인 실패 원인(계정 없음/비밀번호 틀림)은 서버 로그(`logger.info`)에만 구분해서 남기고,
   클라이언트에는 항상 동일한 통합 메시지("이메일/전화번호 또는 비밀번호가 올바르지 않습니다")

## 6. 환자 의약품 적재 흐름

`POST /patients/{patient_id}/medications`로 등록 — `source_type`(manual/prescription_ocr/
pill_image/api_search)에 따라 `verification_status` 기본값이 결정됩니다(manual→user_confirmed,
그 외→unverified). AI/OCR 원문(`source_raw_text`)과 사용자가 최종 확인한 값(`medication_name`)은
별도 필드라 PATCH로 이름을 고쳐도 원문은 절대 덮어써지지 않습니다. 스케줄(`.../schedules`)과
복약기록(`/patients/{patient_id}/medication-records`)은 각각 별도 엔드포인트로 생성하며, 전부
`require_actor_patient_access`로 인가하고 리소스 소유권(`medication.patient_id == 경로의
patient_id`)까지 별도 확인해 다른 환자의 데이터에 접근할 수 없습니다.

## 7. 기존 데이터 이전 방법

```bash
# 1) 먼저 dry-run으로 검토
uv run python scripts/migrate_local_data.py \
  --source-url "sqlite:///./app.db" \
  --target-url "mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE" \
  --source-pii-encryption-key "<기존 로컬 .env의 PII_ENCRYPTION_KEY>" \
  --source-pii-hash-secret "<기존 로컬 .env의 PII_HASH_SECRET>" \
  --target-pii-encryption-key "<공통 개발 DB용 PII_ENCRYPTION_KEY>" \
  --target-pii-hash-secret "<공통 개발 DB용 PII_HASH_SECRET>" \
  --dry-run

# 2) 검토 후 실제 실행 (반드시 타깃 DB 백업 먼저)
uv run python scripts/migrate_local_data.py \
  --source-url "sqlite:///./app.db" \
  --target-url "mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE" \
  --source-pii-encryption-key "..." --source-pii-hash-secret "..." \
  --target-pii-encryption-key "..." --target-pii-hash-secret "..." \
  --yes-i-have-a-backup
```

**왜 PII 키가 4개(소스 2 + 타깃 2)나 필요한가**: `name`/`phone`은 Fernet으로 암호화돼 있는데
각 로컬 환경이 서로 다른 키를 쓰고 있을 수 있습니다. 암호문을 그대로 복사하면 타깃에서
복호화가 안 되므로, 스크립트가 [소스 키로 복호화 → 타깃 키로 재암호화]를 자동으로 처리합니다.
**bcrypt 비밀번호 해시는 복호화하지 않고 그대로(불투명한 문자열로) 복사**합니다.

이전 순서: `caregivers → patients → caregiver_patients → patient_medications →
medication_schedules → medication_records`. `medical_records`/`ocr_results`/`guide_results`/
기존 `medication_logs`는 이번 스크립트 범위 밖입니다(회원+환자의약품 데이터에 집중).

재실행해도 자연키(이메일/phone_hash) 또는 이미 옮긴 조합 기준으로 중복 적재를 건너뜁니다.
실패한 행은 예외 없이 `migrate_local_data_failed_<시각>.json`에 기록되고 나머지는 계속
진행됩니다. `--dry-run` 없이 실행하려면 `--yes-i-have-a-backup`을 반드시 함께 줘야 합니다
(백업 확인 없이는 거부).

## 8. 환경변수 설정 방법

`backend/.env.example`을 복사해 `backend/.env`를 만들고:

```env
APP_ENV=local
# DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE
# DATABASE_SSL_REQUIRED=true
```

- 개인 로컬로 그냥 쓰려면 `APP_ENV=local`만 두고 `DATABASE_URL`은 주석 처리(생략) 상태 유지
- 팀 공통 개발 DB에 붙으려면 `APP_ENV=development`로 바꾸고 `DATABASE_URL`에 팀에서 공유한
  접속 정보를 채우기(비밀번호를 이 파일에 커밋하지 말 것 — `.gitignore`가 `.env`를 이미 제외)
- **Aiven MySQL을 쓴다면 `DATABASE_SSL_REQUIRED=true`도 반드시 함께 설정** — 없으면 SSL
  핸드셰이크 실패로 연결이 거부됩니다.

## 9. 마이그레이션 실행 명령

```bash
cd backend
uv run alembic upgrade head      # 최신 스키마로
uv run alembic downgrade -1      # 한 단계 되돌리기
uv run alembic history           # 리비전 이력 확인
```

새 스키마 변경이 필요해지면:
```bash
uv run alembic revision --autogenerate -m "설명"
# 생성된 파일의 import sqlmodel 확인 + create_foreign_key(None, ...) 나오면 이름 지정 필요
# (SQLite batch 모드 제약 — alembic/README 또는 이 문서 "남은 위험" 참고)
# NOT NULL 컬럼을 기존 테이블에 추가하는 경우 add_column에 server_default를 직접 채워야
# 함(autogenerate는 안 채워줌 — bcdbae97c089 리비전 참고)
uv run alembic upgrade head      # 로컬에서 먼저 검증
```

`APP_ENV=local`처럼 로컬에서 기존 `create_all()` 방식으로 이미 만들어둔 `app.db`가 있다면,
Alembic이 그 상태를 모르기 때문에 `uv run alembic stamp head`로 "이미 최신 상태"라고 표시해두거나,
`app.db`를 지우고 `alembic upgrade head`로 처음부터 만드는 것 중 하나를 선택하세요(팀 공통
DB는 당연히 `alembic upgrade head`로 처음 생성).

## 10. 테스트 실행 결과

```bash
cd backend
uv run pytest tests/ -q
```

**76 passed** (기존 48 + 신규 28). 신규 테스트 파일: `test_database_env.py`(6),
`test_auth_signup_login.py`(8), `test_patient_medications_router.py`(14). 요청된 10개 시나리오
전부 커버:

| # | 시나리오 | 테스트 |
|---|---|---|
| 1 | 가입 후 같은 DB 로그인 성공 | `test_signup_then_login_succeeds_in_same_db` |
| 2 | 잘못된 비밀번호 로그인 실패 | `test_login_wrong_password_fails_with_generic_message` |
| 3 | 중복 회원가입 실패 | `test_duplicate_patient_signup_rejected_with_409` 외 2건 |
| 4 | 다른 환경 DB URL 적용 확인 | `test_database_env.py` 전체(서브프로세스로 실제 프로세스 기동 조건 재현) |
| 5 | 환자 의약품 등록 성공 | `TestCreateMedication` 전체 |
| 6 | 비로그인 등록 실패 | `test_unauthenticated_registration_fails` |
| 7 | 다른 사용자 데이터 접근 실패 | `test_other_patient_cannot_register_for_someone_else` 외 2건 |
| 8 | 의약품 수정/삭제 | `TestUpdateAndDeleteMedication` |
| 9 | 스케줄/복약기록 생성 | `TestSchedulesAndRecords` |
| 10 | transaction rollback 확인 | `test_failed_medication_record_insert_does_not_partially_commit` |

이 외에 직접 실행(스크립트)으로 검증한 것:
- `scripts/migrate_local_data.py`: 실제 실행 → PII 재암호화 정확성(소스 키로 복호화한 평문과
  타깃 키로 재복호화한 평문이 일치) → 재실행 시 전부 "중복 건너뜀"으로 idempotent 확인
- `scripts/seed_dev.py`: 최초 실행 → 재실행 시 건너뜀 → DB 이름에 "prod" 포함 시 실행 거부 확인
- Alembic: `upgrade head` → `downgrade -1` → 재`upgrade head` → `downgrade base` 왕복 전부 정상

프론트엔드: `tsc --noEmit` 통과(변경 없음, 백엔드 전용 작업이라 프론트 영향 없음).

**[2026-07-15 추가] 실제 Aiven MySQL 인스턴스로 검증 완료** — `health_companion_dev`
데이터베이스(같은 Aiven 서비스 안의 기존 개인 프로젝트 DB와는 분리된 전용 DB)에 대해:
- `database.py`를 통한 SSL 연결(`DATABASE_SSL_REQUIRED=true`) 성공
- `alembic upgrade head` → 전체 3개 리비전(baseline/patient_medications/chatbot_name) 정상 적용,
  16개 테이블(15개 + alembic_version) 생성 확인
- 실제 FastAPI 앱(`TestClient`)으로 `POST /monitoring/patients` 회원가입 → `POST /auth/login`
  로그인까지 e2e 성공(PII 암호화/복호화, bcrypt, JWT 전부 포함) — 테스트 데이터는 정리함
- `chatbot_name` NOT NULL 컬럼 추가가 기존 행에도 안전하게 적용되는지(server_default 백필)
  SQLite로 사전 검증 후 실제 MySQL에도 적용, `DESCRIBE notification_settings`로 확인

## 11. 남아 있는 위험 및 추가 작업 (숨기지 않고 명시)

- **기존 로컬 `app.db`가 있는 팀원의 스키마 동기화**: Alembic 도입 전에 `create_all()`로 이미
  만들어진 로컬 DB는 Alembic의 리비전 이력을 모릅니다 — 처음 한 번은 `uv run alembic stamp head`
  (기존 데이터 유지) 또는 `app.db` 삭제 후 `alembic upgrade head`(초기화) 중 선택해야 합니다.
  이 판단은 각자 로컬에 남겨둔 테스트 데이터가 중요한지에 따라 팀원 본인이 결정할 부분이라
  제가 임의로 실행하지 않았습니다.
- **`medical_records`/`ocr_results`/`guide_results`/기존 `medication_logs`는 마이그레이션
  스크립트 범위 밖**입니다 — OCR·RAG 이력까지 공통 DB로 옮기려면 스크립트를 확장해야 합니다.
- **의약품 마스터 테이블이 없어** `patient_medications.drug_id`/`item_seq`는 애플리케이션이
  자동으로 채워주지 않습니다(호출하는 쪽이 이미 확정한 값을 넘길 때만 채워짐) — 실시간 검색
  매칭을 API에 직접 연동하려면 별도 설계가 필요합니다.
- **patient_medications 재실행 안전성 휴리스틱의 한계**: 자연키가 없는 테이블(patient_medications/
  medication_schedules/medication_records)의 중복 판정은 "같은 값 조합이 이미 있으면 건너뜀"
  방식이라, 환자가 정말로 같은 약을 같은 조건으로 두 번 등록한 정상 케이스와 재실행을 완벽히
  구분하지 못할 수 있습니다 — 실제 이전 전에 `--dry-run`으로 먼저 검토를 권장합니다.
- **`on_event("startup")`은 FastAPI/Starlette에서 deprecated 경고가 뜹니다**(테스트 통과에는
  영향 없음) — 이번 작업 범위는 아니지만, 다음에 lifespan 핸들러로 교체하는 게 좋습니다.
- **운영(production) 배포 자체가 아직 없습니다**(README에 "배포는 추후 검토 예정"으로 명시돼
  있음) — `APP_ENV=production` 관련 코드는 준비만 해뒀을 뿐 실제 운영 환경에서 실행해본 적은
  없습니다.

## 12. REQ-039(로그인 잠금·비밀번호 재설정)·REQ-035(회원 탈퇴) 추가 (2026-07-15)

### 새 API

| Method | Endpoint | 설명 | 인증 |
|---|---|---|---|
| POST | `/auth/password-reset/request` | 임시번호(6자리) 이메일 발송 요청 | X (계정 존재 여부와 무관하게 같은 응답) |
| POST | `/auth/password-reset/verify` | 임시번호 확인 → 재설정 전용 `reset_token` 발급 | X |
| POST | `/auth/password-reset/confirm` | `reset_token`으로 새 비밀번호 설정, 잠금·실패횟수 초기화 | X (reset_token 자체가 인증) |
| POST | `/auth/withdraw` | 탈퇴 요청 — 즉시 비활성화, 30일 뒤 개인정보 삭제 예약 | O (본인 로그인 + 비밀번호 재입력) |
| POST | `/auth/withdraw/cancel` | 탈퇴 취소(30일 이내) | X (탈퇴 후엔 로그인이 막히므로 identifier+password로 본인 확인) |

`POST /auth/login`도 두 가지가 바뀌었습니다:
- 5회 연속 비밀번호 실패 시 계정을 잠그고(`locked_at`), 가입 이메일로 임시번호를 자동 발송합니다.
  잠긴 동안은 비밀번호가 맞아도 로그인이 거부됩니다(재설정으로만 해제).
- 탈퇴(`deactivated_at`이 채워진) 계정도 로그인이 거부됩니다 — `/auth/withdraw/cancel`로만 복구.

### 새 환경변수

`EMAIL_PROVIDER=mock`(기본값, 로그만 남김) `| smtp`(실제 발송) — `backend/.env.example`의
"이메일 발송" 섹션 참고. `smtp`로 켤 때만 `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/
`SMTP_FROM`이 필요합니다(하나라도 없으면 즉시 에러 — 재설정 코드가 조용히 안 나가는 사고 방지).

### 새 스키마 (마이그레이션 `38a30cdfa517`)

- `caregivers`/`patients`에 `failed_login_attempts`/`locked_at`/`deactivated_at`/
  `deletion_scheduled_at` 컬럼 추가(기존 행은 `server_default`로 안전하게 백필됨)
- `password_reset_codes` 테이블 신규 (임시번호는 평문 저장하지 않고 HMAC-SHA256 해시만 저장,
  10분 만료, 1회 사용)
- `privacy_purge_audits` 테이블 신규 (탈퇴 요청·비활성화·삭제예정 시각 + 상태(pending/
  completed/cancelled) 기록 — PII를 담지 않는 비식별 감사기록이라 계정이 실제로 삭제된
  뒤에도 이 행 자체는 보존됨)

### 회원 탈퇴 → 실제 삭제 스크립트

`scripts/purge_expired_accounts.py --dry-run`(먼저 확인) / 실행(실제 삭제). 서버가 자동으로
스케줄 실행하지 않는 **수동 스크립트**입니다(사용자 확인 — 새 인프라(Celery 등) 추가 없이
바로 쓸 수 있는 방법을 택함) — 팀이 원하는 주기로 cron 등에 직접 등록해서 돌릴지는 각자
결정할 부분입니다. `scheduled_purge_at`이 지난 `pending` 감사기록만 골라 개인정보 필드
(이름·전화번호·이메일·비밀번호 해시 등)만 지우고, `Patient`/`Caregiver` 행 자체나
`medical_records`/`patient_medications` 등 연관 데이터는 지우지 않습니다(FK 참조가 끊기는
문제와 "임의로 데이터를 지우지 않는다"는 팀 방침 때문).

### 테스트

`test_login_lockout_and_password_reset.py`(10) / `test_account_withdrawal.py`(9) /
`test_purge_expired_accounts.py`(3) 추가 — `uv run pytest backend/tests/` **98개 전부 통과**
(기존 76 + 신규 22). 잠금 임계치 미만/도달, 잠긴 계정 로그인 거부, 재설정 코드 1회성·만료·
오입력, `reset_token`으로 다른 보호된 엔드포인트 접근 불가, 탈퇴→로그인 차단→취소→재로그인,
유예기간 경과 후 취소 거부, purge 스크립트의 dry-run/실행/대상 필터링(계정 없음 케이스 포함)
까지 커버합니다.

### 남아 있는 제한 사항

- **연락처(전화번호)로 가입한 계정은 임시번호를 받을 방법이 없습니다** — 이메일 발송만
  구현했습니다(REQ-039 요구사항 자체가 "가입이 이메일 기반이라 SMS 등 추가 계약 없이 바로
  구축 가능"이라는 판단 하에 진행됨, 사용자 확인). `account.email`이 없으면 코드는 생성되지만
  발송은 안 되고 서버 로그에 경고만 남습니다 — 이 경우 팀에 직접 문의해야 합니다.
- ~~임시번호 재전송/검증 시도 횟수 제한은 구현하지 않았습니다~~ **[2026-07-16 정정]** 팀원
  리뷰(PR #48)에서 이게 실제로 CRITICAL 취약점(코드 누적 브루트포스)으로 재현돼 추가
  구현했습니다 — 재발급 시 이전 코드 무효화, 계정당 요청 횟수 제한(10분 3회), verify
  시도 횟수 제한(5회). 자세한 내용은 `docs/deviation-log-2026-07-16.md` DEV-03 참고.
- **탈퇴 확인 절차는 "현재 비밀번호 재입력"으로 구현**했습니다 — 요구사항의 "확인 절차"가
  프론트 확인 모달만 뜻하는 것일 수도 있어, 프론트 쪽과 UX 확인이 필요할 수 있습니다.

## 13. 공유 DB 스키마 변경 시 로컬 실행 환경 동기화 확인 절차 (2026-07-16 추가)

**배경**: PR #47 마이그레이션을 실제 Aiven 공통 개발 DB에 먼저 적용했는데, 그 DB를 바라보는
로컬 실행 환경(메인 프로젝트 디렉토리)이 해당 커밋을 pull하지 않은 채 계속 실행 중이어서
"DB는 새 스키마, 서버 코드는 옛 스키마"인 상태가 됐고, 초대 기능이 `Unknown column
'invited_phone'` 에러로 깨졌습니다(`docs/deviation-log-2026-07-16.md` DEV-06). 공유 DB에
스키마 변경을 실제로 반영하는 작업과, 그 DB를 바라보는 실행 환경의 코드 동기화는 별개
작업이 아니라 **한 세트로 처리해야** 이런 드리프트가 안 생깁니다.

**공유 개발 DB에 `alembic upgrade head`를 실제로 실행하기 전에 확인할 것:**

1. 지금 이 마이그레이션을 실행하는 사람의 로컬 코드가, 이 마이그레이션이 기대하는 모델
   정의(`models.py`)와 실제로 일치하는가 — 즉 이 마이그레이션이 포함된 브랜치/커밋이
   맞는가.
2. 이 DB를 바라보고 **지금 실행 중인** 다른 로컬 서버(본인 것이든 팀원 것이든)가 있다면,
   그 서버들의 코드도 같은 스키마를 기대하는 버전인가. 아니라면:
   - 그 서버들도 같이 최신 코드로 맞출 수 있는가, 아니면
   - 지금 당장은 맞추기 어렵다면(예: 다른 작업 중이라 브랜치를 못 바꿈) 최소한 "이 DB에
     스키마 변경 적용함, 코드 안 맞으면 이 기능들이 깨짐"을 팀에 공지한다.
3. 마이그레이션 적용 후, 실제로 그 스키마에 의존하는 기능(이번 경우 초대 기능)을 한 번
   실행해서 정상 동작하는지 확인한다 — 마이그레이션 자체의 성공(`alembic current`가
   head를 가리킴)과 "그 스키마를 쓰는 기능이 실제로 동작함"은 별개다.

**이미 드리프트가 생겼다면**(코드는 못 맞추는 상황): 어떤 기능이 영향받는지 구체적으로
파악해서 기록해두고(예: DEV-06처럼), 그 기능을 그 환경에서 잠정적으로 못 쓴다는 걸 명확히
남긴다 — "왜 안 되지"를 나중에 또 반복 조사하지 않도록.
