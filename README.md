# 💊 진료 기록 기반 복약 안내 및 생활습관 개선 가이드 자동 생성 시스템

> AI 헬스케어 4기 파이널 프로젝트 · 2팀 · Uponati(어포나티) 참여기업 주제

[![Python](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-MySQL-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Vite-61DAFB)](https://react.dev/)
[![License](https://img.shields.io/badge/status-in--progress-yellow)]()

---

## 📌 목차

1. [프로젝트 소개](#-프로젝트-소개)
2. [팀 소개](#-팀-소개)
3. [기술 스택](#-기술-스택)
4. [시스템 아키텍처](#-시스템-아키텍처)
5. [프로젝트 구조](#-프로젝트-구조)
6. [시작하기](#-시작하기)
7. [협업 규칙](#-협업-규칙)
8. [프로젝트 일정](#-프로젝트-일정)
9. [트러블슈팅](#-트러블슈팅)
10. [배포](#-배포)

---

## 📖 프로젝트 소개

### 한 줄 소개

사용자의 진료 기록과 복약 정보를 바탕으로, **LLM이 맞춤형 복약·생활습관 가이드를 자동으로 생성**하고, **OCR로 처방전/약봉투를 인식**하며, **실시간 챗봇**으로 사용자의 질의에 응답하는 AI 헬스케어 웹 서비스입니다.

### 배경 및 목적

의료 기록은 개인 맞춤형 의료 서비스 구현의 핵심 데이터입니다. 이 프로젝트는 LLM 기술을 활용해 복약 안내 및 건강 가이드를 자동화하고, AI 모델 서빙과 헬스케어 서비스 연계 역량을 강화하는 실무형 프로젝트로 기획되었습니다. 질병 예측, 환자 건강 모니터링, 의료 상담 챗봇 등 실질적인 문제 해결을 목표로 합니다.

### 주요 타겟층

- 만성질환을 앓고 있어 정기적으로 약을 복용해야 하는 사용자
- 처방전 내용을 직접 해석하기 어려운 **독거노인 및 거동 불편자**
- 본인을 대신해 처방전을 등록해주는 **보호자 / 요양보호사** — 대리 입력 시 누가 등록했는지 사용자에게 투명하게 표시됩니다

### 신뢰 설계 원칙

- 모든 가이드 하단에 "본 정보는 의료진의 진단·처방을 대체하지 않습니다" 고지 표시
- 복약 가이드의 출처(식약처 데이터 등) 항상 명시
- 보호자가 대리로 등록한 경우 사용자에게 투명하게 안내

### 주요 기능

| 구분 | 기능 | 설명 |
|---|---|---|
| 필수 | **LLM 기반 안내 가이드 생성** | 진료 기록 및 복약 정보를 기반으로 맞춤형 복약/생활습관 가이드 자동 생성 |
| 필수 | **실시간 챗봇** | LLM 기반 실시간 응답 및 대화 맥락 반영 |
| 필수 | **OCR 기반 의료정보 인식** | 진료 기록/처방전/약봉투 이미지·PDF에서 주요 텍스트 자동 추출 |
| 선택 | 시각/음성 콘텐츠 변환 | 안내 텍스트를 카드뉴스, 이미지, TTS 음성으로 변환 |
| 선택 | 이미지 분류 기반 복약 분석 | 약품 이미지 인식 및 복약 정보 제공 |
| 선택 | 알림 기능 | 복약 시간 및 가이드 확인 알림 |

---

## 👥 팀 소개

**2팀** · 담당 멘토: 이현구

| 이름 | 역할 |
|---|---|
| 권순현 | OCR·정보추출 (CLOVA OCR 연동, 의료정보 추출 파이프라인) |
| 김영혜 | RAG·가이드생성·백엔드 통합 (LangChain, 벡터DB, 복약 가이드 생성, 로그인/PII 암호화) |
| 박소정 | 프론트·백엔드 통합 (화면 구현, FastAPI 라우터, 배포 준비) |

> 조성아님, 김현우님은 초기(1주차) 이후 팀에서 하차하여 현재 3인 체제로 진행 중입니다.

---

## 🛠 기술 스택

### Backend
`FastAPI` `Uvicorn` `Python 3.13+` `SQLModel` `Alembic` `Aiven MySQL`(팀 공용 개발·운영) / `SQLite`(개인 로컬 전용) `uv`

### AI / LLM
`LangChain` `OpenAI API (gpt-4o-mini)` `CLOVA OCR` `sentence-transformers` `ChromaDB`

### Frontend
`React` `TypeScript` `Vite` `PWA`(Web Push)

### 인프라 / 배포
`AWS EC2` `Docker Compose` `Nginx`(호스트 직접 설치, HTTPS + Duck DNS) `GitHub Actions`

### 관측 / 성능 테스트
`Langfuse`(LLM 호출 추적·평가) `Locust`(부하테스트 — `dev` 그룹과 분리된 `loadtest` 그룹, `uv sync --group loadtest`로만 설치, 배포 이미지엔 안 들어감)

### 협업 도구
`Git / GitHub` `Notion` `Discord`

> 3인 소규모 팀 체제로, SQLModel 기반 동기 처리로 단순화해 운영 중입니다. 배포(AWS EC2 + GitHub Actions 자동 배포)는 [☁️ 배포](#-배포) 참고.

---

## 🏗 시스템 아키텍처

3인 소규모 팀 체제에 맞춰, 별도 메시지 브로커/워커 없이 **FastAPI 단일 프로세스가 동기 방식으로 처리**하는 단순한 구조로 운영 중입니다. 응답이 느린 외부 호출(CLOVA OCR, OpenAI)은 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않도록만 처리합니다.

> ⚠️ 배포(EC2) 환경에는 **Nginx가 호스트에 직접 설치**돼 있습니다(Duck DNS 도메인 `yakcong.duckdns.org` + HTTPS, 2026-07-27 도입). `docker-compose.yml`에는 없는 구성이라 저장소만 봐서는 안 보이고, EC2 인스턴스에 수동으로 설정돼 있어 **git으로 관리되지 않습니다** — 인스턴스를 새로 만들면 재설정이 필요합니다(다음 과제).

```
Client (React + Vite, 사용자 / 보호자)
       │  HTTPS
       ▼
Nginx (EC2 호스트에 직접 설치, docker-compose 밖)
       │  /api/* → :8000, 그 외 → :5173
       ▼
FastAPI (backend/main.py)
       │
       ├─ auth_router      로그인(이메일/전화번호+비밀번호), JWT 발급
       ├─ records_router    처방전 업로드 → OCR 실행 → RAG 가이드 생성까지 한 요청에서 처리
       ├─ ocr_router        CLOVA OCR 연동 (asyncio.to_thread로 감싼 동기 호출)
       ├─ rag_router        복약·생활습관 가이드 생성 (rag/ 연동, asyncio.to_thread)
       ├─ chat_router       환자 처방·가이드 컨텍스트 기반 GPT 챗봇 (SSE 스트리밍)
       ├─ monitoring_router 보호자용 환자 목록·복약 모니터링, 알림함
       └─ care_router       보호자-환자 연결, 알림 설정, 돌봄 등급 평가
       │
       ├─ (같은 프로세스 내) 알림 스케줄러 — 60초 주기 asyncio 루프, 복약 알림/놓침 감지
       │
       ▼
   Aiven MySQL (팀 공용 개발·운영) / SQLite (개인 로컬 전용, backend/app.db)
```

- **FastAPI**: 요청을 받아 그 자리에서 처리 후 바로 응답 (작업 큐 없음). 단, 챗봇 답변(`/chat/ask/stream`)만 SSE로 스트리밍
- **Aiven MySQL**: 팀 공용 개발 DB이자 운영 DB(SSL 접속). 개인이 혼자 로컬에서만 돌릴 때는 `DATABASE_URL` 미설정 시 SQLite로 자동 대체됨
- **Alembic**: 스키마 변경은 마이그레이션으로 관리(`backend/alembic/versions/`) — 배포 시 `alembic upgrade head`를 실행해야 반영됨(누락 시 실제 장애로 이어진 적 있음, [PR #157](https://github.com/pecs0310/AH_04_02/pull/157) 참고)
- **알림 스케줄러**: Redis/Celery 없이 FastAPI 프로세스 안 asyncio 루프로 60초마다 복약 알림·놓침을 확인해 이메일/Web Push 발송. 여러 서버가 같은 알림을 중복 처리하지 않도록 DB `UniqueConstraint`를 선점 기준으로 사용
- **DB 커넥션 풀**: Aiven 플랜의 `max_connections=76`을 배포(운영 워커 2개)와 팀원 로컬 `development` 접속이 함께 나눠 쓴다 — `backend/core/database.py`가 `APP_ENV`별로 풀 크기를 다르게 지정(production 워커당 20개, development 인스턴스당 5개)해서 한도를 넘지 않게 관리한다. 부하테스트로 실측한 처리 가능 규모는 [☁️ 배포](#-배포) 참고
- **rag/**: RAG(LangChain + ChromaDB + OpenAI) 로직은 별도 디렉터리에서 개발되어 `backend`가 `RAG_PROVIDER=real`/`CHAT_PROVIDER=real`일 때 그대로 import해서 사용 (저장소 루트 `pyproject.toml`/`uv.lock`으로 backend와 같은 가상환경을 공유)
- **OCR**: CLOVA OCR(`OCR_PROVIDER=clova`) 또는 로컬 목업(`OCR_PROVIDER=mock`)으로 전환 가능

### 데이터 흐름

1. **업로드** — 보호자/환자가 처방전 이미지를 업로드하면 `records_router`가 OCR을 실행하고 결과를 즉시 응답으로 반환(`review_required` 상태)
2. **OCR 저신뢰 항목 재확인** — 보호자가 화면에서 직접 수정·확정(`confirm`)하면 그 요청 안에서 RAG 가이드 생성까지 동기로 이어서 처리
3. **RAG·가이드생성** — 식약처 e약은요/HIRA 약가마스터/DUR 데이터를 검색해 복약·생활습관 가이드를 생성하고, 인용 출처(source_refs)와 병용금기·주의사항 경고를 함께 반환. 같은 약 조합이면 캐시를 재사용해 LLM을 다시 호출하지 않음
4. **챗봇 질의응답** — 환자의 최근 처방·가이드 결과를 컨텍스트로 GPT가 SSE로 실시간 스트리밍 응답, 하단 면책 고지 자동 표시
5. **복약 알림** — 스케줄러가 정시/놓침 알림을 판단해 이메일·Web Push로 발송

---

## 📂 프로젝트 구조

```
.
├── backend/                 # FastAPI 백엔드 (Aiven MySQL / 로컬 SQLite)
│   ├── core/                 # 인프라·횡단 관심사 — auth(JWT), security(PII 암복호화), database(엔진/세션), dependencies(인증 의존성), scheduler(알림)
│   ├── services/              # 도메인 로직 — drug_reference, drug_matcher, parsing_rules, ocr_interface
│   ├── routers/             # auth/records/ocr/rag/chat/monitoring/care 라우터
│   ├── alembic/versions/     # DB 스키마 마이그레이션
│   ├── data/                # HIRA·DUR 등 대용량 로컬 참고 데이터 (git 미추적)
│   ├── tests/
│   ├── models.py            # SQLModel 테이블 정의
│   └── main.py
├── frontend/                 # React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/            # 화면 단위 컴포넌트
│   │   ├── api/               # 백엔드 API 클라이언트
│   │   └── components/
│   └── package.json
├── rag/                       # RAG 파이프라인 (LangChain + ChromaDB)
│   ├── rag/                   # 가이드 생성 로직, 식약처/HIRA/DUR 연동
│   └── tests/
├── pyproject.toml / uv.lock   # backend/ + rag/ 파이썬 의존성 (uv로 관리, 하나의 가상환경 공유)
├── docs/                       # 프로젝트 문서
│   ├── API명세서/              # API 명세서 버전별 문서 + revision_log/
│   ├── ERD/                    # ERD 버전별 문서 + revision_log/
│   ├── 요구사항_정의서/         # 요구사항 정의서 버전별 문서 + revision_log/
│   ├── deviation_log/          # 팀 간 편차·CAPA 로그 (날짜별)
│   ├── troubleshooting_log/    # 트러블슈팅 로그
│   ├── validation_summary/     # 검증 요약 보고서
│   ├── mentoring_report/       # 멘토링 보고서
│   ├── Team Members' Notes/    # 작업 내용 중 팀원이 숙지해야 할 문서 (team-rules.md 등)
│   └── etc/                    # 그 외 참고 문서 (기술 가이드, 계정 정보, 1주차 기획 등)
└── README.md
```

---

## 🚀 시작하기

> ℹ️ 이 README는 초기 기획 당시(Redis Stream + PostgreSQL + S3 + Nginx, 5인 체제) 내용으로 시작했지만,
> [기술 스택](#-기술-스택)/[시스템 아키텍처](#-시스템-아키텍처)/[프로젝트 구조](#-프로젝트-구조)/"시작하기"/"배포"
> 섹션은 모두 실제 코드 기준으로 갱신했습니다.

### 실제 스택

`FastAPI`(동기, Aiven MySQL — 개인 로컬 단독 실행 시엔 SQLite) + `React`(Vite) — Redis/PostgreSQL/S3 없음.

로컬 개발 환경(이 섹션 기준)엔 Nginx도 없이 프론트(5173)·백엔드(8000)에 직접 접속합니다. **배포된 EC2에는 Nginx가 호스트에 직접 설치**돼 있어 HTTPS+도메인으로 접속되지만, 이건 `docker-compose.yml` 밖의 EC2 인스턴스 설정이라 로컬 실행 방법과는 무관합니다 — 자세한 내용은 [시스템 아키텍처](#-시스템-아키텍처)/[배포](#-배포) 참고.

### 사전 요구사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — 백엔드(backend/ + rag/) 파이썬 의존성·가상환경 관리. 팀원마다 pip/venv로 따로 설치하면 버전이 어긋나기 쉬워서, `pyproject.toml`/`uv.lock` 기준으로 `uv sync` 한 번이면 동일한 환경이 만들어지도록 통일했습니다.
- Node.js 20+
- Docker / Docker Compose (선택 — 로컬 개발엔 없어도 됨)

### 1. 저장소 클론

```bash
git clone https://github.com/AI-HealthCare-04/AH_04_02.git
cd AH_04_02
```

### 2. 환경변수 설정

```bash
cp backend/.env.example backend/.env
cp rag/.env.example rag/.env   # RAG_PROVIDER/CHAT_PROVIDER를 real로 쓸 때만 필요
```

각 `.env`를 열어 팀 내 공유된 값(OpenAI/CLOVA 키, `PII_ENCRYPTION_KEY`/`PII_HASH_SECRET` 등)으로 채워주세요.
**절대 실제 키 값을 커밋하지 않습니다.** 값 없이도 OCR/RAG/챗봇은 전부 mock/stub으로 동작합니다.

### 3-A. Docker Compose로 실행 (권장)

```bash
docker compose up --build -d
docker compose ps   # backend(8000), frontend(5173) 정상 실행 확인
```

### 3-B. 직접 실행

```bash
# 백엔드 — 저장소 루트의 pyproject.toml/uv.lock 기준으로 .venv를 만들고 동기화
uv sync
cd backend && uv run uvicorn main:app --reload   # http://localhost:8000

# 프론트엔드 (새 터미널)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

새 패키지가 필요하면 `requirements.txt`를 직접 고치지 말고 `uv add <패키지명>`(저장소 루트에서 실행)으로 추가하세요 — `pyproject.toml`/`uv.lock`이 같이 갱신되어 다른 팀원도 `uv sync`만 하면 동일한 버전을 받습니다.

### 4. 접속 확인

- 프론트: http://localhost:5173
- API 문서(Swagger): http://localhost:8000/docs

### 5. 부하테스트 (선택)

[Locust](https://locust.io/)는 기본 `uv sync`에는 안 설치되는 별도 `loadtest` 그룹입니다 — 필요할 때만 따로 받습니다.

```bash
uv sync --group loadtest
uv run locust -f locustfile.py                                                # 로컬 백엔드(APP_ENV=local) 대상
uv run locust -f locustfile_deploy.py --host https://yakcong.duckdns.org       # 배포 환경, 인증 불필요한 공개 엔드포인트만
uv run locust -f locustfile_deploy_auth.py --host https://yakcong.duckdns.org  # 배포 환경, 실제 로그인 계정 필요(조회만 수행)
```

`locustfile_deploy_auth.py`는 실행 전 `LOCUST_TEST_IDENTIFIER`/`LOCUST_TEST_PASSWORD` 환경변수로 테스트 계정 정보를 넘겨야 합니다(코드에 하드코딩하지 않음). 위 명령을 실행하면 `http://localhost:8089`에서 웹 UI로 동시 사용자 수를 조절하며 볼 수 있습니다. **배포 환경을 대상으로 할 때는 실제 서비스에 부하가 걸리니, 반드시 가볍게(동시 사용자 소수·짧은 시간) 시작해서 단계적으로 올리세요.**

---

## 🤝 협업 규칙

자세한 내용은 [`docs/Team Members' Notes/team-rules.md`](./docs/Team%20Members%27%20Notes/team-rules.md) 참고.

### 브랜치 전략

`main` → `dev` → `feature/*`/`fix/*`/`chore/*`/`docs/*` 구조로 단순화해서 운영합니다.

- `main`, `dev`에는 직접 push하지 않습니다.
- 기능 개발/버그 수정은 `dev`에서 분기한 `feature/기능명_이름` / `fix/내용_이름` 브랜치에서 진행합니다 (예: `feature/ocr-extraction_sh`).
- 별도의 `release`/`hotfix` 단계는 두지 않습니다 (3인 소규모 팀 기준 단순화).

### 커밋 메시지 규칙

```
<타입>: <변경 내용 요약>
```

| 타입 | 용도 |
|---|---|
| feat | 새로운 기능 추가 |
| fix | 버그 수정 |
| refactor | 기능 변화 없는 리팩토링 |
| docs | 문서 수정 |
| test | 테스트 추가/수정 |
| chore | 설정/환경/패키지 작업 |

### PR 규칙

- base: `dev` (배포 시점에 `main`)
- Reviewer 최소 1명 지정, 승인 후 병합
- merge 전 로컬에서 직접 실행 확인 후 push
- 병합 완료된 브랜치는 삭제

### 절대 커밋하지 않는 것

`.env`, API 키, AWS 자격 증명, DB 비밀번호, 실제 진료기록/처방전/환자 개인정보, 원본 의료 이미지, 대용량 모델 파일

### 커뮤니케이션 원칙

- 모든 팀원/멘토 간 호칭은 **OO님**으로 통일
- 피드백은 쿠션어를 사용해 부드럽게 전달
- 모든 공식 정보는 디스코드/노션 등 공식 채널에서 공유 (비공식 채널 단독 공유 금지)
- 기획 문서 변경 시 PR 머지 즉시 반영 및 팀 공유

---

## 📅 프로젝트 일정

전체 기간: **2026.06.16(화) ~ 08.07(금)**

| 기간 | 내용 |
|---|---|
| 1주차 (6월) | OT, 기획 문서화 |
| 2~4주차 (7월) | 초기 세팅, AI 모델링 / API / 화면단 구현 |
| 5주차 (7월) | 구현 고도화, AWS 배포, 서비스 배포 |
| 6주차 (8월) | QA, 발표 준비, 데모데이 |

- 멘토링: 06.29(월) ~ 08.06(목), 주 1회 (정규 수업시간 외)
- 발표 자료 제출 마감: **2026.08.06(목) 23:59**
- 최종 발표/데모데이: **2026.08.07(금)**
- 배포는 종료일 1주 전까지 완료 필요 (평가 기준)

### 1주차 스프린트 계획

각 담당자가 도메인별로 Day 단위 목표와 완료 기준을 정해 진행합니다.

> 아래는 1주차 당시 5인 체제 기준 계획의 원본 기록입니다. 조성아님·김현우님은 이후 하차했고, 현재는 3인(권순현·김영혜·박소정) 체제로 진행 중입니다 — 현재 팀 구성은 위 [팀 소개](#-팀-소개) 참고.

<details>
<summary><b>① OCR·정보추출 — 권순현</b></summary>

| Day | 작업 | 완료 기준 |
|---|---|---|
| 월 | CLOVA OCR 키 발급, 테스트 호출 | 샘플 이미지 1장에서 raw text 출력 성공 |
| 화 | 처방전/약봉투 샘플 5~10장 수집 후 인식 테스트 | 샘플별 인식 성공/실패 표 작성 |
| 수 | 추출 텍스트 → 약품명/용량/복용법 패턴 정리 | REQ-002 JSON 스키마로 1건 변환 성공 |
| 목 | OCR 실패 케이스 처리 (REQ-008) | 흐릿한 이미지 입력 시 에러메시지 반환 확인 |
| 금 | ②에 넘길 출력 포맷 ②와 합의 + 회고 | 인터페이스 문서 1페이지로 정리 |

</details>

<details>
<summary><b>② RAG·가이드생성 — 김영혜</b></summary>

| Day | 작업 | 완료 기준 |
|---|---|---|
| 월 | OpenAI API 키 확인, LangChain 설치, 튜토리얼 1개 실행 | 로컬에서 질의응답 1회 성공 |
| 화 | 식약처 e약은요 API 등에서 의약품 데이터 샘플 확보 | 약품 10건 효능/주의사항 데이터 확보 |
| 수 | FAISS/ChromaDB 벡터DB 구축 | 질의 1건 → 관련문서 top-3 검색 성공 |
| 목 | 복약가이드 생성 프롬프트 v1 작성·테스트 | 약품명 1개 입력 시 가이드문 출력 확인 |
| 금 | ①의 출력 받아 연결 테스트 + 회고 | ①→② 입력→가이드 생성 end-to-end 1건 성공 |

</details>

<details>
<summary><b>③ 챗봇·백엔드 — 조성아</b></summary>

| Day | 작업 | 완료 기준 |
|---|---|---|
| 월 | FastAPI 골격 생성, hello world 엔드포인트 | `/docs` (Swagger) 정상 로딩 |
| 화 | User/MedicalRecord SQLAlchemy 모델 + 마이그레이션 세팅 | 로컬 DB에 테이블 생성 확인 |
| 수 | `POST /medical-records` 스켈레톤(이미지 저장만) | Swagger에서 업로드 테스트 성공 |
| 목 | 챗봇 엔드포인트 스켈레톤 + 비동기 처리 적용 | 더미 응답이라도 200 응답 확인 |
| 금 | ①②결과 받을 인터페이스 자리 비워두기 + API명세서 최신화 | 명세서 swagger와 일치 확인 |

</details>

<details>
<summary><b>④ 프론트·배포·통합 — 박소정</b></summary>

| Day | 작업 | 완료 기준 |
|---|---|---|
| 월 | Figma 생성, 화면 흐름 5개 박스 배치(Mid-Fi 시작) | 화면 5개 + 화살표 1차 완성 |
| 화 | 업로드화면·가이드결과화면 상세 작업 | 2개 화면 컴포넌트 배치 확정 |
| 수 | 프론트 프로젝트 세팅 + 업로드화면 정적 구현 | 로컬 실행 시 업로드화면 렌더링 |
| 목 | Docker Compose 초안(backend+db 서비스 정의) | `docker-compose up` 시 컨테이너 정상 기동 |
| 금 | 4명 코드 1차 통합 시도(merge 충돌 점검) + 회고 | develop 브랜치 merge 충돌 없이 완료 |

</details>

---

## 🐛 트러블슈팅

개발 중 발생한 주요 문제와 해결 과정을 기록합니다. 단순 오류 메시지보다 **원인 분석 → 해결 방법 → 재발 방지책** 순으로 작성하는 것을 권장합니다.

> 상세 기록은 [`docs/troubleshooting_log/troubleshooting-log.md`](./docs/troubleshooting_log/troubleshooting-log.md) 에 누적합니다. 아래는 주요 이슈 요약입니다.

| 날짜 | 담당 | 문제 | 원인 | 해결 |
|---|---|---|---|---|
| 2026-08-05 | 박소정 | Locust 부하테스트 중 동시접속 ~30명 근처에서 `502`/`504` 발생 | SQLAlchemy 커넥션 풀 기본값(워커당 15개)이 Aiven `max_connections=76`에 비해 여유가 부족했음 | `APP_ENV`별로 풀 크기 재조정(production 워커당 20개, development 인스턴스당 5개) — 재측정으로 50명까지 무결점 확인 ([PR #173](https://github.com/AI-HealthCare-04/AH_04_02/pull/173)) |

### 기록 가이드

- 비밀키·개인정보를 실수로 커밋한 경우, 파일 삭제만으로는 부족합니다. 즉시 팀에 공유 → 키 폐기/재발급 → Git 기록 정리 여부 판단까지의 과정을 반드시 기록합니다.
- `dev` 머지 충돌 해결 과정처럼 협업 중 반복될 수 있는 이슈는 원인과 함께 남겨 다음 충돌 시 참고할 수 있도록 합니다.
- AI 모델/추론 관련 이슈(성능 편차, 추론 실패 케이스 등)는 평가 항목(3-1, 3-3)과도 연결되므로 수치와 함께 기록합니다.

---

## ☁️ 배포

> [2026-07-28 갱신] 아래 "후보 배포 방식 미검토" 내용은 실제 배포 전에 작성된 초안이 그대로 남아있던 것입니다 — 현재는 EC2 + GitHub Actions로 실제 배포되어 있습니다.

- **현재 상태**: `dev` 브랜치에 push되면 `.github/workflows/ci.yml`의 `deploy` job이 SSH로 EC2에 접속해 최신 코드를 받고, **마이그레이션을 적용한 뒤(`alembic upgrade head`) 컨테이너를 강제로 재생성(`--force-recreate`)** — **자동 배포됨.**
  - [2026-08-04] 예전엔 `docker compose up -d --build`만 실행했는데, `backend/Dockerfile`이 코드를 이미지에 안 넣고 바인드마운트로만 받는 구조라 코드만 바뀌면 이미지 해시가 그대로라 **컨테이너가 재생성되지 않고, 스키마 마이그레이션도 안 걸리는** 실제 장애가 있었습니다(배포 7회·20시간 동안 최신 코드가 반영 안 됨). [PR #157](https://github.com/pecs0310/AH_04_02/pull/157)로 수정 — 배포 전 반드시 이 흐름을 유지해야 합니다.
- **구성**: FastAPI + React(Vite) 컨테이너 2개(`docker-compose.yml`), DB는 팀 공용 Aiven MySQL(`DATABASE_URL`). **로컬 개발과 다른 점**: EC2에는 호스트에 직접 설치한 **Nginx**가 두 컨테이너 앞에서 HTTPS(Duck DNS 도메인)와 `/api` 경로 라우팅을 담당 — 이 설정은 저장소에 없고 EC2 인스턴스에만 있음

### 배포 시 로컬 개발과 다른 점 — 특히 `.env`

배포 스텝은 코드만 받아오고 **`.env`는 절대 건드리지 않습니다** (`.gitignore`돼 있어 git에 없음). 즉 EC2의 `backend/.env`는 로컬 `.env`와 별개로, 필요할 때 **직접 SSH로 들어가 손으로** 갱신해야 합니다 — 특히 `CORS_ALLOWED_ORIGINS`(프론트 도메인 추가)나 `VITE_MONITORING_API_URL`(백엔드 도메인) 같은 값이 바뀌었는데 EC2 쪽을 안 고치면 로그인부터 막힙니다. 체크리스트는 [`docs/Team Members' Notes/env-var-checklist.md`](./docs/Team%20Members%27%20Notes/env-var-checklist.md) 참고.

`VITE_*` 값처럼 프론트 **빌드 시점**에 박히는 값을 바꿨다면, 컨테이너 재시작(`restart`)만으로는 반영되지 않고 재빌드(`up -d --build`)가 필요합니다.

### 실측 처리량 (2026-08-05~06, Locust 부하테스트)

배포 환경(EC2 t3.medium, FastAPI 워커 2개)에 Locust(위 [시작하기](#-시작하기) 5번 참고)로 실제 로그인 계정을 이용해 조회 API 부하테스트를 진행해 실제 한계를 확인했습니다.

- **커넥션 풀 조정 전**: 동시접속 **~30명** 근처에서 SQLAlchemy 커넥션 풀 소진으로 `502`/`504` 발생
- **`APP_ENV`별 풀 크기 조정 후**([PR #173](https://github.com/AI-HealthCare-04/AH_04_02/pull/173)): 동시접속 **50명까지 무결점**, **80명대**부터 Aiven `max_connections=76` 한도에 실제로 부딪혀 `500` 에러 발생(재현 확인). 서버(컨테이너)는 이 구간에서도 다운되지 않고 에러 응답만 정상적으로 돌려줌
- 응답속도도 동시접속자 수에 비례해 느려짐 — 50명까지는 2~4초대, 80명대에서는 지속시간이 길어질수록 최대 30초 이상까지 저하
- 동시접속 **200명** 규모까지 안정적으로 처리하려면 이번 풀 조정만으로는 부족하고, 쿼리 최적화(N+1·PII 복호화 비용 등) + Aiven/EC2 플랜 업그레이드가 추가로 필요할 것으로 판단됨(비동기 전환은 리스크 대비 효과가 낮아 우선순위 낮음)

---

## 📄 참고 문서

- [팀 협업 규칙 (team-rules.md)](./docs/Team%20Members%27%20Notes/team-rules.md)
- [요구사항 정의서](./docs/요구사항_정의서/) / [ERD](./docs/ERD/) / [API 명세서](./docs/API명세서/) — 버전별 문서, 변경 이력은 각 폴더의 `revision_log/` 참고
