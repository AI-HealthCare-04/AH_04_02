# API 명세서 — 진료기록 기반 복약·생활습관 안내 시스템

Base URL 없음(각 라우터가 자체 prefix 사용, 아래 참고). 데이터베이스는 **SQLite**(`backend/app.db`, 팀 개발 환경은 공유 MySQL로도 운용), 필드명은 `snake_case`, 시간은 서버 로컬 시각(`datetime.now()`) 그대로 저장·응답한다(UTC/KST 정책 미명시 — v8부터 이어지는 알려진 이슈).

**라우터 prefix**: `auth`(`/auth`), `records`(`/records`), `ocr`(`/ocr`), `rag`(`/rag`), `monitoring`(`/monitoring`), `chat`(`/chat`) 6개는 라우터명과 일치하는 prefix를 쓴다. **`care_router`만 prefix가 없어** 2·3·8절의 `/assessments`, `/invitations`, `/notification-settings`, `/patients/{id}/invitations`, `/trust/relations` 등이 다른 라우터와 달리 루트에 바로 노출된다 — RESTful 관점의 일관성 문제로 v8부터 지적됐으나 이번 버전에서도 아직 조치하지 않았다(다음 버전 후보).

> 버전: v10 (2026-07-22). v9 대비 변경 내역은 `docs/revision_logs/API명세서/API명세서_v9_to_v10_revision_log.md` 참고.
>
> **v9은 PR #61(챗봇 preset/dynamic LLM 유출·등록약 컨텍스트 누락 수정)과 PR #62(보호자→환자 초대 REQ-058 + MedicationRecord 통합 REQ-037 + 챗봇 출처표시/OCR 약품명/의약품명 매핑/복약가이드/검색우선순위/DUR속도 다수 수정)가 dev에 머지된 뒤 작성했다.** 이 두 PR로 v9 당시 1절(auth — 로그인 잠금·비밀번호 재설정·회원탈퇴가 실제로는 이미 구현돼 있었음이 처음 문서화됨), 2절(invitations — 보호자→환자 방향 추가), 5절(rag — source_refs 구조·검색 우선순위), 6절(chat — source_refs 응답 추가, LLM 게이팅 버그 수정), 기존 7절(monitoring — MedicationRecord 승격, 알림 스케줄러 실체 확인)이 갱신됐다. 정합성 검토(`요구사항정의서_API명세서_정합성검토.docx`, 권순현)에서 지적된 REQ-009/011/032 서술 오류도 이번 버전에서 정정했다. **v10은 PR #69 이후 dev 기준으로 실제 라우터와 문서를 다시 대조해 refresh token Method, 대기중 초대 삭제/받은 초대 수락·거절, 환자 내약 등록 API, 처방전 삭제 연쇄 동작을 추가 반영했다.**

## 용어 매핑(요구사항_정의서 ↔ API/코드)

정합성 검토에서 지적된 용어 불일치를 해소하기 위해 표로 명시한다. **코드/DB는 아래 우측 컬럼 용어를 그대로 쓴다** — 이 문서와 이후 모든 API 설명은 우측 용어 기준이다.

| 요구사항_정의서 용어 | 코드/API/DB 용어 |
|---|---|
| 복약관리 대상자 (medication_subject) | `Patient` 클래스, `patients` 테이블, API 설명에서는 "환자" |
| 보호자 (guardian) | `Caregiver` 테이블의 `relation_type="guardian"` — 별도 테이블이 아니라 값으로 구분 |
| 요양보호사 (caregiver) | `Caregiver` 테이블의 `relation_type="caregiver"` |
| 생활지원사 (life_support_worker) | `Caregiver` 테이블의 `relation_type="life_support_worker"` |
| 사회복지사 (social_worker) | `Caregiver` 테이블의 `relation_type="social_worker"` |
| 지원인력(요양보호사·생활지원사·사회복지사 집합) | 별도 코드상 명칭 없음 — `relation_type in (caregiver, life_support_worker, social_worker)`로만 구분 |
| 단체(기관) | `Caregiver` 테이블의 `relation_type="organization"` |
| 돌봄관계 초대 테이블(요구사항_정의서가 종종 언급하는 "care_relation_invitations") | 실제 테이블명은 **`invitations`** — `care_relation_invitations`라는 테이블/엔드포인트는 존재한 적이 없다 |
| 신뢰관계 / 돌봄관계 연결 | `caregiver_patients` 테이블 |

즉 **`guardian`과 `caregiver`는 서로 다른 테이블이 아니라 같은 `Caregiver` 테이블을 `relation_type` 값으로 구분**한다 — 권한 로직(`get_current_actor`/`require_actor_patient_access`)도 `relation_type`을 구분하지 않고 "이 환자에 연결된 Caregiver인가"만 검사한다. 지원인력과 guardian 사이에 코드 레벨의 권한 차등은 현재 없다(교육관리 기능이 구현취소되어 REQ-043의 "guardian은 교육자 불가" 제약도 적용 대상 자체가 없음, 9절 참고).

## ⚠️ 인가(Authorization) — 전 절 공통, 반드시 먼저 읽을 것

**2·3·6·7절(monitoring_router/care_router/chat_router)과 4·5절(records_router/ocr_router/rag_router), 즉 인증이 의미 있는 전 라우터에 토큰 기반 인가가 적용돼 있다** — `backend/core/dependencies.py`의 `get_current_actor`(보호자·환자 공유 화면용, 토큰의 role을 보고 `Caregiver`/`Patient` 중 알맞은 본인 레코드를 반환)와 `require_actor_patient_access`(그 `patient_id`가 실제로 본인 것이거나 본인이 케어하는 환자인지 검증)를 각 엔드포인트가 `Depends()`로 사용한다.

**[v9 정정] chat_router도 인가가 적용돼 있다** — v8은 "6절(chat_router)은 여전히 미적용"이라고 서술했으나, 이는 2026-07-14(`require_actor_patient_access` 도입 커밋)부터 이미 사실이 아니었다. `GET /chat/questions`·`POST /chat/ask`·`POST /chat/ask/stream`·`GET /chat/history` 4개 엔드포인트 전부 `Depends(get_current_actor)` + `require_actor_patient_access(patient_id, ...)`를 통과해야 한다(2026-07-21 코드 재확인, 전용 인가 테스트 `test_chat_router_auth.py` 존재). v9 이전 버전들이 이 사실을 반영하지 못했던 것은 REQ-030/031 조사 시점이 실제 코드 변경보다 앞섰기 때문이다.

