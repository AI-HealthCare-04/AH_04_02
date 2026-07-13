# 💊 진료 기록 기반 복약 안내 및 생활습관 개선 가이드 자동 생성 시스템

> AI 헬스케어 4기 파이널 프로젝트 · 2팀 · Uponati(어포나티) 참여기업 주제

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://www.docker.com/)
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
| 김영혜 | RAG·가이드생성 (LangChain, 벡터DB, 복약 가이드 생성) |
| 조성아 | 챗봇·백엔드 (FastAPI, DB 모델링, 챗봇 API) |
| 박소정 | 프론트·배포·통합 (화면 구현, Docker Compose, 통합 테스트) |
| 김현우 | TBD |

> 역할 분담은 1주차 스프린트 기준이며, 추후 변경 시 업데이트합니다.

---

## 🛠 기술 스택

### Backend
`FastAPI` `Uvicorn` `Python 3.13` `uv`

### AI / LLM
`LangChain` `OpenAI API` `CLOVA OCR` `sentence-transformers`

### Database & Cache
`PostgreSQL` `Redis (Stream / Pub-Sub)`

### Infra & Deploy
`Docker` `Docker Compose` `Nginx` `AWS EC2` `AWS S3`

### 협업 도구
`Git / GitHub` `Notion` `Discord` `ZEP`

> 프론트엔드 스택은 팀 논의 후 확정되는 대로 업데이트합니다.

---

## 🏗 시스템 아키텍처

AI 추론처럼 응답 시간이 긴 작업을 FastAPI가 직접 처리하면 서버가 다른 요청을 받지 못하게 되는 문제를 막기 위해, **Producer–Consumer 패턴**을 적용합니다.

```
Client (사용자 / 보호자)
       │
       ▼
Nginx (리버스 프록시, SSL 종단, SSE 연결 유지)
       │
       ▼
FastAPI (Producer) ──→ PostgreSQL
       │  XADD (작업 등록)
       ▼
Redis Stream (메시지 브로커)
       │  XREAD (Consumer Group)
       ▼
┌─────────────┬─────────────┬─────────────┐
│ OCR Worker  │ RAG Worker  │ Chat Worker │
│ (CLOVA OCR) │ (LangChain  │ (asyncio,   │
│   ①권순현   │  + FAISS)   │   SSE)      │
│             │   ②김영혜   │   ③조성아   │
└─────────────┴─────────────┴─────────────┘
       │             │             │
       ▼             ▼             ▼
    AWS S3      Vector DB      PostgreSQL
   (이미지)       (FAISS)      (가이드/이력)
       │             │             │
       └─────────────┴─────────────┘
                    │
            Redis Pub/Sub (결과 발행)
                    │
                    ▼
            FastAPI → SSE → Client
```

- **Nginx**: 리버스 프록시, SSL 종단, 정적 파일 처리
- **FastAPI**: 요청 접수 및 비즈니스 로직 처리, Redis Stream에 작업 등록 후 SSE로 결과 전달
- **Redis**: 메시지 브로커 및 작업 큐 (Stream), FastAPI-Worker 간 디커플링, Consumer Group으로 수평 확장
- **OCR / RAG / Chat Worker**: 역할별로 분리된 Consumer. 장애 시 Redis XCLAIM으로 작업 재할당
- **PostgreSQL**: 사용자, 의료기록, 가이드 결과, 대화 이력 저장 *(MySQL→PostgreSQL 변경 검토 중, 추후 확정 시 업데이트)*
- **AWS S3**: 처방전 원본 이미지, 모델 파일 저장
- **FAISS**: 식약처 의약품 데이터 임베딩 기반 벡터 검색

### 데이터 흐름

