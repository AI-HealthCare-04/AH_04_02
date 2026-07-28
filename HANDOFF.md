# 건강동행 — 작업 인계 문서 (2026-07-23 작성)

다른 계정/다른 LLM(Codex 등)이 이어받을 수 있도록 이 세션에서 한 작업과 현재 상태를 정리한다.
**이 파일은 git에 커밋돼있지 않다** — 다른 Claude 계정이 같은 로컬 디렉토리를 이어서 열면 그대로
보이지만, 완전히 다른 기기/도구라면 이 파일 내용을 직접 붙여넣어야 한다.

## 저장소 / 브랜치 / PR

- 로컬 경로: `/Users/sojung/dev/Final_medication_guidance_based_on_medical_records`
- 현재 브랜치: `feature/frontend-setup_sojung`
- 베이스: `dev`
- 열려있는 PR: **#71** — https://github.com/pecs0310/AH_04_02/pull/71 (`MERGEABLE`, dev와 완전 동기화 상태, 2026-07-23 기준)
- 최근 HEAD 커밋: `b563d89` (dev 병합 포함)

## ⚠️ 중요 — 이 브랜치는 다른 세션과 동시에 작업 중이다

같은 git 계정(`pecs0310 <babi0310@naver.com>`)으로 **또 다른 AI 세션(혹은 팀원)이 이 정확히 같은
브랜치에서 병행 작업 중**이다. 이번 세션 도중 최소 두 번, 내가 모르는 사이에 다른 세션이 커밋을
푸시한 걸 뒤늦게 발견했다(예: `4b074cc` — 내가 만든 챗봇 로직 변경 때문에 깨진 테스트 9건을
고치고, 내 중복처방 판정 로직에 "처방일자" 기준을 추가로 얹은 커밋). **작업을 새로 시작하기 전에
반드시 `git fetch && git log --oneline HEAD..origin/<branch>`로 뒤처지지 않았는지 확인할 것.**
그리고 dev 자체도 팀원(영혜님)이 활발히 PR을 merge하고 있으니 `origin/dev`도 같이 확인해야 한다.

## 이번 세션에서 한 일 (시간순)

1. **처방전 중복 등록 근본 원인 수정 + 기존 데이터 정리** — React StrictMode가 개발 모드에서
   업로드 이펙트를 두 번 실행해 등록내역이 중복 저장되던 버그. `Processing.tsx`에 `useRef` 가드
   추가, 기존 중복 `medical_records` 정리(raw_text 기준, `pinned` 우선/없으면 최신순 유지).
2. **로그인 후 진입 화면 분기** — 보호자/기관 계정은 `/patients`(환자관리)로, 환자 본인은
   `/dashboard`(오늘의 복약)로. 로그인 상태에서 홈 화면에 회원가입/로그인 버튼이 계속 보이던
   버그도 수정(`Landing.tsx`가 `loggedIn` 여부를 안 보고 있었음).
3. **UI 톤온톤 정리** — 페이지/카드 배경색을 순백(`#FFFFFF`/`#FAF6F1`)에서 좀 더 또렷한 웜톤
   (`C.ivory`≈`#F2E8D8`, 카드는 `C.surface`≈`#F9F4EB`)으로 전면 통일. NavBar 현재 메뉴 주황색
   강조. 등록내역 즐겨찾기(고정) 기능.
4. **등록내역·복약 일정 선택 삭제 + 전체선택** — `Records.tsx`/`Schedule.tsx`에 다중 선택 삭제와
   전체선택 체크박스 추가. 그 과정에서 진짜 백엔드 버그 발견·수정: `DELETE /monitoring/schedules/
   {id}`가 `notification_logs` FK 제약 위반으로 500 나던 것(참조 로그를 먼저 지우고 flush).