인증이 필요 없는 것은 의도된 예외로 ① 회원가입(`POST /monitoring/patients`, `POST /monitoring/caregivers`), ② 초대 링크 열람/수락/거절(`GET /invitations/{token}`, `POST /invitations/{token}/accept`·`/reject`), ③ 로그인/토큰 재발급/비밀번호 재설정(`POST /auth/login`, `POST /auth/token/refresh`, `POST /auth/password-reset/*`), ④ 세션 무관 단건 조회·헬스체크(`GET /ocr/ping`, `GET /ocr/drug-info`, `GET /rag/ping`)다. **`POST /auth/signup`은 2026-07-14에 `POST /monitoring/caregivers`와 중복되는 죽은 코드로 판단되어 제거됐다** — 회원가입은 `/monitoring/patients`·`/monitoring/caregivers` 둘로만 이뤄진다.

이 문서에서 "인증" 컬럼은 **"로그인이 필요한가"가 아니라 "그 값이 실제로 검증되는가"**를 뜻한다.

## 공통 모델

에러 응답은 FastAPI 기본 형식을 그대로 쓴다:

```json
// HTTPException — 4xx/5xx
{"detail": "해당 환자를 찾을 수 없어요"}

// pydantic 검증 실패 — 422
{"detail": [{"loc": ["body", "drug_name"], "msg": "Field required", "type": "missing"}]}
```

비동기 작업 접수(`202`)는 없다 — 대부분의 요청은 동기적으로 처리되어 완료된 결과를 그대로 반환한다. 단, 챗봇 답변은 `POST /chat/ask/stream`에서 `text/event-stream`으로 토큰 단위 SSE 스트리밍을 지원한다. RAG 가이드 생성 진행률을 별도로 흘려주는 SSE는 없다(REQ-028 계열 후속 후보).

## 1. 인증·사용자 (REQ-001, REQ-035, REQ-039, REQ-045, REQ-046(미구현), REQ-049, REQ-050)

