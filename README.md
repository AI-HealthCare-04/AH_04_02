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
9. [배포](#-배포)

---

## 📖 프로젝트 소개

### 한 줄 소개

사용자의 진료 기록과 복약 정보를 바탕으로, **LLM이 맞춤형 복약·생활습관 가이드를 자동으로 생성**하고, **OCR로 처방전/약봉투를 인식**하며, **실시간 챗봇**으로 사용자의 질의에 응답하는 AI 헬스케어 웹 서비스입니다.

### 배경 및 목적

의료 기록은 개인 맞춤형 의료 서비스 구현의 핵심 데이터입니다. 이 프로젝트는 LLM 기술을 활용해 복약 안내 및 건강 가이드를 자동화하고, AI 모델 서빙과 헬스케어 서비스 연계 역량을 강화하는 실무형 프로젝트로 기획되었습니다. 질병 예측, 환자 건강 모니터링, 의료 상담 챗봇 등 실질적인 문제 해결을 목표로 합니다.

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
| 권순현 | TBD |
| 김영혜 | TBD |
| 박소정 | TBD |
| 조성아 | TBD |
| 김현우 | TBD |

> 역할 분담은 추후 확정되는 대로 업데이트합니다.

---

## 🛠 기술 스택

### Backend
`FastAPI` `Uvicorn` `Python 3.13` `uv`

### AI / LLM
`LangChain` `OpenAI API` `CLOVA OCR` `sentence-transformers`

### Database & Cache
`MySQL` `Redis (Stream / Pub-Sub)`

### Infra & Deploy
`Docker` `Docker Compose` `Nginx` `AWS EC2` `AWS S3`

### 협업 도구
`Git / GitHub` `Notion` `Discord` `ZEP`

> 프론트엔드 스택은 팀 논의 후 확정되는 대로 업데이트합니다.

---

## 🏗 시스템 아키텍처

AI 추론처럼 응답 시간이 긴 작업을 FastAPI가 직접 처리하면 서버가 다른 요청을 받지 못하게 되는 문제를 막기 위해, **Producer–Consumer 패턴**을 적용합니다.

```
Client → Nginx (Reverse Proxy)
            │
            ▼
        FastAPI (Producer)
            │  XADD (작업 등록)
            ▼
        Redis Stream (Message Broker)
            │  작업 소비
            ▼
        AI Worker (Consumer)
            │  모델 로드(S3) → 추론/학습
            ▼
        Redis Pub/Sub (결과 발행)
            │
            ▼
        FastAPI → SSE → Client (실시간 결과 전달)
```

- **Nginx**: 리버스 프록시, SSL 종단, 정적 파일 처리
- **FastAPI**: 요청 접수 및 비즈니스 로직 처리, Redis Stream에 작업 등록 후 SSE로 결과 전달
- **Redis**: 메시지 브로커 및 작업 큐 (Stream), FastAPI-Worker 간 디커플링
- **AI Worker**: 실제 모델 추론/학습 수행, Consumer Group으로 수평 확장 가능
- **MySQL**: 사용자/서비스 데이터 저장
- **AWS S3**: 모델 파일 및 미디어 저장소

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

### 사전 요구사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker / Docker Compose

### 1. 저장소 클론

```bash
git clone https://github.com/pecs0310/Final_medication_guidance_based_on_medical_records.git
cd Final_medication_guidance_based_on_medical_records
```

### 2. 의존성 설치

```bash
uv sync --all-groups --frozen
```

### 3. 환경변수 설정

```bash
cp envs/example.local.env envs/.local.env
ln -s envs/.local.env .env
```

`.env` 파일을 열어 팀 내 공유된 값(DB 계정, API 키 등)으로 채워주세요. **절대 실제 키 값을 커밋하지 않습니다.**

### 4. 서버 실행

```bash
docker compose up --build -d
docker ps   # 컨테이너 정상 실행 확인
```

### 5. 접속 확인

- API 문서(Swagger): http://localhost/api/docs

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

---

## ☁️ 배포

- **배포 환경**: AWS EC2 (Ubuntu) + Docker Compose
- **구성**: Nginx → FastAPI → Redis Stream → AI Worker, MySQL, S3
- **배포 링크**: _추후 업데이트_
- **API 문서**: _추후 업데이트_

배포 절차는 [Docker를 활용한 EC2 백엔드 서버 배포 가이드]와 [FastAPI + Docker 자동화 스크립트 가이드]를 참고합니다.

---

## 📄 참고 문서

- [팀 협업 규칙 (team-rules.md)](./docs/team-rules.md)
- 요구사항 정의서 / ERD / API 명세서: `docs/` 폴더 내 추가 예정
