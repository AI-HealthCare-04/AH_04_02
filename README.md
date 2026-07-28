# 💊 진료 기록 기반 복약 안내 및 생활습관 개선 가이드 자동 생성 시스템

> AI 헬스케어 4기 파이널 프로젝트 · 2팀 · Uponati(어포나티) 참여기업 주제

[![Python](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-SQLite-009688)](https://fastapi.tiangolo.com/)
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
`FastAPI` `Uvicorn` `Python 3.13+` `SQLModel` `SQLite` `uv`

### AI / LLM
`LangChain` `OpenAI API (gpt-4o-mini)` `CLOVA OCR` `sentence-transformers` `ChromaDB`

### Frontend
`React` `TypeScript` `Vite`

### 협업 도구
`Git / GitHub` `Notion` `Discord`

> 3인 소규모 팀 체제로, SQLModel 기반 동기 처리로 단순화해 운영 중입니다. 배포(AWS EC2 + GitHub Actions 자동 배포)는 [☁️ 배포](#-배포) 참고.

---

## 🏗 시스템 아키텍처

3인 소규모 팀 체제에 맞춰, 별도 메시지 브로커/워커 없이 **FastAPI 단일 프로세스가 동기 방식으로 처리**하는 단순한 구조로 운영 중입니다. 응답이 느린 외부 호출(CLOVA OCR, OpenAI)은 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않도록만 처리합니다.

```
Client (React + Vite, 사용자 / 보호자)
       │  HTTP (axios)
       ▼
FastAPI (backend/main.py)
       │
       ├─ auth_router      로그인(이메일/전화번호+비밀번호), JWT 발급
       ├─ records_router    처방전 업로드 → OCR 실행 → RAG 가이드 생성까지 한 요청에서 처리
       ├─ ocr_router        CLOVA OCR 연동 (asyncio.to_thread로 감싼 동기 호출)
       ├─ rag_router        복약·생활습관 가이드 생성 (rag/ 연동, asyncio.to_thread)
       ├─ chat_router       환자 처방·가이드 컨텍스트 기반 GPT 챗봇
       ├─ monitoring_router 보호자용 환자 목록·복약 모니터링
       └─ care_router       보호자-환자 연결, 알림 설정, 돌봄 등급 평가
       │
       ▼
   SQLite (backend/app.db)
```

- **FastAPI**: 요청을 받아 그 자리에서 처리 후 바로 응답 (별도 작업 큐·SSE 스트리밍 없음)
- **SQLite**: 환자/보호자/처방전/가이드/알림설정 등 전체 데이터 저장 — 설치 없이 파일 하나로 동작
- **rag/**: RAG(LangChain + ChromaDB + OpenAI) 로직은 별도 디렉터리에서 개발되어 `backend`가 `RAG_PROVIDER=real`/`CHAT_PROVIDER=real`일 때 그대로 import해서 사용 (저장소 루트 `pyproject.toml`/`uv.lock`으로 backend와 같은 가상환경을 공유)
- **OCR**: CLOVA OCR(`OCR_PROVIDER=clova`) 또는 로컬 목업(`OCR_PROVIDER=mock`)으로 전환 가능

### 데이터 흐름

1. **업로드** — 보호자/환자가 처방전 이미지를 업로드하면 `records_router`가 OCR을 실행하고, 필요 시 RAG 가이드 생성까지 이어서 처리한 뒤 결과를 그대로 응답으로 반환
2. **OCR 저신뢰 항목 재확인** — OCR 인식 신뢰도가 낮으면 `review_required` 상태로 남기고, 보호자가 화면에서 직접 수정·확정(`confirm`)하면 그 값으로 RAG 가이드를 생성
3. **RAG·가이드생성** — 식약처 e약은요/HIRA 약가마스터/DUR 데이터를 검색해 복약·생활습관 가이드를 생성하고, 인용 출처(source_refs)와 병용금기·주의사항 경고를 함께 반환
4. **챗봇 질의응답** — 환자의 최근 처방·가이드 결과를 컨텍스트로 GPT가 답변을 생성, 하단 면책 고지 자동 표시

---

## 📂 프로젝트 구조

```
.
├── backend/                 # FastAPI 백엔드 (SQLite)
│   ├── core/                 # 인프라·횡단 관심사 — auth(JWT), security(PII 암복호화), database(엔진/세션), dependencies(인증 의존성)
│   ├── services/              # 도메인 로직 — drug_reference, drug_matcher, parsing_rules, ocr_interface
│   ├── routers/             # auth/records/ocr/rag/chat/monitoring/care 라우터
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
├── API명세서/                 # API 명세서 버전별 문서
├── ERD/                       # ERD 버전별 문서
├── 요구사항_정의서/            # 요구사항 정의서 버전별 문서
├── docs/                       # 그 외 프로젝트 문서 (team-rules.md, revision_logs 등)
└── README.md
```

---

## 🚀 시작하기

> ℹ️ 이 README는 초기 기획 당시(Redis Stream + PostgreSQL + S3 + Nginx, 5인 체제) 내용으로 시작했지만,
> [기술 스택](#-기술-스택)/[시스템 아키텍처](#-시스템-아키텍처)/[프로젝트 구조](#-프로젝트-구조)/"시작하기"/"배포"
> 섹션은 모두 실제 코드 기준으로 갱신했습니다.

### 실제 스택

`FastAPI`(동기, SQLite) + `React`(Vite) — Redis/PostgreSQL/S3/Nginx 없음.

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

---

## 🤝 협업 규칙

자세한 내용은 [`docs/team-rules.md`](./docs/team-rules.md) 참고.

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

> 상세 기록은 [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md) 에 누적합니다. 아래는 주요 이슈 요약입니다.

| 날짜 | 담당 | 문제 | 원인 | 해결 |
|---|---|---|---|---|
| - | - | _아직 기록된 이슈 없음_ | - | - |

### 기록 가이드

- 비밀키·개인정보를 실수로 커밋한 경우, 파일 삭제만으로는 부족합니다. 즉시 팀에 공유 → 키 폐기/재발급 → Git 기록 정리 여부 판단까지의 과정을 반드시 기록합니다.
- `dev` 머지 충돌 해결 과정처럼 협업 중 반복될 수 있는 이슈는 원인과 함께 남겨 다음 충돌 시 참고할 수 있도록 합니다.
- AI 모델/추론 관련 이슈(성능 편차, 추론 실패 케이스 등)는 평가 항목(3-1, 3-3)과도 연결되므로 수치와 함께 기록합니다.

---

## ☁️ 배포

> [2026-07-28 갱신] 아래 "후보 배포 방식 미검토" 내용은 실제 배포 전에 작성된 초안이 그대로 남아있던 것입니다 — 현재는 EC2 + GitHub Actions로 실제 배포되어 있습니다.

- **현재 상태**: `dev` 브랜치에 push되면 `.github/workflows/ci.yml`의 `deploy` job이 SSH로 EC2에 접속해 `git pull origin dev && docker compose up -d --build`를 실행 — **자동 배포됨.**
- **구성**: FastAPI + React(Vite) 컨테이너 2개(`docker-compose.yml`), DB는 팀 공용 Aiven MySQL(`DATABASE_URL`) — 로컬 개발과 동일한 구성을 그대로 씀

### 배포 시 로컬 개발과 다른 점 — 특히 `.env`

배포 스텝은 코드만 `git pull`하고 **`.env`는 절대 건드리지 않습니다** (`.gitignore`돼 있어 git에 없음). 즉 EC2의 `backend/.env`는 로컬 `.env`와 별개로, 필요할 때 **직접 SSH로 들어가 손으로** 갱신해야 합니다 — 특히 `CORS_ALLOWED_ORIGINS`(프론트 도메인 추가)나 `VITE_MONITORING_API_URL`(백엔드 도메인) 같은 값이 바뀌었는데 EC2 쪽을 안 고치면 로그인부터 막힙니다. 체크리스트는 [`docs/env-var-checklist.md`](./docs/env-var-checklist.md) 참고.

`VITE_*` 값처럼 프론트 **빌드 시점**에 박히는 값을 바꿨다면, 컨테이너 재시작(`restart`)만으로는 반영되지 않고 재빌드(`up -d --build`)가 필요합니다.

---

## 📄 참고 문서

- [팀 협업 규칙 (team-rules.md)](./docs/team-rules.md)
- [요구사항 정의서](./요구사항_정의서/) / [ERD](./ERD/) / [API 명세서](./API명세서/) — 버전별 문서, 변경 이력은 [`docs/revision_logs/`](./docs/revision_logs/) 참고