**[v9] 로그인 잠금·비밀번호 재설정·회원탈퇴가 이미 구현돼 있었다는 사실을 이번에 처음 문서화한다** — v8까지는 `backend/routers/auth_router.py`를 전수 조사하지 않아 REQ-035/039를 "미구현"으로 잘못 표기하고 있었다(요구사항_정의서_v8도 동일한 오류, revision log 참고).

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/monitoring/patients` | 환자 회원가입 | `{name, note?, phone?, email?, birth_date?, password?, push_enabled?, sms_enabled?, email_opt_in?}` | `200 PatientPublic` | X | 완료 |
| POST | `/monitoring/caregivers` | 보호자/단체 회원가입(조직 가입 겸용) | `{name, relation_type, phone?, email?, birth_date?, password?, push_enabled?, sms_enabled?, email_opt_in?, org_name?, org_type?, business_reg_no?, manager_name?, manager_phone?}` | `200 CaregiverPublic` | X | 완료 |
| POST | `/auth/login` | 로그인 — 보호자/환자 통합, 이메일 또는 전화번호로 식별 | `{identifier, password}` | `200 {access_token, token_type:"bearer", caregiver_id, name, role}` + 쿠키 `refresh_token`(httponly) | X | 완료 |
| POST | `/auth/token/refresh` | access_token 재발급(refresh 회전 + 재사용 탐지) | 쿠키 `refresh_token` | `200 LoginResponse`(동일 모양) | 쿠키 검증만 | 완료 |
| POST | `/auth/password-reset/request` | 비밀번호 재설정 코드 발급(이메일 발송) | `{identifier}` | `200 {message}`(계정 존재 여부 무관 항상 동일 문구 — 계정 열거 공격 방지) | X | 완료 |
| POST | `/auth/password-reset/verify` | 코드 검증 → 1회용 reset_token 발급 | `{identifier, code}` | `200 {reset_token}` | X | 완료 |
| POST | `/auth/password-reset/confirm` | reset_token으로 새 비밀번호 설정 | `{reset_token, new_password}` | `200 {message}` | reset_token 자체가 인가 수단 | 완료 |
| POST | `/auth/withdraw` | 회원 탈퇴 요청(비밀번호 재확인) | `{password}` | `200 {message, deletion_scheduled_at}` | O(`get_current_actor`) | 완료 |
| POST | `/auth/withdraw/cancel` | 탈퇴 취소(유예기간 내) | `{identifier, password}` | `200 {message}` | 식별자+비밀번호(로그인 자체가 막혀 있어 토큰 인가 불가) | 완료 |
| GET | `/monitoring/patients` | 내 정보(환자 본인) 또는 내가 케어하는 환자 목록 | 없음 | `200 [PatientPublic]` | O(`get_current_actor`) | 완료 |
| PATCH | `/monitoring/patients/{patient_id}` | 환자 정보 수정 | 경로 `patient_id`; 수정할 필드만 | `200 PatientPublic` | O | 완료 |
| PUT | `/monitoring/patients/{patient_id}/meal-times` | 자가진단 온보딩 — 아침/점심/저녁 식사시간·규칙성 저장(REQ-051, 신규) | `{breakfast_time?, breakfast_regular?, lunch_time?, lunch_regular?, dinner_time?, dinner_regular?}` | `200 PatientPublic`(6필드 포함) | O | **완료(단, 저장까지만 — 아래 REQ-051 설명 참고)** |
| DELETE | `/monitoring/patients/{patient_id}` | 환자 계정·연결 삭제 | 경로 `patient_id` | `200 {deleted: patient_id}` | O | 완료 |
| GET | `/monitoring/caregivers` | 내 정보(보호자 본인) 조회 | 없음 | `200 [CaregiverPublic]`(항상 1건) | O | 완료 |

**로그인 잠금(REQ-039)**: 5회 연속 로그인 실패 시 `locked_at`을 기록해 계정을 잠근다. 잠긴 계정은 비밀번호가 맞아도 30분(`LOCKOUT_DURATION_MINUTES`)이 지나거나 비밀번호 재설정을 완료해야 다시 로그인할 수 있다. 5번째 실패 시점에 자동으로 비밀번호 재설정 코드도 함께 발급된다. 로그인 실패 응답은 "이메일/전화번호 또는 비밀번호가 올바르지 않습니다."로 통일해 계정 존재·잠금 여부를 외부에 노출하지 않는다(계정 열거 방지).

**비밀번호 재설정(REQ-039)**: `request`(코드 발급, 계정에 이메일이 있을 때만 실제 발송 — 전화번호만 있는 계정은 코드 발송 채널이 없어 잠금 자동 해제(30분)나 지원팀 문의로만 복구 가능) → `verify`(코드 검증, 10분 만료·5회 시도 제한, 검증 성공 시 1회용 `reset_token` 발급) → `confirm`(`reset_token`으로 새 비밀번호 확정, 잠금·실패횟수 초기화) 3단계. `request` 자체엔 60초 재요청 쿨다운과 10분당 3회 상한이 있다.

**회원 탈퇴(REQ-035)**: 탈퇴 요청 시 즉시 `deactivated_at`을 기록하고 `deletion_scheduled_at`(+30일)을 계산, `PrivacyPurgeAudit`에 `pending` 감사 레코드를 남긴다. 탈퇴 후엔 로그인도 refresh도 모두 차단된다(`deactivated_at is not None`이면 두 엔드포인트 모두 명시적으로 거부). 30일 유예기간 내 `identifier`+`password`로 취소 가능 — 감사 레코드는 `cancelled`로 갱신되고 삭제하지 않는다(감사 추적성 보존). **[v9 정정] 30일 경과 후 실제 개인정보 영구 삭제를 수행하는 배치는 `backend/scripts/purge_expired_accounts.py`(142줄)로 이미 구현·테스트(`test_purge_expired_accounts.py`, 141줄)돼 있다**(2026-07-21 3라운드 감사로 확인 — 이전 초안의 "실행 로직 유무 확정 못함"은 grep 한 번이면 확인 가능했던 오류). 단 서버 프로세스가 이 스크립트를 자동으로 스케줄링하지는 않는다 — 수동 실행 또는 별도 cron 등록이 전제다.

**PII 암호화**: `patients`/`caregivers`의 `name`/`phone`은 DB에 Fernet 대칭키로 암호화(`name_encrypted`/`phone_encrypted`) + 조회용 `phone_hash`(HMAC-SHA256)로 저장되지만, **응답에는 항상 평문으로 복호화되어 나간다.** `caregivers.manager_name`/`manager_phone`은 암호화 대상이 아니다(계정 본인 PII가 아니라는 이유로 의도적으로 평문 저장, v8과 동일).

**REQ-049(앱 최초 실행 화면 정책)**: 클라이언트 동작 규약이라 API 없음 — **확인필요**(로그인/refresh 자체는 있으나 "저장된 토큰으로 자동 로그인" 로직 프론트 재확인 필요, v8과 동일. 2026-07-21 3라운드 감사로 요구사항_정의서_v9·ERD_v9와 상태어 통일 — "부분"이 아니라 "확인필요"가 정확하다).

**REQ-051(신규, 식사시간·복약 알림 참고자료)**: 2026-07-17 회의에서 원래 계획이던 "자가진단(제3자 도움 필요 여부 판단)" 목적을 서비스 방향에서 제외하기로 결정하면서, 그 온보딩 화면 구조만 재사용해 식사시간을 물어보는 것으로 대체했다(회원가입 직후 `MealTimeCheck.tsx`, `/meal-check`). **목적은 복약 알림 시각 설정 시 참고 자료로 활용하는 것**이지만, 코드 조사 결과 `backend/core/scheduler.py`(알림 발송 로직)와 가이드 생성 로직 어디에도 이 6개 필드(`breakfast_time` 등)를 실제로 읽어서 활용하는 코드가 없다 — **입력·저장은 완료됐지만 "참고자료로 활용"하는 부분은 미구현**이다.

### 폐기·보류 항목 (v9에서 정리)
- **자가진단(REQ-005/006/007, 원래 목적: care_level 3단계 판정으로 제3자 도움 필요 여부 판단)** — 2026-07-17 회의에서 이 목적 자체를 서비스 방향에서 제외하기로 결정했다. `POST /assessments`·`GET /assessments/latest`(3절) API는 코드에 남아 있고 정상 동작하지만, **[v9 정정] 이 값을 입력하는 프론트 화면(`Check.tsx`)은 v8 작성 시점(2026-07-13)엔 실제로 존재했었다** — 다만 어디에서도 연결되지 않는 고아 화면이었고, 2026-07-15(2026-07-17 회의보다 이틀 앞서) "로그인 막다른 길 수정" 커밋에서 진입 경로가 없다는 이유로 이미 삭제됐다(`git log --diff-filter=D`로 확인). 즉 07-17 회의가 이 화면을 없앤 것이 아니라, 화면은 그 전에 이미 사라져 있었고 회의는 "그 목적 자체를 더 이상 추구하지 않는다"는 제품 결정을 내린 것이다. 결과적으로 `care_level_assessments`는 실제 서비스에서 항상 비어 있고, 이를 참조하는 REQ-004(해제 승인)·REQ-007a(연결 권유)·REQ-026c(차등 알림)의 `third_party_needed` 분기는 **"평가 이력이 없으면 independent로 간주"라는 폴백 때문에 사실상 항상 independent 경로로만 동작한다**(`care_router.py:357`). 즉 이 REQ들의 API 자체는 "완료"이지만, third_party_needed 분기는 트리거할 방법이 없어 사실상 도달 불가능한 코드다 — 요구사항_정의서에서 REQ-005/006/007은 "보류(목적 폐기, 재개 시 재검토)"로, REQ-004/007a/026c는 "완료(단, third_party_needed 분기는 자가진단 부재로 실질적으로 미도달)"로 구분 표기한다.

### 미구현 항목 (v6 설계에는 있었음, v8과 동일)
- **보호자 본인의 정보 수정·삭제 엔드포인트는 없다**(환자만 PATCH/DELETE 있음)
- 가입 시 보호자 연락처 자동 초대(REQ-046) — 환자 가입과 보호자 연결(`POST /invitations`)이 완전히 분리된 별도 절차

## 2. 돌봄관계 (REQ-002~004, REQ-058(보호자→환자 초대))

**[v9 정정] 보호자→환자 초대(REQ-058)가 새로 추가됐다** — 이전 초안은 이 기능을 "REQ-037"로 잘못 표기했다. REQ-037은 이미 복약 여부 기록(7절, `medication_records`)을 가리키는 번호로 요구사항_정의서에 확정돼 있어 번호가 중복 사용되고 있었다(2026-07-21 3라운드 정합성 감사로 발견) — 요구사항_정의서_v9에 신설한 REQ-058로 정정했다. — 기존 초대는 "환자가 아직 계정 없는 보호자류를 초대"하는 방향뿐이었는데, 이제 "보호자가 아직 계정 없는 환자를 초대"하는 반대 방향도 같은 `invitations` 테이블·엔드포인트로 지원한다.

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/invitations` | 초대 토큰 발급 — `relation_type`에 따라 두 방향을 모두 처리 | `{patient_id?, relation_type, invited_phone?, inviter_caregiver_id?}` | `200 {token, invite_url}` | O(방향별로 다름, 아래 설명) | 완료 |
| GET | `/invitations/{token}` | 초대 링크 정보 조회 | 경로 `token` | `200 {status, relation_type, patient_name, inviter_name, phone_verification_required}` | X(의도됨) | 완료 |
| POST | `/invitations/{token}/accept` | 초대 수락 — `relation_type`에 따라 두 방향을 모두 처리 | 환자→보호자 방향: `{caregiver_name, caregiver_id?, phone?}` / 보호자→환자 방향: `{patient_name, patient_email?, patient_password, patient_phone?}` | 환자→보호자: `200 {caregiver_id, patient_id, status:"accepted"}` / 보호자→환자: `200 {patient_id, status:"accepted"}` | X(의도됨) | 완료 |
| POST | `/invitations/{token}/reject` | 초대 링크 기반 거절 | 경로 `token` | `200 {status:"rejected"}` | X(의도됨) | 완료 |
| DELETE | `/invitations/{invitation_id}` | 보낸 대기중 초대 삭제/취소 — 행 삭제가 아니라 `status="cancelled"`로 전환해 이미 전달된 링크 수락을 차단 | 경로 `invitation_id` | `200 {deleted, status:"cancelled"}` | O | 완료 |
| GET | `/caregivers/{caregiver_id}/pending-invitations` | 로그인한 보호자/지원인력의 받은 초대 목록 — 초대 전화번호 해시와 계정 전화번호가 일치하는 pending 초대만 조회 | 경로 `caregiver_id` | `200 [{id, relation_type, patient_name, created_at, expires_at}]` | O(`get_current_caregiver`) | 완료 |
| POST | `/invitations/{invitation_id}/accept-as-caregiver` | 받은 초대 목록에서 토큰 없이 수락 — 새 계정을 만들지 않고 로그인한 보호자/지원인력 계정으로 연결 생성 | 경로 `invitation_id` | `200 {caregiver_id, patient_id, status:"accepted"}` | O(`get_current_caregiver`) | 완료 |
| POST | `/invitations/{invitation_id}/reject-as-caregiver` | 받은 초대 목록에서 토큰 없이 거절 | 경로 `invitation_id` | `200 {status:"rejected"}` | O(`get_current_caregiver`) | 완료 |
| GET | `/patients/{patient_id}/invitations` | 환자의 초대 발송 이력(환자→보호자 방향만) | 경로 `patient_id` | `200 [Invitation]` | O | 완료 |
| GET | `/monitoring/caregivers/{caregiver_id}/patients` | 보호자가 연결된 환자 목록 | 경로 `caregiver_id` | `200 [PatientPublic]` | O | 완료 |
| GET | `/monitoring/patients/{patient_id}/caregivers` | 환자에 연결된 보호자 목록 | 경로 `patient_id` | `200 [CaregiverPublic]` | O | 완료 |
| POST | `/monitoring/caregivers/{caregiver_id}/patients/{patient_id}` | 보호자-환자 연결 생성(신규 환자 최초 연결 전용) | 경로 둘 다 | `200 {linked/already_linked, caregiver_id, patient_id}` | O(이미 다른 보호자 있으면 403) | 완료 |
| DELETE | `/monitoring/caregivers/{caregiver_id}/patients/{patient_id}` | 연결 해제(즉시) | 경로 둘 다 | `200 {unlinked:true}` | O | 완료 |
| DELETE | `/trust/relations/{trust_id}` | 돌봄관계 해제 요청 — care_level에 따라 즉시 revoked 또는 revocation_pending | 경로 `trust_id` | `200 TrustRevocationResult` | O | 완료(단, third_party_needed 분기는 위 "폐기·보류 항목" 참고) |
| POST | `/trust/relations/{trust_id}/revocation-approval` | 해제 승인/거부 — 자기승인 불가 | `{approve:bool}` | `200 RevocationApprovalResult` | O | 완료 |

