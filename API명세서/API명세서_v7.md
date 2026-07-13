# API 명세서 — 진료기록 기반 복약·생활습관 안내 시스템

Base URL 없음(각 라우터가 자체 prefix 사용, 아래 참고). 데이터베이스는 **SQLite**(`backend/app.db`), 필드명은 `snake_case`, 시간은 서버 로컬 시각(`datetime.now()`) 그대로 저장·응답한다.

**라우터 prefix**: `auth`(`/auth`), `records`(`/records`), `ocr`(`/ocr`), `rag`(`/rag`), `monitoring`(`/monitoring`), `chat`(`/chat`) 6개는 라우터명과 일치하는 prefix를 쓴다. **`care_router`만 prefix가 없어** 2·3·7절의 `/assessments`, `/invitations`, `/notification-settings`, `/patients/{id}/invitations`가 다른 라우터와 달리 루트에 바로 노출된다 — RESTful 관점의 일관성 문제로, 다음 버전에서 `/care` prefix를 붙이는 걸 검토할 것.

> 버전: v7 (2026-07-13). v6 대비 변경 내역은 `docs/revision_logs/API명세서` 참고.
>
> **v6은 목표 설계 문서였고, 실제 구현과 크게 어긋나 있었다.** 이번 v7은 `backend/routers/` 7개 라우터를 전수 조사해 **실제로 존재하는 엔드포인트만** 기준으로 다시 작성했다. v6에 있었지만 구현되지 않은 기능(회원 탈퇴, 비밀번호 재설정, 잠금 해제, 돌봄관계 해제 승인 워크플로, SSE 스트리밍, TTS, 캐싱, 교육·추적관리 전체 등)은 각 절 끝에 "미구현 항목"으로 남겨 요구사항 자체는 잃어버리지 않도록 했다(요구사항_정의서_v8에서 REQ별 구현여부로 다시 정리).

## ⚠️ 인가(Authorization) — 전 절 공통, 반드시 먼저 읽을 것