5. **오늘의 복약 중복 처방 자동 방지** — `_create_schedules_from_ocr`가 같은 환자·같은 약 이름으로
   이미 활성 일정이 있으면 새로 만들지 않고 건너뛰도록 수정, `PrescriptionDetail.tsx`에 "이미
   등록된 처방이에요" 배너 추가. **[중요] 이후 다른 세션이 이 로직을 확장했다** — 단순 약 이름
   매치가 아니라 `prescription_date`(처방일자, `parsing_rules.extract_prescription_date()`로
   OCR 원문에서 파싱)까지 비교해서, 같은 약이라도 처방일자가 다르면 "재처방"으로 보고 기존
   일정을 비활성화한 뒤 새로 등록하도록 개선됨(`4b074cc`). 이 로직을 다시 건드릴 땐 이 커밋부터
   읽을 것.
6. **챗봇 고정질문 약품 맥락 분리** — `GET /chat/questions`가 항상 "환자의 최근 등록 약"으로
   고정 질문을 만들던 걸, 실제로 어느 화면(DrugInfo/DrugDetail)에서 들어왔는지 `drug_name`
   쿼리파라미터로 받아 그 약 기준으로 만들고, 맥락 없이(플로팅 챗봇 버튼) 들어오면 일반 고정
   질문(PRESET_QUESTIONS)을 보여주도록 수정. **[중요]** 이 시그니처 변경(`_build_dynamic_
   questions(patient_id, session)` → `_build_dynamic_questions(drug_name)`)이 기존 테스트 9개를
   깨뜨렸는데, 내가 직접 안 고치고 다른 세션이 나중에 고쳤다(`4b074cc`) — **다음에는 백엔드 로직을
   바꾸면 반드시 `pytest`를 직접 돌려서 확인할 것.** 이번 세션 내내 브라우저 수동 테스트만 하고
   자동 테스트 스위트를 한 번도 실행하지 않은 게 이번 세션의 가장 큰 허점이다.
7. **환자→보호자 초대(문자/URL/QR) 기능 복원** — 팀 회의로 없어졌던 기능을 사용자 요청으로 복원.
   처음엔 내가 새로 `InviteCaregiverPanel.tsx`를 만들었으나, 이후 dev를 pull하며 보니 dev 쪽
   (`Connect.tsx`, PR#68/69)이 이미 훨씬 완성도 높은 버전(보호자용 "받은 초대" 수락/거절, 초대
   삭제, 클립보드 복사 fallback 포함)을 갖고 있어서 **내 컴포넌트는 버리고 dev 버전을 채택**했다
   (내 톤온톤 배경색만 다시 입힘).
8. **마이페이지 "내 정보" 신설 + 로그아웃 버튼** — 회원가입 때 정보 확인·수정(환자/보호자/기관
   모두), 열람 전 비밀번호 재확인(`POST /auth/verify-password`, 상태 안 바꾸고 확인만).
   로그아웃 버튼 추가(`access_token`/`patient_id`/`caregiver_id`/`user_name` 전부 제거 후 홈으로).
9. **회원가입 이메일/전화번호 실시간 중복 확인** — 필드에서 포커스 아웃 시 즉시 확인(`GET
   /monitoring/patients/check-duplicate`, `GET /monitoring/caregivers/check-duplicate`), 비밀번호
   확인과 동일한 빨간 테두리+문구 UX.
10. **dev 동기화 두 차례 수행** — PR#68/69(영혜님, RAG 가이드/langfuse 개선 — `GUIDE_DATA_VERSION`
    v1.0→v1.1 캐시 무효화 포함) + PR#70(문서 전용) 병합. 상세는 아래 "알아둘 것" 참고.

## 알아둘 것 (환경/컨벤션)

- **zsh 래퍼 버그**: 이 샌드박스에서 `cd foo && command`처럼 `cd`를 명령어 체인 앞에 붙이면
  `exec_scmb_expand_args:3: command not found: _safe_eval` 에러가 난다. `command cd`, `command git`
  처럼 `command` 접두어를 쓰거나, `cd` 자체를 아예 피하고 절대경로/`env -C <dir> <cmd>`를 쓸 것.
- **Python**: 시스템 `python3`엔 `pymysql`이 없다. 항상
  `/Users/sojung/dev/Final_medication_guidance_based_on_medical_records/.venv/bin/python3` 사용.