**보호자→환자 초대 인가**: `relation_type="patient"`로 생성할 때는 대상 환자 계정이 아직 없어 `require_actor_patient_access`로 검증할 수 없다 — 대신 `inviter_caregiver_id`가 요청한 본인(로그인한 보호자)과 일치하는지만 확인한다(`role != "caregiver" or subject.id != payload.inviter_caregiver_id` → 403). 수락 시엔 `_register_patient()`(회원가입과 동일 로직 재사용)로 실제 `Patient` 계정을 만들고 `invitations.patient_id`를 채운 뒤 `caregiver_patients` 연결을 생성한다. **[v9 정정] 비밀번호는 현재 필수가 아니다** — `care_router.py:accept_invitation()`은 `patient_name`이 없으면 `400`으로 막지만 `patient_password`는 값 검증 없이 그대로 `_register_patient()`에 전달한다(2026-07-21 코드 재확인 — "실제 로그인 가능한 계정"이라는 목적을 고려하면 비밀번호를 필수화하는 편이 안전하다는 리뷰 의견이 있었으나, 아직 committed dev 코드에는 반영되지 않았다. 다음 버전에서 필수화 여부를 확정할 것).

**보안 개선(v9)**: v8 시점엔 `invitations.invited_phone`이 평문 저장·응답되고 `token`도 원문으로 저장·목록조회에 노출되는 것이 알려진 취약점이었다 — **이번 버전에서 둘 다 해소됐다**: `invited_phone`은 `invited_phone_encrypted`로 암호화 저장되고, `token`은 발급 시점에만 평문을 1회 응답하며 이후에는 `token_hash`만 저장·비교한다(목록 조회 API도 해시만 다룬다).

`relation_type`은 `guardian`, `caregiver`, `life_support_worker`, `social_worker`, **`patient`(신규)**를 쓴다. **[v9 정정] `organization`은 `/invitations`를 통한 초대 흐름의 유효값이 아니다** — `InvitationCreate.relation_type`의 `Literal`엔 `organization`이 없다(2026-07-21 코드 확인). `organization`은 `Caregiver.relation_type` 전체 값 중 하나로서 `POST /monitoring/caregivers`(직접 회원가입)에서만 쓰이며, 초대를 통한 단체 가입 경로는 없다.

### 미구현 항목
- 초대 만료(`410 Gone`), 중복 처리 거부(`409`) — `expires_at` 필드는 v9에서 추가됐으나(초대 생성 시 발급+7일 계산), 만료 시 자동으로 `status="expired"`로 전환하는 별도 배치는 없고 `_get_invitation_by_token()` 호출 시점에만 지연 평가로 전환된다(요청이 안 오면 영원히 `pending`으로 남을 수 있음)