**[2026-07-13, PR #29 병합] 2·3·7절(monitoring_router/care_router)은 이제 토큰 기반 인가가 적용됐다.** `backend/dependencies.py`의 `get_current_caregiver`(보호자 전용 화면용) / `get_current_actor`(보호자·환자 공유 화면용, 토큰의 role을 보고 `Caregiver`/`Patient` 중 알맞은 본인 레코드를 반환) + `require_patient_access`/`require_actor_patient_access`(그 `patient_id`가 실제로 본인 것이거나 본인이 케어하는 환자인지 검증)를 각 엔드포인트가 `Depends()`로 사용한다.

**4·6절(records_router/ocr_router/rag_router/chat_router)은 여전히 미적용이다** — `patient_id`/`caregiver_id`를 쿼리·바디 파라미터로 그대로 신뢰한다(issue #21 본문에도 "다른 라우터도 점검 필요"로 명시된 범위, PR #29 리뷰에서도 범위 밖으로 재확인됨).

인증이 필요 없는 것은 의도된 예외 3종류뿐이다: **① 회원가입**(`POST /auth/signup`, `POST /monitoring/patients`, `POST /monitoring/caregivers` — 계정이 없어야 호출하는 게 당연함), **② 초대 링크 열람/수락/거절**(`GET /invitations/{token}`, `POST /invitations/{token}/accept`·`/reject` — 초대받은 사람이 아직 계정이 없을 수 있어 토큰 자체가 인가 수단), **③ 로그인/토큰 재발급**(`POST /auth/login`, `GET /auth/token/refresh`).

이 문서에서 "인증" 컬럼은 **"로그인이 필요한가"가 아니라 "그 값이 실제로 검증되는가"**를 뜻한다. 요구사항_정의서의 REQ-031(인증·역할별 인가)은 2·3·7절 기준으로는 구현 완료, 4·6절 기준으로는 아직 미구현이다.

> **알려진 잔여 이슈**: `POST /monitoring/caregivers/{caregiver_id}/patients/{patient_id}`(보호자-환자 연결)에 "이미 다른 보호자가 연결된 환자면 거부" 체크가 PR #29에서 함께 추가돼, 초대 없이 임의 환자에 자가 연결하는 경로는 막혔다(재현 테스트로 확인 완료). 다만 이 자가연결 자체가 "방금 만든 환자를 최초 연결"하는 용도로 여전히 인증 없이 열려 있는 건 아니고 `Depends(get_current_caregiver)`로 보호되며, `patient_id`가 자동증가 정수라는 점 자체의 근본적 위험은 여전히 존재하므로 회원가입 직후 응답에서 `patient_id`를 노출하는 범위는 계속 최소화할 것.

## 공통 모델

에러 응답은 FastAPI 기본 형식을 그대로 쓴다(별도 커스텀 에러 스키마 없음):

```json
// HTTPException — 4xx/5xx
{"detail": "해당 환자를 찾을 수 없어요"}

// pydantic 검증 실패 — 422
{"detail": [{"loc": ["body", "drug_name"], "msg": "Field required", "type": "missing"}]}
```

비동기 작업 접수(`202`)나 SSE 스트리밍은 없다 — 모든 요청은 동기적으로 처리되어 완료된 결과를 그대로 반환한다. 외부 호출(CLOVA OCR, OpenAI)은 `asyncio.to_thread`로 감싸 서버가 다른 요청을 막지 않게만 처리한다.

## 1. 인증·사용자 (REQ-001, REQ-035(미구현), REQ-039(미구현), REQ-045, REQ-046(미구현), REQ-049(부분))

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/auth/signup` | 보호자 회원가입 | `{email, password, name, relation_type="guardian"}` | `201 {id, email, name}` | X | 완료 |
| POST | `/monitoring/patients` | 환자 회원가입(보호자 가입과 별도 엔드포인트) | `{name, note?, phone?, email?, birth_date?, password?, push_enabled?, sms_enabled?, email_opt_in?}` | `200 {id, name, note, phone, email, birth_date, push_enabled, sms_enabled, email_opt_in, created_at}` | X | 완료 |
| POST | `/monitoring/caregivers` | 보호자/단체 회원가입(조직 가입 겸용) | `{name, relation_type, phone?, email?, birth_date?, password?, push_enabled?, sms_enabled?, email_opt_in?, org_name?, org_type?, business_reg_no?, manager_name?, manager_phone?}` | `200 CaregiverPublic{...}` | X | 완료 |
| POST | `/auth/login` | 로그인 — 보호자/환자 통합, 이메일 또는 전화번호로 식별 | `{identifier, password}` | `200 {access_token, token_type:"bearer", caregiver_id, name}` + 쿠키 `refresh_token` | X | 완료 |
| GET | `/auth/token/refresh` | access_token 재발급 | 쿠키 `refresh_token` | `200 {access_token, token_type, caregiver_id, name}` | 쿠키 검증만(access 토큰 아님) | 완료 |

**PII 암호화**: `patients`/`caregivers`의 `name`/`phone`은 DB에 Fernet 대칭키로 암호화(`name_encrypted`/`phone_encrypted`) + 조회용 `phone_hash`(HMAC-SHA256)로 저장되지만, **응답에는 항상 평문으로 복호화되어 나간다**(`.name`/`.phone` 프로퍼티가 투명하게 복호화). `caregivers.manager_name`/`manager_phone`(단체 담당자 연락처)은 암호화 대상이 아니다(계정 본인 PII가 아니라는 이유로 의도적으로 평문 저장).

**REQ-049(앱 최초 실행 화면 정책)**: 클라이언트 동작 규약이라 API 없음 — 부분 구현(로그인/refresh 자체는 있으나 "저장된 토큰으로 자동 로그인" 로직은 프론트 미확인).

### 미구현 항목 (v6 설계에는 있었음)
- `GET /users/me`(내 정보 조회 — 애초에 "나"를 식별할 인가 수단이 없음), `PATCH /users/me`
- 로그인 5회 실패 시 계정 잠금 + 임시번호 발송·재로그인(REQ-039) — `POST /auth/login` 실패 처리는 400 하나뿐, 잠금·임시코드 로직 없음
- 비밀번호 재설정(`/auth/password-reset/*`)
- 회원 탈퇴(`DELETE /users/me`, 30일 유예 삭제, REQ-035)
- 가입 시 보호자 연락처 자동 초대(REQ-046) — 환자 가입(`POST /monitoring/patients`)과 보호자 연결(`POST /invitations`)이 완전히 분리된 별도 절차

## 2. 돌봄관계 (REQ-002~004)

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/invitations` | 보호자 초대 토큰 발급 | `{patient_id, relation_type, invited_phone, inviter_caregiver_id}` | `200 {token, invite_url}` | O(`get_current_actor`, 본인/케어 환자만) | 완료 |
| GET | `/invitations/{token}` | 초대 링크 정보 조회 | 경로 `token` | `200 {token, status, relation_type, patient_name, inviter_name}` | X(의도됨 — 계정 없는 수신자용, 만료 검증 로직은 없음) | 완료(부분 — 자동 만료 미구현) |
| POST | `/invitations/{token}/accept` | 초대 수락 → 연결 생성 | `{caregiver_name, caregiver_id?}` | `200 {caregiver_id, patient_id, status:"accepted"}` | X(의도됨 — 계정 없는 수신자용) | 완료 |
| POST | `/invitations/{token}/reject` | 초대 거절 | 경로 `token` | `200 {status:"rejected"}` | X(의도됨) | 완료 |
| GET | `/patients/{patient_id}/invitations` | 환자의 초대 발송 이력 | 경로 `patient_id` | `200 [Invitation{...}]` (⚠️ `token` 원문·평문 `invited_phone` 포함) | O(`get_current_actor`) | 완료 |
| GET | `/monitoring/caregivers/{caregiver_id}/patients` | 보호자가 연결된 환자 목록 | 경로 `caregiver_id` | `200 [PatientPublic]` | O(`get_current_caregiver`, 본인만) | 완료 |
| GET | `/monitoring/patients/{patient_id}/caregivers` | 환자에 연결된 보호자 목록 | 경로 `patient_id` | `200 [CaregiverPublic]` | O(`get_current_actor`) | 완료 |
| POST | `/monitoring/caregivers/{caregiver_id}/patients/{patient_id}` | 보호자-환자 연결 생성(신규 환자 최초 연결 전용, 2번째부터는 초대 필요) | 경로 둘 다 | `200 {linked/already_linked, caregiver_id, patient_id}` | O(`get_current_caregiver`, 본인 계정만 + 이미 다른 보호자가 있으면 403) | 완료 |
| DELETE | `/monitoring/caregivers/{caregiver_id}/patients/{patient_id}` | 연결 해제 | 경로 둘 다 | `200 {unlinked:true}` | O(`get_current_actor`, 본인 보호자 또는 본인 환자만) | 완료 |

**보안 주의**: `GET /patients/{patient_id}/invitations` 응답에 초대 링크의 원문 `token`이 그대로 노출된다 — 이 값은 사실상 유일한 인가 수단이므로, 이 목록 조회 API 자체가 노출돼서는 안 되는 값을 돌려주고 있다(인가는 적용됐지만 응답 필드 자체의 문제라 별개). `Invitation.invited_phone`은 `patients`/`caregivers`의 phone과 달리 **암호화되지 않고 평문 저장·응답**된다(PII 정책 사각지대).

`relation_type`은 `guardian`, `caregiver`, `life_support_worker`, `social_worker`, `organization`을 쓴다(v6의 `admin` 역할은 없음).

### 미구현 항목
- 연결 해제 승인/반려 워크플로(`PATCH .../revocation`, `revocation_pending` 상태) — 지금은 `DELETE`가 즉시 해제
- 초대 만료(`410 Gone`), 중복 처리 거부(`409`) — 현재는 만료 개념 자체가 없음
- 연결 0명 시 안내(REQ-007a) — 백엔드 API 없음(프론트 로직 여부 미확인)

## 3. 상태·복약가능여부 — 자가진단 (REQ-005~007, REQ-007a(미구현))

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/assessments` | 자가진단 결과 저장 + 케어등급 즉시 판정 | `{patient_id, cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness}` | O(`get_current_actor`) | 완료 |
| GET | `/assessments/latest` | 최신 평가 1건 | 쿼리 `patient_id` | `200 CareLevelAssessment` 또는 `200 null`(없으면) | O(`get_current_actor`) | 완료 |

v6은 "상태 저장"과 "평가"를 별개 리소스(`status`/`care_level`)로 분리했지만, 실제로는 `POST /assessments` 하나가 입력·평가·저장을 한 번에 처리한다(트랜잭션 분리 없이 애초에 한 테이블·한 요청).

### 미구현 항목
- 평가 이력 목록 조회(`GET .../care-level/history`) — 최신 1건만 조회 가능, 과거 이력 API 없음
- `/users/me/status` 같은 전용 자기조회 경로는 없지만, `get_current_actor`가 환자 토큰이면 곧 본인이므로 기존 쿼리 파라미터 방식(`?patient_id=`) 그대로 자기 자신의 `patient_id`를 넘기면 사실상 동일하게 동작한다 — 별도 경로 추가 없이 인가만으로 자연스럽게 해소됨
- 연결 권유 안내 표시/닫기(REQ-007a, `care-level-notice*`)

## 4. 진료기록·OCR (REQ-008~011, REQ-023~024, REQ-047(미구현))

OCR 제공자는 `OCR_PROVIDER` 환경변수로 전환한다(`clova`=기본값, 실제 CLOVA OCR 연동 / `mock`=로컬 목업, 키 없이 흐름 테스트용). v6의 "EasyOCR 통일" 결정은 이후 CLOVA OCR로 다시 바뀌었다.

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/records` | 처방전 이미지 업로드 → OCR 실행(RAG는 별도, 4·5절 확인 흐름에서만 실행) | 쿼리 `patient_id`(필수), `caregiver_id`(선택); multipart `file` | `200 {record_id, status:"review_required", failure_reason, created_at, uploaded_by_name, medications:[...], guide:null}` | X | 완료 |
| POST | `/records/manual` | OCR 실패 시 "직접 입력" 빈 레코드 생성 | 쿼리 `patient_id`, `caregiver_id`(선택) | `200` (위와 동일 모양, medications 1건 빈 값) | X | 완료 |
| POST | `/records/{record_id}/medications` | 확인 화면에서 약물 항목 추가 | 경로 `record_id` | `200` (레코드 응답) | X | 완료 |
| DELETE | `/records/{record_id}/medications/{medication_id}` | 항목 삭제(마지막 1개는 삭제 불가) | 경로 둘 다 | `200` (레코드 응답) | X | 완료 |
| GET | `/records` | 환자별 처방전 이력 목록 | 쿼리 `patient_id`(필수) | `200 [{record_id, status, created_at, diagnosis, drug_names, uploaded_by_name}]` | X | 완료 |
| GET | `/records/{record_id}` | 단건 재조회(새로고침용) | 경로 `record_id` | `200` (guide 포함 최신 상태) | X | 완료 |
| GET | `/ocr/drug-info` | 약품명으로 약효분류·적응증 조회(세션 무관 단건 조회) | 쿼리 `drug_name` | `200 {drug_name, matched_name, drug_class, indication}` | X | 완료 |
| GET | `/ocr/ping` | 라우터 연결 확인(디버그) | 없음 | `200 {status:"ok", owner:"권순현"}` | X | 완료(디버그용) |
| POST | `/ocr/test` | OCR 단독 테스트(실제 흐름은 `POST /records`) | 쿼리 `patient_id`; multipart `file` | `200 {record_id, status, medications}` | X | 완료(테스트용) |

**설계 변경(v6 대비)**: v6은 OCR 신뢰도(`confidence < 0.80`)에 따라 `review_required` 여부가 갈렸지만, 실제로는 **신뢰도와 무관하게 항상 `review_required`로 반환**하고 사람이 `POST /records/{id}/confirm`(5절)으로 확정해야 다음 단계로 넘어간다 — "저신뢰만 확인"이 아니라 "전부 확인" 정책으로 바뀌었다.

`uploaded_by_name`(대리 업로드한 보호자 이름, 본인 업로드면 `null`)은 평문 응답이다(REQ-024 대리 입력 투명성).

### 미구현 항목
- OCR 재시도 전용 엔드포인트(`POST .../retries`) — 재시도는 그냥 `POST /records`를 다시 호출
- 약물명 오타 제안(`typo_suggestion`, REQ-047)
- OCR 완료/가이드 완료 시각을 별도 필드로 노출(`ocr_completed_at` 등) — 내부적으로 계산되지 않음

## 5. 복약·생활습관 가이드 (REQ-012~020, REQ-028, REQ-032~033)

가이드 생성은 별도 엔드포인트가 아니라 **`POST /records/{record_id}/confirm`(4절, 확인 화면 "확정" 버튼) 호출 시 그 안에서 함께 실행**된다.

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/records/{record_id}/confirm` | 약물 항목 확정 → RAG 가이드 생성 → 복약일정 자동 등록까지 한 번에 | 경로 `record_id`; `{medications:[{id, drug_name, dosage, frequency, diagnosis, drug_class}]}` | `200` (레코드 응답, `guide` 필드 포함) | X | 완료 |
| GET | `/rag/ping` | RAG 라우터 연결 확인(디버그) | 없음 | `200 {status:"ok", owner:"김영혜"}` | X | 완료(디버그용) |

`RAG_PROVIDER` 환경변수로 전환한다 — 기본값(`stub`)은 고정 가짜 데이터(`{"title":"테스트 출처","url":"..."}`)를 반환하고, `real`로 켜야 실제 파이프라인(`rag-prototype/`, LangChain+ChromaDB+OpenAI)이 동작한다. 실제 파이프라인의 가이드에는:
- **출처 인용**(`source_refs`): e약은요(식약처) + HIRA 약가마스터(표준코드·ATC코드·허가상태)를 병합해 인용(REQ-014)
- **DUR 경고**: 병용금기(같은 처방전의 다른 약과 실제로 함께 있을 때만), 노인주의·연령금기·임부금기(약 하나의 속성, 다른 약과 무관) — 전부 로컬 CSV 조회(`backend/data/dur_*.csv`), API 활용신청 승인 대기 상태
- **면책 고지**(`disclaimer`, REQ-032): 매 응답에 고정 문구 포함

캐싱(`cache_key`, `cache_expires_at`), TTS 음성(`GET .../guide/audio`), SSE 진행률 스트리밍은 없음 — 매 확정마다 새로 생성한다.

### 미구현 항목
- 가이드 재생성 전용 엔드포인트(`POST .../guides`) — 재생성하려면 새 확인 흐름을 다시 타야 함
- 캐싱, TTS(REQ 선택 기능), SSE 진행률

## 6. 챗봇 (REQ-021~022, REQ-048)

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| GET | `/chat/questions` | 고정 질문 버튼 목록 | 없음 | `200 [{id, text}]` | X | 완료 |
| POST | `/chat/ask` | 고정 질문 또는 자유 텍스트 질문에 답변 | `{patient_id, question_id?, question?}` (둘 중 하나 필수) | `200 {question, answer, answer_source, created_at}` | X | 완료 |
| GET | `/chat/history` | 대화 이력 조회 | 쿼리 `patient_id` | `200 [ChatMessage]` | X | 완료 |

`CHAT_PROVIDER` 환경변수로 전환 — 기본값(`stub`)은 고정 질문엔 사전 정의 답변, 자유 질문엔 안내 문구만 반환. `real`로 켜면 환자의 최근 처방·가이드 결과를 컨텍스트로 GPT(OpenAI)가 실제 답변을 생성하고, 메뉴 안내(어떤 화면에서 무엇을 할 수 있는지)도 함께 답할 수 있다. LLM 호출 실패 시 조용히 고정 답변으로 폴백하고 `answer_source`에 그 사유를 남긴다(REQ-048 관련 — 저신뢰 확인 후 챗봇 연결 안내는 프론트 로직).

SSE 스트리밍 응답은 없음(동기 응답 한 번에 전체 답변 반환).

## 7. 복약 알림·기록·모니터링 (REQ-007, REQ-026a~026d(부분), REQ-036~038)

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/monitoring/schedules` | 복약 일정 등록 | `{patient_id, drug_name, time_slot, dose_timing?, caregiver_alert?, memo?}` | `200 MedicationSchedule{...}` | O(`get_current_actor`) | 완료 |
| GET | `/monitoring/schedules` | 일정 조회 | 쿼리 `patient_id`(필수), `active_only?`(기본 true) | `200 [MedicationSchedule]` | O(`get_current_actor`) | 완료 |
| PATCH | `/monitoring/schedules/{schedule_id}` | 일정 변경 | 경로 `schedule_id`; 변경 필드 | `200 MedicationSchedule` | O(`get_current_actor`, 그 일정의 patient_id 기준) | 완료 |
| DELETE | `/monitoring/schedules/{schedule_id}` | 일정 및 로그 삭제 | 경로 `schedule_id` | `200 {deleted:id}` | O(`get_current_actor`) | 완료 |
| POST | `/monitoring/schedules/{schedule_id}/check` | 복약 체크(오늘자) | `{status, confirmed_by_caregiver_id?}` | `200 {schedule_id, status}` | O(`get_current_actor`) | 완료 |
| DELETE | `/monitoring/schedules/{schedule_id}/check` | 체크 취소(pending으로 되돌림) | 경로 `schedule_id` | `200 {schedule_id, status:"pending"}` | O(`get_current_actor`) | 완료 |
| GET | `/monitoring/logs` | 최근 N일 복약 로그 | 쿼리 `patient_id`(필수), `days?`(기본 30) | `200 [{id, schedule_id, drug_name, time_slot, status, checked_at, confirmed_by_type, confirmed_by_name}]` | O(`get_current_actor`) | 완료 |
| GET | `/monitoring/today` | 오늘자 통합 조회(대시보드용) | 쿼리 `patient_id`(필수) | `200 [{id, name, time, note, status}]` | O(`get_current_actor`) | 완료 |
| GET | `/monitoring/patients/{patient_id}/known-drugs` | 드롭다운용 기존 약물명 목록 | 경로 `patient_id` | `200 [str]` | O(`get_current_actor`) | 완료 |
| GET | `/notification-settings` | 알림 수신 설정 조회(없으면 저장 없이 기본값만 반환) | 쿼리 `patient_id` | `200 NotificationSetting{patient_id, medication_reminder_enabled, care_alert_enabled, all_push_enabled, updated_at}` | O(`get_current_actor`) | 완료 |
| PUT | `/notification-settings` | 알림 수신 설정 변경(최초 변경 시 row 생성) | 쿼리 `patient_id`; 변경 필드 | `200 NotificationSetting` | O(`get_current_actor`) | 완료 |

**[2026-07-13, PR #29 병합]** 이 절 전체가 `get_current_actor`/`require_actor_patient_access`로 보호된다(이전엔 `patient_id` 쿼리만 있으면 누구나 호출 가능했고, `GET /monitoring/schedules`는 `patient_id`를 아예 생략하면 전체 환자 일정이 노출됐었다 — 지금은 `patient_id`가 필수 파라미터로 바뀌면서 이 문제도 함께 해소됨).

`medication_reminder_enabled`(복약 알림), `care_alert_enabled`(보호자 돌봄 알림), `all_push_enabled`(전체 푸시 스위치)는 기본값 전부 `true`다. v6과 달리 실제 알림 발송(FCM/SMS 등)은 구현돼 있지 않고, 이 설정값은 저장만 되는 상태다.

`confirmed_by_name`(복약 체크를 대신 확인한 보호자 이름)은 평문 응답.

### 미구현 항목
- 실제 알림 발송(스케줄 시각에 맞춘 push/SMS) — 설정값 저장만 존재, 발송 로직 없음
- 안전 알림 최소 인원 권고(`should_recommend`, REQ-007a 관련)
- `PATCH /notifications/{id}` 읽음 처리 — 발송 자체가 없어 해당 없음
- `GET /monitoring/medication-subjects/{id}`(보호자용 요약, adherence_rate 등 집계) — 로그 원본 조회(`/monitoring/logs`)만 있고 집계 API는 없음

## 8. 교육·추적관리 (REQ-040~044) — 전체 미구현

`education_profiles`, `education_support_logs`에 해당하는 테이블·엔드포인트가 `backend/models.py`/`backend/routers/`에 전혀 없다. 교육 단계 자동 분류(freshman/junior/senior), 전화지원 일정, 재교육 회차 관리 기능은 요구사항_정의서에는 있으나 이번 스프린트 범위에서 손대지 않았다.

## 상태 코드

`200` 성공(이 프로젝트는 `201`/`202`를 쓰지 않고 생성도 `200`으로 통일), `400` 잘못된 요청(로그인 실패 등), `404` 리소스 없음, `409` 상태 충돌(예: 확인 대기 상태가 아닌데 확정 시도), `422` pydantic 검증 실패(FastAPI 기본), `500` 서버 오류(예: RAG 파이프라인 예외).
