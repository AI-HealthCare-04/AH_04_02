# 건강동행 프로젝트 — 세션 인수인계 문서
> 작성일: 2026-07-07 (야간~새벽 세션 반영) / 다음 채팅에서 이 파일을 업로드하면 바로 이어서 진행 가능
> ⚠️ 멘토링 **7/8(수) 20시로 연기됨** (팀원 1명 불참으로 7/7 예정에서 변경)

---

## 🟢 7/8 최종 마무리 — git 정리 및 dev 병합 완료

- **PR #9 처리 완료**: 코멘트로 통합 내역 남기고 Close (git merge 아닌 텍스트 포팅 방식이었음을 명시)
- **저장소 대청소 완료** (`5ddc5cb`): 1주차 MySQL/Docker 템플릿(`app/`, `ai_worker/`, `infra/`, `scripts/`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`, `envs/`) + 루트에 잘못 생겼던 `node_modules/`, `package.json` 전부 삭제
- **`feature/frontend-setup_sojung` → `dev` 병합 완료** (`351e544`): `dev`가 이제 공식적으로 `backend/`+`frontend/`(schedule_v6, SQLite) 기준. 충돌 해결 원칙: 옛 `app/`·`ai_worker/` 관련은 전부 삭제 유지, `docs/` 문서류는 재구성된 최신 버전 유지, 권순현 개인 작업 폴더(`AH_04_02_soonhyun/`)는 본인 소관이라 손대지 않고 유지
- **김영혜에게 구조 변경 공지 완료** — 본인 브랜치를 새 `dev` 기준으로 맞출 때 오늘 같은 충돌 겪을 수 있음을 미리 안내함
- **로컬 정리**: 조사용으로 받았던 `review-branch`, `pr9-ocr` 임시 브랜치 삭제 완료. 순현님 개인 브랜치(`feature/ocr-day1-setup_soonhyun`)는 원격에 그대로 보존
- **팀 노션 페이지 확인**: Team Rule/Weekly Objective/Daily Check List 등은 빈 템플릿 상태, References(34개 문헌)만 채워져 있음 — Trouble Shootings/Daily Scrum/Development Task 초안 텍스트 전달해서 사용자가 직접 붙여넣음 (Claude의 Notion 직접 쓰기 연동은 미보유 상태였음)

### 최종 브랜치 상태
```
dev                              — backend/frontend 기준으로 확정, 최신
feature/frontend-setup_sojung    — dev와 동기화됨
main                             — 별도 (건드리지 않음)
```

## 🔴 7/8 발견: dev 브랜치가 schedule_v6(backend/frontend) 전환을 아직 반영 안 함 (해결됨, 위 항목 참고)

- **`dev` 브랜치**: 옛 `app/`(MySQL 템플릿) 구조 그대로. `backend/`, `frontend/` 폴더 자체가 없음. 권순현의 OCR 작업은 `AH_04_02_soonhyun/`라는 개인 격리 폴더에 있음(PR #9 본인이 "records_router.py로 흡수 예정"이라고 명시 — 통합 전 단계라는 걸 스스로 인지하고 있는 상태, 문제 아님)
- **`feature/frontend-setup_sojung`(본인 브랜치)**: `backend/`+`frontend/`(schedule_v6, SQLite) 구조 전체. `dev` 대비 10 커밋 앞, 43 커밋 뒤처짐
- 원인: schedule_v6(SQLite 전환)를 **권순현이 직접 작성**했지만(조장 아님, 7/8 정정), 그 구조가 아직 `dev`에 병합된 적이 없음. 각자 계획은 알고 있으나 브랜치 통합이 안 된 순수 절차 문제
- PR #9 그대로 머지 시도했다가 `app/`, `docs/` 관련없는 파일에서 충돌 발생 → `git merge --abort`로 중단함(정상 처리)
- **다음 세션 액션**: 권순현과 "dev를 backend/frontend 기준으로 업데이트할지" 팀 합의 필요. 합의 전까지 dev에 push 금지, 본인 작업은 `feature/frontend-setup_sojung`에 안전하게 있음(push 완료 확인됨)

## 🔴 7/7 밤샘 세션 요약 (반드시 먼저 읽을 것)

### 1. iCloud livelock — 완전히 해결됨 (확정)
- 프로젝트를 `~/dev/Final_medication_guidance_based_on_medical_records/`로 실제 이동 완료. Vite/uvicorn 둘 다 이 경로에서 정상 기동 확인됨
- **Desktop 쪽 옛 경로에 iCloud 잔재(빈 껍데기) 남아있음** — 실제 파일 아님, 안전하게 삭제 가능:
  ```bash
  rm -rf ~/Desktop/AI_Health_care/18.\ 최종프로젝트_진료\ 기록\ 기반\ 복약\ 안내\ 및\ 생활\ 습관\ 개선\ 가이드\ 자동\ 생성\ 시/git/Final_medication_guidance_based_on_medical_records
  ```
- git 원격 연결(GitHub) 정상 유지 확인 — `.git` 폴더가 통째로 같이 이동해서 `origin` 그대로 살아있음. `git remote -v`로 재확인 가능

### 2. 충격적 발견 — App.tsx가 라우터가 아니라 Figma Make 프로토타입이었음
- 실제 프로젝트의 `App.tsx`는 그동안 채팅에서 만든 라우터 버전이 아니라, **22개 화면을 `screen` state 하나로 전환하는 Figma Make 통짜 스캐폴드**였음 (react-router-dom 자체를 안 씀)
- 화면 상단에 떠 있던 검은 메뉴바("① 랜딩 ② 로그인 ... ㉑ OCR오류")가 바로 이 스캐폴드의 데모 스위처였음 — 유일하게 작동하던 네비게이션
- **원본은 `App.figma-export.tsx.bak`으로 백업 후 보관 중** (안 지워짐, 나중에 화면 추출용으로 계속 씀)
- 라우터 버전으로 교체 완료, 정상 작동 확인

### 3. 더 충격적인 발견 — pages/, components/ 폴더가 실제 프로젝트에 아예 없었음
- 그동안 채팅에서 만든 `Landing.tsx`, `Login.tsx`, `Dashboard.tsx`, `Upload.tsx`, `Processing.tsx`, `Result.tsx`, `Check.tsx`, `Select.tsx`, `Connect.tsx`, `Chat.tsx`, `InviteAccept.tsx`, `NavBar.tsx` 등 전부 **다운로드 파일로만 존재하고 실제 프로젝트엔 한 번도 반영된 적 없었음** (`api/monitoring.ts` 등도 마찬가지)
- `frontend_src_full.zip`으로 11개 페이지 + NavBar + api 3종 전체를 한 번에 묶어서 실제 반영 완료
- 이 과정에서 추가로 튀어나온 문제 2건도 해결됨:
  - `node_modules/tapable` 파일 손상 → `rm -rf node_modules package-lock.json && npm install`로 해결
  - `package.json`에 `react-router-dom` 자체가 없었음(Figma Make 스캐폴드엔 필요 없었으니까) → 별도 설치로 해결
- **최종 확인**: `/login`(보호자 선택) → `/dashboard`(실제 API 데이터로 "오늘의 복약" 렌더링)까지 E2E 실동작 확인함

### 4. 오늘 밤 새로 정한 방향 — Figma 화면 15개 전부 연결하기로 결정
- 지금 라우터엔 11개 화면만 있고(위 3번 참고), Figma로 디자인했던 나머지 15개(회원가입/보호자연결(리치버전)/자가진단(리치버전)/처방전업로드(리치버전)/처방전확인/복약일정/알림설정/모니터링대시보드/이용기록/마이페이지/챗봇(리치버전)/약품상세/처방상세/복약가이드/환자관리/교육관리)는 `App.figma-export.tsx.bak` 안에 코드만 있고 라우터엔 없음
- **`계정 잠금` 화면은 스킵 확정** — 지금 시스템에 비밀번호 로그인 자체가 없어서(보호자 이름 선택 방식) 논리적으로 맞지 않음
- 나머지는 전부 연결 목표, 백엔드 없는 기능은 새로 만들기로 함

### 5. 백엔드 배치 1 완료 (아래 5개, 전부 curl로 실제 테스트 통과)
새 테이블 4개(`CareLevelAssessment`, `Invitation`, `NotificationSetting`, `ChatMessage`) + 새 라우터 2개(`care_router.py`, `chat_router.py`) 추가:
- `POST/GET /assessments` — 자가진단 결과 저장 (판정 로직은 AssessmentPage.tsx의 computeResult()와 동일하게 포팅)
- `POST /invitations`, `GET /invitations/{token}`, `POST /invitations/{token}/accept|reject` — 보호자 초대 토큰 발급→수락 플로우 (수락 시 신규/기존 보호자 선택 가능, caregiver_patients 자동 연결)
- `GET/PUT /notification-settings` — 알림 설정 저장 (없으면 기본값 자동 생성)
- `GET /chat/questions`, `POST /chat/ask`, `GET /chat/history` — 고정 질문 3개 + 사전답변 (schedule_v6 Day6 계획 그대로, 나중에 김영혜가 실제 LLM으로 교체할 자리 표시해둠)
- `GET /records?patient_id=` — 환자별 처방전 이력 목록 (기존엔 단건 조회만 있었음)

⚠️ **적용 시 주의**: `models.py`가 바뀌어서 서버 재시작 전 `rm -f app.db` 필수 (SQLite는 기존 테이블에 컬럼 자동 추가 안 함)

### 6. 다음 세션에서 할 일
1. **`index.css`에 Tailwind import 추가 필수**: `@import "tailwindcss";` 한 줄 — 안 하면 Figma 화면들(Tailwind 클래스 기반) 갖고 와도 스타일이 하나도 안 먹음. `tailwindcss`/`@tailwindcss/vite`는 이미 `package.json`에 있음 (설치는 돼 있었음)
2. `App.figma-export.tsx.bak`에서 화면 컴포넌트를 하나씩 `pages/`로 추출 + 라우터 등록
3. 각 화면의 mock 데이터를 오늘 만든 백엔드 API로 교체 (자가진단→`/assessments`, 보호자연결→`/invitations`, 알림설정→`/notification-settings`, 챗봇→`/chat/*`, 이용기록→`/records`, 복약일정/환자관리는 이미 있는 `/monitoring/*`, `/patients` 그대로 사용)
4. 아직 백엔드 없는 것: 교육관리(care-education) — 계속 3번째로 후순위 밀리는 기능, 마지막에 처리 권장
5. Desktop의 iCloud 잔재 폴더 삭제 (위 1번 명령어)

---

## 프로젝트 기본 정보


- **서비스명**: 건강동행 (가칭)
- **팀**: AI 헬스케어 4기 파이널 프로젝트 2팀
- **담당**: 박소정 — ④ 프론트엔드·배포·통합
- **멘토**: 이현구 (다음 멘토링: 7/8(수) 20:00 — 팀원 1명 불참으로 7/7에서 연기됨)
- **GitHub**: https://github.com/AI-HealthCare-04/AH_04_02
- **로컬 경로**: `~/dev/Final_medication_guidance_based_on_medical_records/` (7/6 변경 — iCloud Desktop 동기화가 vite.config.ts 타임스탬프를 계속 건드려서 Vite가 무한 재시작되는 문제로 iCloud 동기화 밖으로 이전함. 예전 경로는 `~/Desktop/AI_Health_care/18. 최종프로젝트.../git/...`였음)
- **현재 브랜치**: `feature/frontend-setup_sojung`
- **Figma**: https://www.figma.com/design/2J0k0BpzENAtXTzbkmZx3L/
- **프로젝트 기한**: 2026-08-07 (배포 마감 7/31)

### 팀원 역할
| 이름 | 역할 |
|---|---|
| 권순현 | ① OCR·정보추출 (CLOVA, 2주차 한시) + `ocr_router.py` |
| 김영혜 | ② RAG·가이드생성 (LangChain) + `rag_router.py` |
| 박소정 | ④ 프론트·배포 + `main.py`/`monitoring_router.py`(백엔드 통합 총괄) |
| ~~조성아~~ | ~~③ 챗봇·백엔드~~ — 7/6 팀 이탈 |
| ~~김현우~~ | ~~역할 미정~~ — 7/6 실무 제외 확정, **실질 인원 3명** |

---

## ⚠️ 7/6 긴급: iCloud 동기화로 인한 Vite 무한 재시작 (7/7 최종 해결 확인됨 — 위 요약 1번 참고)

- 증상: 프로젝트가 iCloud Drive 동기화 대상인 `~/Desktop/...` 안에 있어서, iCloud가 `vite.config.ts` 타임스탬프를 주기적으로 건드림 → Vite가 설정 변경으로 착각하고 서버 재시작 → 브라우저가 React 로딩을 끝내기 전에 계속 죽는 livelock 발생 (npm install 직후 동기화 대상 파일이 많아지면서 심화됨)
- 시도했다가 되돌린 것: 특정 폴더만 iCloud 동기화 제외(file-provider 속성 변경) — 오히려 강제 eviction/재다운로드가 발생해 Vite가 멈춤. 두 번 다 원복함
- **해결**: 프로젝트 폴더를 iCloud 동기화 밖(`~/dev/`)으로 이동. 이후 경로 참조 전부 갱신됨(아래 로컬 경로 항목 참고)
- 팀원 중 macOS + iCloud Desktop/Documents 동기화 켜져 있는 사람은 동일 증상 가능성 있음 — 처음부터 `~/dev/` 같은 비동기화 폴더에서 작업 권장

## ⚠️ 7/6 긴급: 인원 변동 + 백엔드 구조 전면 단순화 (최우선 숙지)

- **실질 팀 인원 3명** — 권순현(①OCR), 김영혜(②RAG), 박소정(④프론트·배포+백엔드 통합). **조성아(이탈), 김현우(제외)** 둘 다 실무에서 빠짐
- 권순현이 **`schedule_v6_explained.md`**로 8일(Day1~8) 통합 일정 직접 작성·배포 (7/8 정정: "조장"이 아니라 권순현 본인 작성) — 아래 내용이 어제 만든 `인원변동_대응안_0706.md`(MySQL·역할재배분 A/B/C안)를 **대체**함. 그 문서는 참고용으로만 남기고 실행 기준은 이 섹션을 따를 것
- **기술 스택 전면 단순화 확정**:
  - DB: ~~MySQL 8.0~~ → **SQLite** (설치 불필요, 파일 하나)
  - 통신: ~~SSE~~ → **동기 요청-응답** (스트리밍 없음)
  - 큐: ~~Redis Stream/asyncio~~ → **Redis 완전 미사용**, BackgroundTask 또는 그냥 순차 함수 호출
  - 챗봇: ~~자유 대화~~ → **고정 질문 3~4개 + 사전답변** (엔드포인트 1개, `/chat`)
  - 인증: **이번 8일 계획에 로그인/회원가입 언급 없음** — 즉 `Login.tsx`/`api/auth.ts`가 호출하는 실제 로그인 백엔드는 이번 스코프에 없음. 데모까지는 고정 테스트 유저로 갈지, 로그인 자체를 스킵할지 팀 확인 필요 (미확정 이슈로 남김)
- **파일 구조 확정**: `main.py`(박소정) + `routers/ocr_router.py`(권순현) + `routers/rag_router.py`(김영혜) + `routers/monitoring_router.py`(박소정)
- **멘토 최우선 지정**: 복약모니터링(medication_schedules/logs) — 마침 `Dashboard.tsx`에 이미 구현된 "오늘의 복약" UI(taken/pending/skipped)가 이 기능과 그대로 대응됨. 화면은 있고 백엔드만 없는 상태
- **Day별 요약**: D1 골격+SQLite연결(오늘) / D2 각자 스키마 설계 / D3 라우터 작성 시작(모니터링 CRUD 최우선) / D4 라우터 완성 / D5 전체 흐름 연결(3인 페어링) / D6 챗봇+통합점검 / D7 통합테스트+예외처리 / D8 최종점검
- **컷 우선순위**(시간 부족 시): BackgroundTask 자동화 → 순차 호출로 대체 가능 / 챗봇 → "준비중" 표시로 대체 가능. **절대 포기 불가**: 골격, SQLite, 모니터링 CRUD, ocr_router, rag_router

### 기존 20테이블 MySQL ERD(`Diagram_v2_리뷰반영.dbml`)에 대한 처리
이 스코프에선 구현 대상이 아님 — SQLite 4테이블(records, ocr_results, guide_results, medication_schedules/logs)로 대폭 축소. ERD는 인원 충원 시 재참조할 참고 자료로 보관.

## ⚠️ 7/2 멘토링으로 인한 주요 변경사항 (반드시 숙지)

- **개발 마감이 2주차(7/10)로 앞당겨짐** — High 우선순위 기능만 다음 주 금요일까지 완성 목표
- **테스트 방식**: 2 iteration(2바퀴) 돌려 테스트 후 보완하는 프로세스 도입
- **High 항목 50% 축소** 권장 (아이젠하워 매트릭스 적용) — 교육/알림 기능 후순위 연기, 이미지분류 복약분석·시각음성변환 등 선택기능은 여유될 때만
- **Redis Stream → asyncio 백그라운드 태스크로 단순화** (과도한 설계로 판단됨, 기존 skeleton 재활용 가능. 대안: Redis Pub/Sub)
- **벡터DB: FAISS → ChromaDB로 전환**
- **OCR: 2주차(7/10)까지 한시적으로 CLOVA OCR로 전환** (7/2 멘토링 결정) — 기존 "EasyOCR 확정, CLOVA 전환 없음" 방침을 일시적으로 뒤집는 결정이라 팀 문서(API명세서, 사전보고서) 업데이트 필요. 2주차 이후 EasyOCR 복귀 여부는 미확정
- **RAG hallucination 최소화 3요소 모두 필요**: ①출처 강제 인용 ②응답 형식 제약 ③Self-consistency
- 상세 재조정 로드맵: `로드맵_v2_멘토반영_0702.md` 참고

---

## 기술 스택 (7/2 기준, 변경사항 반영)

- **Frontend**: React + Vite + TypeScript, react-router-dom, axios
- **Backend**: FastAPI, Python 3.13, asyncio, Pydantic, JWT
- **AI**: LangChain, **ChromaDB**(FAISS에서 전환 예정), OpenAI gpt-4o-mini(개발) / gpt-4o(배포)
- **OCR**: ~~EasyOCR~~ → **CLOVA OCR로 한시적 전환 (2주차/7·10까지)**, confidence 필드는 계속 미사용 권장
- **DB**: **MySQL 8.0** (PostgreSQL에서 확정 변경됨) + Tortoise ORM
- **Queue**: ~~Redis Stream~~ → **asyncio 백그라운드 태스크로 단순화 예정** (전환 작업 미착수)
- **Infra**: Docker Compose, Nginx, AWS EC2, S3

---

## 핵심 설계 원칙

### 1. 두 가지 "상태" 개념 구분 (중요, 절대 혼동 금지)
| | care_level (케어레벨) | 환자상태 |
|---|---|---|
| 판단 기준 | 인지·거동·시력 | 진단명 + 처방 약물 |
| 목적 | 서비스 이용방식 결정 | 가이드 내용 결정 |
| 시점 | 업로드 전 | OCR 후 RAG 단계 |

### 2. 신뢰 설계 원칙 (REQ-007a)
- care_level이 "제3자 도움 필요"여도 강제하지 않음
- 보호자 등록 권유만 표시, 어르신 자기결정권 존중
- 어르신이 거부하면 혼자 사용 가능

### 3. 화면 흐름 (9단계)
```
/ (랜딩) → /login → /check (자가판단+검사결과) → /select (유형선택)
                                                    ├─ 본인 → /upload
                                                    └─ 보호자 → /connect → /upload
/upload → /processing → /result → /chat
```

### 4. Figma 리디자인 관련 신규 화면 (7/2 작업, 아직 라우터 미등록)
- 랜딩페이지, 홈 대시보드, 보호자 연결 관리, 초대 수락, 자가진단 체크리스트 5개 화면을 캡처 기반으로 코드 작성 완료
- 신규 컴포넌트: `NavBar.tsx`(공용), `Landing.tsx`(교체), `Dashboard.tsx`(신규), `Connect.tsx`(교체), `InviteAccept.tsx`(신규), `Check.tsx`(교체)
- **미완료**: `App.tsx`에 `/dashboard`, `/invite/:token` 라우터 추가 필요 (코드 안내는 전달했으나 직접 수정은 못함)
- 색상은 정확한 Figma hex값을 못 받아서 기존 팔레트(`#C16A45`, `#FAF6F1`) 기준으로 추정 적용됨 → 실제 값 확인 필요
- 라우터 등록 및 나머지 화면(로그인 등) 리뉴얼 여부는 미결정

---

## 현재 개발 상태

### 프론트엔드 (frontend/src/pages/) — 7/7 전면 갱신: 실제 프로젝트 반영 확인됨

| 파일 | 상태 | 비고 |
|---|---|---|
| Landing.tsx | ✅ 실제 반영 확인 | 정적 페이지 |
| Login.tsx | ✅ 실제 반영 확인 | ~~이메일/비밀번호~~ → **보호자 선택 방식**으로 재작성됨(auth 스코프 제외 반영), `GET /monitoring/caregivers` 실연동 |
| Check.tsx | ✅ 실제 반영 확인 | 결과 저장은 아직 mock — `/assessments` 연동 대기 (백엔드는 준비됨) |
| Select.tsx | ✅ 실제 반영 확인 | 분기용, 연동 불필요 |
| Connect.tsx | ✅ 실제 반영 확인 | 목록 mock, 초대 전송도 alert()만 — `/invitations` 연동 대기 (백엔드는 준비됨) |
| Upload.tsx | ✅ 실제 반영 확인, 실연동 완료 | `POST /records`로 파일+patientId 전달, Processing으로 이동 |
| Processing.tsx | ✅ 실제 반영 확인, 실연동 완료 | 폴링 아님 — `POST /records` 응답 기다리는 동안 3단계 애니메이션만 시각효과로 표시 |
| Result.tsx | ✅ 실제 반영 확인, 실연동 완료 | Processing이 넘겨준 데이터 그대로 렌더링 (재조회 없음) |
| Chat.tsx | ✅ 실제 반영 확인 | mock 응답 — `/chat/questions`, `/chat/ask` 연동 대기 (백엔드는 준비됨) |
| Dashboard.tsx | ✅ 실제 반영 확인, 실연동 완료 | `GET /monitoring/today` 실데이터, 3버튼(복용/아직/건너뜀) 전부 실제 API 호출 |
| InviteAccept.tsx | ✅ 실제 반영 확인 | 초대 정보 mock — `/invitations/{token}` 연동 대기 (백엔드는 준비됨) |
| NavBar.tsx | ✅ 실제 반영 확인 | 이번에 새로 작성(기존엔 실체 없이 import만 되고 있었음) |
| api/monitoringClient.ts, monitoring.ts, records.ts | ✅ 실제 반영 확인 | 백엔드 baseURL `http://localhost:8000` 직접 호출 (Nginx 프록시 없음) |
| api/client.ts, medicalRecords.ts, auth.ts | ⚠️ 사용 안 함 | 옛 MySQL+Docker 백엔드용, 지금 아무도 안 import함 — 삭제 가능 |

**⚠️ Tailwind 미적용 상태**: 위 화면들은 전부 inline style이라 문제없이 보이지만, `App.figma-export.tsx.bak`에서 화면을 가져올 땐 `index.css`에 `@import "tailwindcss";` 추가 먼저 해야 함 (다음 세션 1순위)

### 아직 라우터에 없는 화면 (Figma 디자인은 존재, `App.figma-export.tsx.bak` 안에 코드 있음)
회원가입, 계정잠금(스킵 확정), 처방전업로드(리치버전), 처방전확인, 복약일정, 알림설정, 모니터링대시보드(보호자용), 이용기록, 마이페이지, 챗봇(리치버전), 약품상세, 처방상세, 복약가이드, 환자관리, 교육관리 — 총 14개(계정잠금 제외)

---

## 인프라 파일 현황 (7/2 기준, 전면 갱신)

| 파일 | 위치 | 상태 |
|---|---|---|
| docker-compose.yml | 프로젝트 루트 | ✅ 완료, 정상 동작 확인 |
| infra/nginx/default.conf | infra/nginx/ | ✅ 완료 |
| envs/.local.env | envs/ | ✅ 완료 |
| app/Dockerfile | app/ | ✅ **완료** (멀티스테이지 빌드, 7/2 생성) |
| ai_worker/Dockerfile | ai_worker/ | ✅ **완료** (멀티스테이지 빌드, 7/2 생성) |

**전체 6개 컨테이너(redis, mysql, fastapi, ai-worker, nginx 등) 정상 기동 확인, `http://localhost/api/docs` 200 OK**

### 표준 실행 명령어
```bash
docker compose --env-file envs/.local.env up -d --build
```
(⚠️ `docker-compose`가 아닌 `docker compose` V2 플러그인 사용, 반드시 `--env-file` 플래그 포함)

### 7/2 해결한 Docker 이슈 9건 (상세는 `트러블슈팅_모음_0702.md` 참고)
Docker Desktop 미실행, asyncmy 컴파일 실패(build-essential 설치), docker-compose→docker compose, 환경변수 빈값, 3306 포트 충돌(→3307), uv 바이너리 누락, uvicorn 실행 실패(WORKDIR 통일), ai-worker 무한재시작(임시 대기루프)

---

## 남은 작업 (우선순위 순, 7/2 기준 갱신)

### 이번 주 금요일(7/3)까지
- [ ] 멘토링 사전보고서 CLOVA 문구 최종 수정 (4-2 세부일정표) — ⚠️ 단, 아래 OCR 방침 변경으로 문구 자체를 재검토해야 할 수 있음
- [ ] 팀 회의: 계정 잠금 정책(인증코드 필수 방식 의도 확인), 탈퇴취소 로그 방식 결정
- [ ] REQ-028 요구사항 추적표 누락 보완
- [ ] Figma 신규 라우터(`/dashboard`, `/invite/:token`) App.tsx 등록 여부 결정 및 반영
- [ ] develop 브랜치 1차 merge (4명 코드 통합, **아직 미착수**)
- [ ] **API명세서.md·README 등 문서의 "EasyOCR로 통일" 문구를 CLOVA 한시 전환 방침으로 수정** (아래 참고)
- [ ] ①담당(권순현)과 CLOVA API 키·연동 방식 공유 필요

### 2주차(7/6~7/10) — 멘토 지정 MVP 마감
- [ ] AI Worker(`ai_worker/main.py`) 임시 대기 루프 → 실제 OCR(CLOVA)/RAG 로직으로 교체
- [ ] Redis Stream → asyncio 백그라운드 태스크 전환 (③담당과 작업량 재분배 논의 필요)
- [ ] 벡터DB FAISS → ChromaDB 전환
- [x] ~~백엔드 API 실제 연동 (Upload, Result)~~ → 완료 (7/2 저녁)
- [x] ~~Processing.tsx mock 타이머 → 실제 연동~~ → polling 방식으로 완료 (SSE는 추후 업그레이드)
- [x] ~~Result.tsx mock 데이터 → API 응답으로 교체~~ → 완료
- [ ] 로그인 API 연동 후 `Upload.tsx`의 `localStorage.getItem("user_id")` 임시 처리를 실제 로그인 흐름으로 교체
- [ ] E2E 1차 확인 ("정답이 나오는 수준") — 백엔드 엔드포인트 실제 응답 확인 필요 (Swagger)

### 후순위/제외 확정
교육 기능, 알림 기능 (전면 후순위) / 이미지 분류 기반 복약분석, 시각·음성 콘텐츠 변환 (선택기능, 여유 시)

---

## 트러블슈팅 기록 (누적)

| 날짜 | 이슈 | 원인 | 해결 |
|---|---|---|---|
| 6/30 | Invalid hook call 에러 | react-router-dom package.json 누락 | node_modules 삭제 후 npm install 재실행 |
| 6/30 | Upload → Processing 이동 안 됨 | handleUpload에 navigate 없음 | useNavigate 추가 |
| 7/1 | 모바일 검은 여백 | index.css #root에 width:1126px 고정 | index.css 전면 교체 (width:100%) |
| 7/1 | 모바일 접속 불가 | npm run dev 기본값은 localhost만 열림 | npm run dev -- --host 로 실행 |
| 7/1 | PyCharm에서 파일 열면 렉 | 대형 TSX 파일 용량 문제 | 터미널 cat > 명령어(heredoc)로 직접 덮어쓰기 |
| 7/2 | Docker Desktop 미실행 | - | 앱 실행 |
| 7/2 | asyncmy 컴파일 실패 | build-essential 누락 | 패키지 설치 |
| 7/2 | docker-compose 명령어 실패 | V1 문법 사용 | docker compose(V2 플러그인)로 변경 |
| 7/2 | 환경변수 빈값 | --env-file 플래그 누락 | envs/.local.env 명시 |
| 7/2 | 3306 포트 충돌 | 로컬 시스템 MySQL 점유 | DB_EXPOSE_PORT=3307, sudo lsof로 확인 |
| 7/2 | uv: not found | runtime 이미지에 uv 바이너리 없음 | builder에서 복사 |
| 7/2 | uvicorn 실행 실패 | builder/runtime WORKDIR 불일치 (venv shebang 경로) | 둘 다 /app으로 통일 |
| 7/2 | ai-worker 무한 재시작 | main.py 비어있음 | 임시 대기 루프 작성 |
| 7/7 | iCloud로 Vite 무한 재시작(livelock) | Desktop 동기화 폴더 안에서 작업 | `~/dev/`로 프로젝트 폴더 통째 이동 |
| 7/7 | `mv`가 실행 안 되고 멈춘 것처럼 보임 | 터미널에 붙여넣기만 되고 Enter 안 눌림(사용자 확인 필요했던 케이스) | 커서 포커스 확인 후 Enter |
| 7/7 | node_modules/tapable 손상, Vite config 로드 실패 | iCloud 이동 중 대용량 폴더 손상 가능성 | `rm -rf node_modules package-lock.json && npm install` |
| 7/7 | "Invalid hook call" / useRef null (react-router-dom) | package.json에 react-router-dom 자체가 없었음 | `npm install react-router-dom` 후 전체 재설치 |
| 7/7 | 화면 위 이상한 검은 메뉴바, URL과 화면 불일치 | App.tsx가 실은 Figma Make 프로토타입(state 기반, react-router 미사용)이었음 | 라우터 버전으로 App.tsx 교체 (원본은 `.bak`으로 보관) |
| 7/7 | `Failed to resolve import "./pages/Landing"` | pages/, components/ 폴더가 실제 프로젝트에 아예 없었음(그동안 만든 파일이 한 번도 반영 안 됨) | `frontend_src_full.zip`으로 전체 일괄 반영 |

---

## 서버 실행 명령어 (7/7 갱신 — Docker 아님, schedule_v6 방식)

```bash
# 프로젝트 루트로 이동
cd ~/dev/Final_medication_guidance_based_on_medical_records

# 백엔드 (SQLite, uvicorn 직접 실행 — Docker/MySQL 아님)
cd backend
uvicorn main:app --reload
# → http://localhost:8000/docs 에서 확인

# 프론트엔드 (다른 터미널 탭에서)
cd frontend
npm run dev
# → http://localhost:5173 (모바일 포함 접속하려면 npm run dev -- --host)

# models.py 수정한 뒤엔 반드시 (SQLite는 컬럼 자동 추가 안 됨)
rm -f backend/app.db
```

⚠️ 예전 `docker compose --env-file envs/.local.env up -d --build`는 1주차 때 만든 `app/`(MySQL 템플릿) 기준 명령어로, **지금은 안 씀**. `app/`, `ai_worker/`, `docker-compose.yml`, `envs/`, `infra/`는 정리 대상(삭제 또는 archive) — 지금 당장 안 건드려도 됨.

---

## 관련 산출물 파일

- `로드맵_v2_멘토반영_0702.md` — 멘토 피드백 반영 재조정 로드맵
- `문서_검토_리뷰용_0702.md` — 요구사항정의서/ERD/API명세서 1차 리뷰
- `트러블슈팅_모음_0702.md` — Docker + 프론트엔드 트러블슈팅 전체 (1주차, 지금 스택과는 다름)
- `schedule_v6_explained.md` — 권순현 작성, 3인 8일 통합일정 (현재 실행 기준)
- `frontend_src_full.zip` — 7/7 실제 프로젝트에 반영한 pages/components/api 전체
- `backend-batch1/` — 7/7 추가한 백엔드 5종(자가진단/초대/알림설정/챗봇/이용기록목록) main.py·models.py·routers 3개