## 3. 상태·복약가능여부 — 자가진단(REQ-005~007, REQ-007a) — **[v9] 목적 폐기, 상태 재정리**

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/assessments` | 자가진단 결과 저장 + 케어등급 즉시 판정 | `{patient_id, cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness}` | `200 CareLevelAssessment` | O | 완료(API 자체는 동작하나 아래 참고) |
| GET | `/assessments/latest` | 최신 평가 1건 | 쿼리 `patient_id` | `200 CareLevelAssessment` 또는 `200 null` | O | 완료 |
| POST | `/trust/relations/{trust_id}/dismiss-alert` | 보호자 연결 권유 안내 닫기 — 30일간 재표시 억제 | 경로 `trust_id` | `200 {patient_id, caregiver_alert_dismissed_at, next_alert_at}` | O | 완료 |

**[v9] 2026-07-17 회의 결정 — 자가진단(제3자 도움 필요 판단 목적)은 서비스 방향에서 제외한다.** `POST /assessments`를 실제로 호출하는 프론트 화면이 없어(코드 전수 조사로 확인) 이 API는 현재 도달 불가능한 죽은 경로다. `GET /assessments/latest`가 항상 `null`을 반환하므로, `care_level`을 참조하는 모든 로직(`_should_alert_now`는 예외 — 이건 `caregiver_alert_dismissed_at` 기준이라 무관)은 **"평가 이력이 없으면 independent로 간주"** 폴백만 실질적으로 작동한다.

### 미구현/보류 항목
- 평가 이력 목록 조회(`GET .../care-level/history`) — v8과 동일
- **자가진단 입력 화면 자체가 보류(2026-07-17 결정)** — API를 삭제하지는 않되, 요구사항_정의서에서 REQ-005/006/007을 "보류"로 재분류(자세한 내용은 요구사항_정의서_v9 참고)

## 4. 진료기록·OCR (REQ-008~011, REQ-023~024, REQ-047)

OCR 제공자는 `OCR_PROVIDER` 환경변수로 전환한다(`clova`=기본값, 실제 CLOVA OCR 연동 / `mock`=로컬 목업). **v6의 "EasyOCR 통일" 결정은 CLOVA OCR로 다시 바뀌었고, 코드에 EasyOCR 관련 파일은 전혀 남아있지 않다(정합성 검토 REQ-009 지적사항 재확인, 요구사항_정의서_v8이 아직 "EasyOCR"로 서술하던 것을 v9에서 정정).**

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/records` | 처방전 이미지 업로드 → OCR 실행 | 쿼리 `patient_id`(필수), `caregiver_id`(선택); multipart `file` | `200 {record_id, status:"review_required", failure_reason, created_at, uploaded_by_name, medications:[...], guide:null}` | O | 완료 |
| POST | `/records/manual` | OCR 실패 시 "직접 입력" 빈 레코드 생성 | 쿼리 `patient_id`, `caregiver_id`(선택) | `200`(동일 모양) | O | 완료 |
| POST | `/records/{record_id}/medications` | 확인 화면에서 약물 항목 추가 | 경로 `record_id` | `200`(레코드 응답) | O | 완료 |
| DELETE | `/records/{record_id}/medications/{medication_id}` | 항목 삭제(마지막 1개는 삭제 불가) | 경로 둘 다 | `200`(레코드 응답) | O | 완료 |
| PATCH | `/records/{record_id}/medications/{medication_id}` | 확인 화면 약물 항목 수정 + 오타 제안(REQ-047) | 경로 둘 다; `{drug_name, dosage?, frequency?, total_days?, diagnosis?, drug_class?}` | `200 {..., matched_drug_name, match_score, needs_review, typo_suggestion}` | O | 완료 |
| GET | `/records` | 환자별 처방전 이력 목록 | 쿼리 `patient_id`(필수) | `200 [{record_id, status, created_at, diagnosis, drug_names, uploaded_by_name}]` | O | 완료 |
| GET | `/records/{record_id}` | 단건 재조회 | 경로 `record_id` | `200`(guide 포함 최신 상태) | O | 완료 |
| DELETE | `/records/{record_id}` | 처방전 소프트 삭제(`deleted_at`) — `record_id`로 연결된 `medication_schedules` 비활성화 + `PatientMedication.prescription_id`로 연결된 내약 soft delete + 해당 내약 기반 schedule 비활성화 | 경로 `record_id` | `200 {message: "삭제됐어요"}` | O | 완료 |
| GET | `/ocr/drug-info` | 약물상세 화면용 단건 조회 | 쿼리 `drug_name` | `200 {drug_name, matched_name, drug_class, indication, precautions, side_effects, interactions, storage, patient_summary, dur_cautions}` | X(의도됨) | 완료 |
| GET | `/ocr/ping` | 라우터 연결 확인 | 없음 | `200 {status:"ok", owner:"권순현"}` | X | 완료(디버그용) |
| POST | `/ocr/test` | OCR 단독 테스트 | 쿼리 `patient_id`; multipart `file` | `200 {record_id, status, medications}` | O | 완료(테스트용) |