- **DB**: 공유 Aiven MySQL(`health_companion_dev`) — 로컬 SQLite 아님. `backend/.env`의
  `DATABASE_URL` 참고. 팀 전체가 같은 DB를 보므로 테스트 데이터는 만들면 반드시 정리할 것.
- **Docker**: `docker-compose`로 프론트(5173)/백엔드(8000) 실행 중일 수 있음. 백엔드 코드를
  고치면 `docker restart final_medication_guidance_based_on_medical_records-backend-1`로 재시작
  해야 반영된다(uvicorn --reload가 붙어있지만 가끔 안 먹을 때가 있어 재시작이 확실함).
- **소프트 삭제 컨벤션**: `MedicalRecord`/`Patient`/`Caregiver`/`PatientMedication`은 `deleted_at`,
  `MedicationSchedule`은 `active` 플래그로 소프트 삭제한다. 절대 하드 삭제하지 말 것(단,
  `DELETE /monitoring/schedules/{id}`처럼 이미 하드 삭제로 설계된 기존 엔드포인트는 그대로 둠).
- **PII 암호화**: `Patient.name`/`phone`, `Caregiver.name`/`phone` 등은 프로퍼티(암호화 setter)라
  생성자 kwarg로 못 받는다 — 객체 만든 뒤 `.name = ...`/`.phone = ...`로 대입해야 함.
- **알렘빅**: 여러 세션이 동시에 마이그레이션을 만들면 head가 갈라질 수 있다(`alembic heads`로
  확인). 갈라지면 `alembic merge -m "..." <head1> <head2>`로 병합 커밋 만들고, 실제 DDL이 이미
  라이브로 적용된 쪽은 `alembic stamp`, 안 된 쪽만 `alembic upgrade`로 반영.
- **디자인 토큰**: `frontend/src/theme.ts`의 `C` 객체가 유일한 색상 소스여야 한다 — 새 화면 만들 때
  하드코딩 hex 대신 `C.ivory`/`C.surface`/`C.terracotta` 등을 쓸 것. 다만 기존 코드 중 일부는 아직
  `bg-[#F2E8D8]`/`bg-[#F9F4EB]` 같은 Tailwind 리터럴로 남아있다(파일마다 관례가 섞여있음 — 같은
  파일 안에서는 기존 패턴을 따라가는 게 안전).

## 다음에 할 만한 것 (요청받지 않았으면 먼저 하지 말 것, 참고용)

- 백엔드 로직을 고칠 때마다 `pytest`를 실제로 돌려서 확인하는 습관 들이기(이번 세션 최대 반성점).
- "받은 초대" UI가 지금 `Connect.tsx`(보호자 전용)와 `PatientManagement.tsx`(예전에 내가 넣은 것)
  두 곳에 비슷하게 존재한다 — 중복인지, 의도된 것인지 팀에 확인 후 정리 여지 있음.
- `Patient.gender` 필드를 암호화할지 여부 — 아직 평문(사용자 확인은 받았으나 팀 논의 필요, 이전
  세션 메모 참고).

## 확인 방법

```bash
# dev/브랜치 동기화 확인 (항상 먼저)
command git fetch origin dev
command git log --oneline HEAD..origin/dev

# 백엔드 문법/타입
/Users/sojung/dev/Final_medication_guidance_based_on_medical_records/.venv/bin/python3 -m py_compile backend/routers/*.py
command npx --prefix frontend tsc -p frontend --noEmit

# 백엔드 테스트 (이번 세션에서 거의 안 돌려본 부분 — 꼭 실행해볼 것)
env -C /Users/sojung/dev/Final_medication_guidance_based_on_medical_records/backend \
  /Users/sojung/dev/Final_medication_guidance_based_on_medical_records/.venv/bin/python3 -m pytest
```

## 참고 문서 (이 세션의 memory, 같은 Claude 계정이면 자동으로 보임)

`/Users/sojung/.claude/projects/-Users-sojung-dev-Final-medication-guidance-based-on-medical-records/memory/MEMORY.md`
— 다른 계정/다른 LLM은 이 경로에 접근 못하므로, 필요하면 이 파일들 내용도 같이 복사해서 넘길 것.