1. **업로드** — 사용자/보호자가 처방전 이미지 업로드 → FastAPI가 S3 저장 후 Redis에 작업 등록, 즉시 "접수 완료" 응답
2. **OCR·정보추출** (①) — OCR Worker가 CLOVA OCR로 약품명/용량/복용법/진단명 추출 → REQ-002 JSON 스키마로 변환, 실패 시 REQ-008 기준 에러 응답
3. **RAG·가이드생성** (②) — RAG Worker가 FAISS로 식약처 데이터 검색(top-3) → 복약 가이드 및 생활습관 가이드 생성, 출처(source_refs) 명시
4. **결과 전송** (③) — 완료 시 Redis Pub/Sub으로 신호 → FastAPI가 SSE로 클라이언트에 결과 스트리밍
5. **챗봇 질의응답** (③) — 추가 질문 시 Chat Worker가 대화 이력(ChatHistory) 기반으로 SSE 스트리밍 응답, 하단 면책 고지 자동 표시

---

## 📂 프로젝트 구조

```
.
├── ai_worker/              # AI 추론/학습 워커 (Redis Stream Consumer)
│   ├── core/               # Redis 설정, 워커 옵션
│   ├── schemas/            # Worker 전용 데이터 스키마
│   ├── tasks/              # 백그라운드 작업 정의 (inference, training 등)
│   ├── Dockerfile
│   └── main.py
├── app/                    # FastAPI 백엔드 서버 (Redis Stream Producer)
│   ├── apis/               # API 라우터
│   ├── core/               # 공통 설정, DB, JWT, 로깅
│   ├── dependencies/       # 의존성 주입 (인증/인가 등)
│   ├── dtos/                # 요청/응답 스키마 (Pydantic)
│   ├── models/              # DB 모델
│   ├── repositories/        # 데이터 액세스 계층
│   ├── services/            # 비즈니스 로직
│   ├── tests/                # 테스트 코드
│   ├── Dockerfile
│   └── main.py
├── docs/                    # 프로젝트 문서
│   ├── README.md
│   └── team-rules.md        # 팀 GitHub 협업 규칙
├── envs/                     # 환경변수 템플릿
│   ├── example.local.env
│   └── example.prod.env
├── infra/                    # 배포 인프라 설정
│   ├── docker/
│   └── nginx/
├── scripts/                  # 자동화 스크립트
│   ├── ci/
│   ├── certbot.sh             # SSL 인증서 발급 자동화
│   └── deployment.sh          # 배포 자동화
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

---

## 🚀 시작하기

> ⚠️ 이 README의 [기술 스택](#-기술-스택)/[시스템 아키텍처](#-시스템-아키텍처)/[프로젝트 구조](#-프로젝트-구조) 섹션은
> 초기 기획 당시(Redis Stream + PostgreSQL + S3 + Nginx, 5인 체제) 내용이 그대로 남아있어 실제 코드와
> 다릅니다 — 아래 "시작하기"/"배포"는 실제 코드 기준으로 갱신했고, 나머지 섹션은 별도 문서 정리 작업으로
> 남겨뒀습니다.

### 실제 스택

`FastAPI`(동기, SQLite) + `React`(Vite) — Redis/PostgreSQL/S3/Nginx 없음.

### 사전 요구사항

- Python 3.13+
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
cp rag-prototype/.env.example rag-prototype/.env   # RAG_PROVIDER/CHAT_PROVIDER를 real로 쓸 때만 필요
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
# 백엔드
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload   # http://localhost:8000

# 프론트엔드 (새 터미널)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

### 4. 접속 확인

- 프론트: http://localhost:5173
- API 문서(Swagger): http://localhost:8000/docs

---

## 🤝 협업 규칙

자세한 내용은 [`docs/team-rules.md`](./docs/team-rules.md) 참고.

### 브랜치 전략 — Git Flow

```
main
 └─ develop
     ├─ release/*    배포 준비
     ├─ hotfix/*      운영 중 긴급 수정
     ├─ feat/*         기능 개발
     ├─ fix/*          버그 수정
     ├─ refactor/*     리팩토링
     ├─ docs/*         문서 작업
     └─ chore/*        설정/환경 작업
```

- `main`, `develop`에는 직접 push하지 않습니다.
- 기능 개발은 `develop`에서 분기한 `feature/기능명` 브랜치에서 진행합니다.
- 배포 준비는 `develop → release/*` 분기 후 테스트, 완료되면 `main`과 `develop` 양쪽에 병합합니다.
- 운영 중 긴급 버그는 `main`에서 분기한 `hotfix/*`로 수정 후 `main`, `develop` 양쪽에 병합합니다.

### 커밋 메시지 규칙

```
<이모지> <타입>: <변경 내용 요약>
```

| 타입 | 용도 |
|---|---|
| ✨ feat | 새로운 기능 추가 |
| 🐛 fix | 버그 수정 |
| ♻️ refactor | 기능 변화 없는 리팩토링 |
| 📝 docs | 문서 수정 |
| ✅ test | 테스트 추가/수정 |
| 💡 chore | 설정/환경/패키지 작업 |
| 🚑 hotfix | 긴급 수정 |

### PR 규칙

- base: `develop` (배포 통합 시 `main`)
- Reviewer 최소 1명 지정, 승인 후 병합
- 병합 방식: `develop`까지는 Squash and merge, `develop → main`은 일반 Merge
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
- `develop` 머지 충돌 해결 과정처럼 협업 중 반복될 수 있는 이슈는 원인과 함께 남겨 다음 충돌 시 참고할 수 있도록 합니다.
- AI 모델/추론 관련 이슈(성능 편차, 추론 실패 케이스 등)는 평가 항목(3-1, 3-3)과도 연결되므로 수치와 함께 기록합니다.

---

## ☁️ 배포

- **현재 상태**: 로컬 Docker Compose(`docker-compose.yml`)로 backend(8000)/frontend(5173) 컨테이너 기동 확인 완료. **실제 클라우드 배포는 아직 안 함.**
- **구성**: FastAPI(SQLite, 동기) + React(Vite) 2개 컨테이너뿐 — Redis/PostgreSQL/S3/Nginx 없음
- **배포 링크**: _아직 없음_

### 배포 시 로컬 개발과 달라지는 점

`docker-compose.yml`은 소스를 바인드 마운트하고 `backend/.env`/`rag-prototype/.env` 파일을 그대로 읽는 로컬 개발용 구성입니다. 실제 서버(EC2/Render/Railway 등)에 올릴 땐 아래를 반드시 바꿔야 합니다.

1. **환경변수 주입 방식** — 바인드 마운트된 `.env` 파일 대신, 배포 플랫폼의 환경변수/시크릿 기능으로 `SECRET_KEY`, `PII_ENCRYPTION_KEY`, `PII_HASH_SECRET`, (필요시) `OPENAI_API_KEY`, `DATA_GO_KR_SERVICE_KEY`, `CLOVA_OCR_*`를 주입
2. **`VITE_MONITORING_API_URL`** — 프론트 빌드 시 `http://localhost:8000` 대신 실제 배포된 백엔드 도메인으로 설정 (`frontend/src/api/monitoringClient.ts` 참고)
3. **CORS `allow_origins`** — `backend/main.py`에 배포된 프론트 도메인 추가
4. **`--reload` 제거** — 개발용 Dockerfile은 `uvicorn --reload`를 쓰는데, 운영에서는 빼는 게 안전(코드 변경 시 불필요한 재시작 방지)
5. **SQLite 파일 영속성** — `backend/app.db`가 컨테이너 안에만 있으면 재배포 시 데이터가 날아감 — 볼륨 마운트 필요

### 후보 배포 방식 (아직 미결정)

- **가장 간단**: Render/Railway 같은 PaaS에 backend/frontend 각각 서비스로 올리기 (Dockerfile 이미 있어서 바로 사용 가능)
- **직접 제어**: EC2 1대 + `docker compose up -d` (지금 로컬 구성과 거의 동일하게 유지 가능)

---

## 📄 참고 문서

- [팀 협업 규칙 (team-rules.md)](./docs/team-rules.md)
- 요구사항 정의서 / ERD / API 명세서: `docs/` 폴더 내 추가 예정