**[v9] 약품명 매칭·표시 정확도 개선(PR #62, 이번 버전에서 처음 문서화)**:
- 처방전 확인 화면·복약 일정 어디에나 표시되는 약품명이 이제 `matched_drug_name`(전체 제품명, 예: "노바스크정5mg")을 우선하도록 통일됐다(`OcrResult.display_name` 프로퍼티) — v8까지는 화면마다 규칙이 달라 축약명("암로디핀")이나 성분명("메트포르민")이 실제 제품명 대신 표시되던 버그가 여러 건 있었다.
- 약품명 매칭 후보 목록에서 성분명 사전(`_HARDCODED_FALLBACK`, 약효분류 판정 전용)이 실수로 섞여 있어 성분명이 제품명보다 우선 매칭되던 버그, HIRA 상품명의 괄호 성분명 부기("태극암로디핀정(암로디핀말레산염)")가 유사도 계산을 왜곡해 엉뚱한 브랜드로 오매칭되던 버그, 한글 용량 표기("밀리그램"/"밀리그람")를 인식 못 해 같은 성분 다른 용량끼리 오매칭되던 버그를 모두 수정했다.
- **함량에 "/"가 들어가는 복합제 표기(예: "50/1000mg")와 형태·용량이 붙은 약품명(예: "암로디핀정 5mg")은 이미 v8 이전부터 `parsing_rules.py`가 인식하고 있었다** — 코드 재확인 결과 정규식이 슬래시 구분 복합제 용량을 이미 처리하며, 관련 회귀 테스트도 존재한다. 요구사항_정의서에 명시적 REQ로 추가해 추적 가능하게 한다(REQ-052, 신규).
- **약효분류(drug_class)는 v8 이전부터 이미 필수 입력이 아니다** — `records_router.py`/`ocr_router.py` 확인 결과 `drug_class`가 비어 있어도 처방전 등록·확인·가이드 생성 흐름이 막히지 않는다(빈 문자열 기본값으로 통과). 이 역시 REQ로 명시해 "선택 정보"임을 문서화한다(REQ-053, 신규).
- 진단명 추출 정규식이 개행 없는 OCR 텍스트에서 연락처·처방 목록까지 통째로 삼켜 `diagnosis` 컬럼 길이 초과로 처방전 확정 자체가 실패하던 버그를 수정했다(정지 조건 추가 + 방어적 길이 제한).

**설계 변경(v6 대비, v8과 동일 — 정합성 검토 REQ-011 지적 반영해 문구 명확화)**: v6은 OCR 신뢰도(`confidence < 0.80`)에 따라 `review_required` 여부가 갈렸지만, **실제로는 신뢰도와 무관하게 항상 `review_required`로 반환**하고 사람이 `POST /records/{id}/confirm`으로 확정해야 다음 단계로 넘어간다. 요구사항_정의서_v8이 아직 "0.80 미만만 review_required"로 서술하던 부분을 v9에서 정정한다.

### 미구현 항목 (v8과 동일)
- OCR 재시도 전용 엔드포인트, OCR 완료 시각 전용 필드

## 5. 복약·생활습관 가이드 (REQ-012~020, REQ-028, REQ-032~033)

가이드 생성은 `POST /records/{record_id}/confirm` 호출 시 그 안에서 함께 실행된다.

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/records/{record_id}/confirm` | 약물 항목 확정 → RAG 가이드 생성 → 복약일정 자동 등록 | 경로 `record_id`; `{medications:[...]}` | `200 {record_id, status, failure_reason, created_at, uploaded_by_name, medications:[...], guide:{medication_guide, lifestyle_guide, source_refs}}` | O | 완료 |
| GET | `/rag/ping` | RAG 라우터 연결 확인 | 없음 | `200 {status:"ok", owner:"김영혜"}` | X | 완료(디버그용) |
| POST | `/rag/test/{record_id}` | RAG 가이드 생성 단독 테스트 | 경로 `record_id` | `200 {guide_id, cached, cache_expires_at, note}` | O | 완료(테스트용) |

**[v9 정정] `POST /records`·`/records/manual`·`/records/{id}/confirm`의 응답에는 `cached`/`cache_expires_at` 최상위 필드가 없다** — `_build_record_response()`(`records_router.py`)는 `record_id`/`status`/`failure_reason`/`created_at`/`uploaded_by_name`/`medications`/`guide`만 반환하며, `confirm_medications()`는 `run_rag()`가 돌려주는 캐시 여부·만료시각을 `_from_cache`/`_cache_expires_at`(밑줄 접두사로 명시적으로 버림)로 무시하고 응답에 포함하지 않는다(2026-07-21 코드 재확인). 캐시 정보는 `POST /rag/test/{record_id}`(디버그·테스트 전용 엔드포인트)의 응답에만 노출된다.

가이드 캐싱(REQ-020, PR #60)은 v8과 동일 — SHA-256 캐시 키로 `guide_cache` 테이블에 7일 TTL 저장, stub 모드에서는 캐시하지 않는다.

**[v9] 검색 우선순위 정리(PR #62)**: 의약품 정보(효능·효과·주의사항 등)는 e약은요/HIRA/DUR/식약처 허가정보 같은 open API 조회 결과가 없으면 애초에 `NoContextFoundError`로 가이드 생성 자체가 실패하도록 이미 설계돼 있었다(open API 우선 원칙이 이미 강제됨, 추가 수정 불필요). 반면 **생활습관 안내(음식·운동·주의사항)는 질병관리청 국가건강정보포털 실제 수집분보다, 학회 진료지침을 AI가 요약한 미검증 2차 가공 데이터(`data/lifestyle_guidelines.json`, 4개 질환만 커버)가 먼저 조회되고 있었다** — v9에서 질병관리청 데이터(`search_kdca_health_info`)를 최우선으로, curated 데이터는 그걸로 못 찾을 때만 보강하도록 순서를 바꿨다.

**[v9] 챗봇 DUR 조회 속도 개선**: DUR 관련 질문(병용금기 등) 하나당 최대 약 60회의 순차 정부 API 호출이 걸리던 것을, 결과 캐싱(`lru_cache`)과 병렬 호출(`ThreadPoolExecutor`)로 개선했다(엔드포인트 계약 변경 없음, 응답 속도만 개선).

`RAG_PROVIDER` 환경변수로 전환(기본 `stub`, `real`이면 실제 파이프라인 `rag/`(LangChain+ChromaDB+OpenAI) 동작)하는 것은 v8과 동일.

- **면책 고지(REQ-032)**: v8과 동일하게 여전히 API 응답 필드가 아니다. RAG 파이프라인(`rag/rag_chain.py`)의 `GuideResponse`는 `disclaimer`를 생성하지만 `rag_router.py`가 추출하지 않아 API 응답에는 없다 — 프론트엔드(`Result.tsx`/`Dashboard.tsx`/`Processing.tsx`) 하드코딩이다. **요구사항_정의서_v8이 아직 REQ-032를 "완료"로 서술하고 있어 정합성 검토에서 지적됐다 — v9에서 "부분"으로 정정한다.**

### 미구현 항목 (v8과 동일)
- 가이드 재생성 전용 엔드포인트, TTS 음성, SSE 진행률 스트리밍

## 6. 챗봇 (REQ-021~022, REQ-048)

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| GET | `/chat/questions` | 고정/동적 질문 버튼 목록 — 환자가 등록한 약이 있으면 그 약 이름 기반 동적 질문, 없으면 고정 질문 | 쿼리 `patient_id`(필수) | `200 [{id, text}]` | O | 완료 |
| POST | `/chat/ask` | 고정/동적/자유 텍스트 질문에 답변 | `{patient_id, question_id?, question?}` | `200 {question, answer, answer_source, source_refs, created_at}` | O | 완료 |
| POST | `/chat/ask/stream` | 위와 동일하나 SSE로 토큰 단위 스트리밍 | `{patient_id, question_id?, question?}` | `text/event-stream` — `data: {"delta": "..."}`* N + 마지막 `data: {"done":true, "answer_source", "source_refs", "created_at", "partial"}` | O | 완료 |
| GET | `/chat/history` | 대화 이력 조회 | 쿼리 `patient_id` | `200 [ChatMessage]` | O | 완료 |

**[v9 정정] 6절 전체가 이제 인가 적용 대상이다** — 4개 엔드포인트 모두 `Depends(get_current_actor)` + `require_actor_patient_access(patient_id, ...)`를 거친다(2026-07-14 도입, 상단 "인가" 절 참고). `GET /chat/questions`는 v8 문서에 누락돼 있던 `patient_id` 필수 쿼리 파라미터를 v9에서 추가했다(2026-07-19 커밋으로 이미 필수화됨).

**[v9] `source_refs` 응답 필드 추가(PR #62)** — v8까지는 `answer_source`(예: `"llm (gpt-4o-mini)"`, 생성 **방법** 라벨일 뿐)를 프론트가 "출처"로 오인해 표시하고 있었다. 실제 ChromaDB 검색 결과(제품명/필드명 등)를 `source_refs`로 뽑아 응답에 포함하도록 수정했다. DUR 전용 질문(병용금기 등)은 이 배열이 항상 빈 배열이다(ChromaDB를 거치지 않고 DUR API/CSV로 직접 답하므로).

**[v9] preset/dynamic 질문의 LLM 유출 버그 수정(PR #61)** — v8까지는 정해진 질문(preset/dynamic)을 선택해도 `_CHAT_LLM_AVAILABLE`이면 무조건 LLM을 다시 호출해 고정 답변이 아닌 LLM 생성 답변이 나가는 버그가 있었다. `_resolve_question()`이 이제 `use_llm` 플래그를 함께 반환해, preset/dynamic 매칭 성공 시에는 LLM을 호출하지 않고 검수된 고정 답변을 그대로 반환한다(freeform 자유 질문만 LLM 호출). 같은 PR에서 "내 약 등록"(`PatientMedication`)만 하고 처방전 OCR 기록이 없는 환자의 LLM 컨텍스트에 등록약 이름이 누락되던 버그도 수정했다.

**[v9] 생활습관 vs 의약품 질문 분류(PR #62)** — 챗봇 자유질문의 RAG 검색도 5절과 동일한 원칙(질병관리청 우선/open API 우선)을 적용해, 질문 종류(생활습관 키워드 포함 여부)에 따라 우선 조회하는 `doc_type`을 다르게 적용한다.

`CHAT_PROVIDER` 환경변수로 전환하는 것은 v8과 동일.


## 7. 환자 내약 등록·복약기록 (REQ-036~038, REQ-052~053, REQ-061, v10 신규 문서화)

`patient_medications_router.py`는 2026-07-14 `main.py`에 등록됐지만 v9에서는 "범위 밖"으로 남아 있었다. v10에서는 실제 라우터 prefix(`/patients`) 기준으로 별도 절을 신설한다. 이 절은 처방전 OCR 결과와 별도로 환자/보호자가 직접 확정한 "현재 복용 중인 약"을 관리하는 API다. 모든 엔드포인트는 `get_current_actor`와 `require_actor_patient_access(patient_id, ...)`로 본인 환자 또는 연결된 환자 접근만 허용한다.

REST 관점에서 리소스는 `patients/{patient_id}` 하위의 `medications`, `medication-records`다. `DELETE`는 의료 데이터 복구 가능성을 위해 실제 삭제가 아니라 `deleted_at`을 채우는 soft delete다.

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/patients/{patient_id}/medications` | 환자 내약 등록 | `{drug_id?, item_seq?, product_code?, medication_name, manufacturer_name?, dosage_amount?, dosage_unit?, frequency_per_day?, administration_route?, start_date?, end_date?, prescription_id?, source_type?, source_raw_text?, verification_status?, is_active?}` | `200 PatientMedicationPublic` | O | 완료 |
| GET | `/patients/{patient_id}/medications` | 환자 내약 목록 조회 | 쿼리 `include_inactive?`(기본 true) | `200 [PatientMedicationPublic]` | O | 완료 |
| GET | `/patients/{patient_id}/medications/{medication_id}` | 환자 내약 단건 조회 | 경로 `patient_id`, `medication_id` | `200 PatientMedicationPublic` | O | 완료 |
| PATCH | `/patients/{patient_id}/medications/{medication_id}` | 환자 내약 수정 | 수정할 필드만 | `200 PatientMedicationPublic` | O | 완료 |
| DELETE | `/patients/{patient_id}/medications/{medication_id}` | 환자 내약 soft delete — `deleted_at` 기록 + `is_active=false` | 경로 `patient_id`, `medication_id` | `200 {deleted: medication_id}` | O | 완료 |
| POST | `/patients/{patient_id}/medications/{medication_id}/schedules` | 내약 기반 복약 일정 생성 | `{time_slot, dose_timing?, meal_relation?, instructions?, timezone?, days_of_week?, caregiver_alert?, memo?}` | `200 SchedulePublic` | O | 완료 |
| POST | `/patients/{patient_id}/medication-records` | 내약 기반 복약 기록 생성 | `{patient_medication_id, schedule_id?, scheduled_at?, taken_at?, status?, verification_method?, evidence_image_url?, memo?}` | `200 MedicationRecordPublic` | O | 완료 |
| GET | `/patients/{patient_id}/medication-records` | 내약 기반 복약 기록 조회 | 쿼리 `patient_medication_id?` | `200 [MedicationRecordPublic]` | O | 완료 |

**검증 규칙**: `medication_id`·`patient_medication_id`가 경로의 `patient_id` 소유가 아니면 404로 응답해 IDOR를 막는다. `source_type="manual"`이면 사람이 직접 확정한 값으로 보고 `verification_status` 기본값을 `user_confirmed`로 둔다. 그 외 `prescription_ocr`/`pill_image`/`api_search`는 `unverified`가 기본값이다.

**의약품 마스터와의 관계**: 이 프로젝트에는 아직 별도 의약품 마스터 테이블이 없다. 따라서 `drug_id`, `item_seq`, `product_code`는 클라이언트 또는 OCR/API 검색 단계에서 이미 확정된 값이 있을 때만 저장한다. 라우터 내부에서 임의로 제품명을 재매핑하지 않고, 원문 추적이 필요한 경우 `source_raw_text`를 보존한다.

## 8. 복약 알림·기록·모니터링 (REQ-007, REQ-026a~026d, REQ-036~038)

**[v9 정정] `POST .../check`의 요청 바디에는 `confirmed_by_caregiver_id`가 없다** — v8까지 이 필드를 클라이언트가 보낼 수 있는 것처럼 서술했으나, 실제로는 요청 중인 사용자(`actor`)가 보호자면 서버가 `subject.id`로 직접 계산해 채운다(다른 환자와 무관한 보호자 id를 클라이언트가 임의로 지정하지 못하도록 하는 2026-07-20 보안 수정, `monitoring_router.py:529`). 클라이언트는 `status`만 보낸다.

**[v9] `medication_records`가 유일한 실사용 복약기록 테이블로 승격됐다(PR #62)** — v8까지는 `medication_logs`(실사용, `taken`/`skipped`만)와 `medication_records`(프론트 어디서도 호출 안 되는 죽은 코드, `missed` 포함 5개 상태)가 이원화돼 있었다. `medication_logs` 테이블 자체는 하위호환을 위해 이번 버전에서 DROP하지 않았다(1스프린트 관찰 후 별도 정리 예정).

| Method | Endpoint | 설명 | 요청 | 응답 | 인증 | 구현 |
|---|---|---|---|---|---|---|
| POST | `/monitoring/schedules` | 복약 일정 등록 | `{patient_id, drug_name, time_slot, dose_timing?, caregiver_alert?, memo?}` | `200 MedicationSchedule` | O | 완료 |
| GET | `/monitoring/schedules` | 일정 조회 | 쿼리 `patient_id`(필수), `active_only?`(기본 true) | `200 [MedicationSchedule]` | O | 완료 |
| PATCH | `/monitoring/schedules/{schedule_id}` | 일정 변경 | 경로 `schedule_id`; 변경 필드 | `200 MedicationSchedule` | O | 완료 |
| DELETE | `/monitoring/schedules/{schedule_id}` | 일정 및 관련 기록 삭제 | 경로 `schedule_id` | `200 {deleted:id}` | O | 완료 |
| POST | `/monitoring/schedules/{schedule_id}/check` | 복약 체크(오늘자) — `medication_records`에 기록 | `{status}` | `200 {schedule_id, status}` | O | 완료 |
| DELETE | `/monitoring/schedules/{schedule_id}/check` | 체크 취소(pending으로 되돌림) | 경로 `schedule_id` | `200 {schedule_id, status:"pending"}` | O | 완료 |
| GET | `/monitoring/logs` | 최근 N일 복약 로그 | 쿼리 `patient_id`(필수), `days?`(기본 30) | `200 [{..., status, checked_at, confirmed_by_type, confirmed_by_name}]` | O | 완료 |
| GET | `/monitoring/today` | 오늘자 통합 조회(대시보드용) — `taken`/`pending`/`skipped`/`missed` 4가지 상태 | 쿼리 `patient_id`(필수) | `200 [{id, name, time, note, status}]` | O | 완료 |
| GET | `/monitoring/patients/{patient_id}/known-drugs` | 드롭다운용 기존 약물명 목록 | 경로 `patient_id` | `200 [str]` | O | 완료 |
| GET | `/notification-settings` | 알림 수신 설정 조회 | 쿼리 `patient_id` | `200 NotificationSetting` | O | 완료 |
| PUT | `/notification-settings` | 알림 수신 설정 변경 | 쿼리 `patient_id`; 변경 필드 | `200 NotificationSetting` | O | 완료 |

**[v9] 알림 발송 로직 실체 확인 — v8의 "설정값 저장만"이라는 서술을 정정한다.** `backend/core/scheduler.py`는 60초 주기 in-process 비동기 루프(Celery/Redis Stream 아님, REQ-029가 요구하는 방식과 다름 — 팀이 규모상 이 방식을 의도적으로 선택)로 다음을 수행한다:
1. **리마인더 발송**: 활성 일정의 `time_slot`이 막 지난(10분 이내) 항목마다 `notification_logs`에 `kind="reminder"` 행을 만들고, `notification_settings.medication_reminder_enabled`가 꺼져 있으면 `status="suppressed"`로 기록만 하고 실제 발송은 하지 않는다(발송 자체는 이메일만, 아래 참고).
2. **누락 판정**: 정각+60분이 지나도 `medication_records`에 기록이 없으면 `kind="missed"`로 표시하고 마찬가지로 알림을 시도한다.
3. **실제 발송 채널은 이메일(mock/smtp)뿐이다** — `sms_enabled`는 회원가입에서 수집하는 선호도 값일 뿐 실제 SMS 발송 로직(문자 게이트웨이 연동)은 없다. Push(FCM 등) 인프라도 없다. 수신 대상은 환자 본인(이메일 수신 동의 시) + 최소 1인의 보호자(단, `care_level="third_party_needed"`면 전체 보호자)이며, 이 role 분기도 위 3절의 "자가진단 폐기" 영향으로 실질적으로는 항상 "1인"쪽 분기만 탄다.

`medication_reminder_enabled`(복약 알림), `care_alert_enabled`(보호자 돌봄 알림), `all_push_enabled`(전체 푸시 스위치)는 기본값 전부 `true`.

`confirmed_by_name`(복약 체크를 대신 확인한 보호자 이름)은 평문 응답.

### 미구현 항목
- 실제 SMS/Push 발송 — 이메일(mock/smtp)만 실제로 동작(v8 "설정값 저장만"에서 v9 정정)
- `PATCH /notifications/{id}` 읽음 처리
- `GET /monitoring/medication-subjects/{id}`(집계 API) — 로그 원본 조회만 있고 집계 API는 없음

## 9. 교육·추적관리 (REQ-040~044) — 구현취소

`education_profiles`, `education_support_logs`에 해당하는 테이블·엔드포인트가 `backend/models.py`/`backend/routers/`에 전혀 없다(v8과 동일). 2026-07-22 문서 최신화 시점에 팀 범위에서 **지원인력 교육지원/교육·추적관리 기능은 구현하지 않기로 결정**했으므로, REQ-040~044는 "다음 스프린트 후보"가 아니라 **구현취소**로 관리한다. **REQ-043("guardian은 교육자 지정 불가")도 이 기능 자체가 취소되어 적용 대상이 없다** — 정합성 검토에서 "API명세서에 이 제약이 전혀 언급 없다"고 지적됐으나, 애초에 이 REQ가 다루는 기능을 제품 범위에서 제외했기 때문에 코드 레벨 제약도 만들지 않는다.

## 범위 밖(v10 기준)

- `patient_medications_router.py`는 v10 7절에 문서화 완료했다.
- `care_router`의 prefix 부재(`/invitations`, `/assessments`, `/notification-settings`가 루트에 노출)는 실제 코드와 프론트 호출부에 영향을 주므로 이번 문서 버전업에서는 경로를 바꾸지 않고 알려진 REST 일관성 개선 후보로 남긴다.
- 교육·추적관리(REQ-040~044)는 지원인력 교육지원 기능을 제품 범위에서 제외하기로 하여 9절 구현취소로 유지한다.

## 상태 코드

`200` 성공, `201` 없음(v8까지 있던 `POST /auth/signup`이 제거되며 이 프로젝트에서 `201`을 명시적으로 반환하는 엔드포인트가 없어짐 — 회원가입은 이제 `/monitoring/patients`·`/monitoring/caregivers`가 `200`으로 응답), `400` 잘못된 요청(로그인 실패·계정 잠금·탈퇴 관련 등), `401` 인증 실패(refresh 토큰 무효/재사용, reset_token 무효), `403` 인가 실패, `404` 리소스 없음, `409` 상태 충돌, `422` pydantic 검증 실패, `500` 서버 오류, `502`/`503`/`504` OCR 외부 호출(CLOVA) 실패.
