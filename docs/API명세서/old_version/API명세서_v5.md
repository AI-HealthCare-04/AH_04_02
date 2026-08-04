# API 명세서 — 진료기록 기반 복약·생활습관 안내 시스템

Base URL은 `/api`, 데이터베이스는 **MySQL 8.0**을 사용하며, 필드명은 `snake_case`, 시간은 ISO 8601 UTC 저장·표시 시 사용자 시간대로 변환한다. 로그인 제외 모든 요청은 `Authorization: Bearer {JWT}`가 필요하다.

> 버전: v5 (2026-07-03). v4 대비 변경 내역은 `docs/API명세서/revision_log` 참고.

## 공통 모델

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "요청 값을 확인해 주세요.",
  "details": [{"field": "drug_name", "reason": "required"}],
  "request_id": "req_01..."
}
```

비동기 작업 접수 API는 P95 3초 이내 `202 Accepted`를 반환한다. OCR 완료 후 가이드 생성 완료 목표는 10초이며, 완료 여부는 상태 조회 또는 SSE로 전달한다.

## 1. 인증·사용자 (REQ-001, REQ-031, REQ-035, REQ-039)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/auth/register` | 회원가입 | `{email?, phone?, password, name, role}` | `201 {user_id, role}` |
| POST | `/auth/login` | 로그인 | `{email_or_phone, password}` | `200 {access_token, refresh_token, user_id, role, last_login_at}` |
| POST | `/auth/refresh` | access token 갱신·refresh token 순환 | `{refresh_token}` | `200 {access_token, refresh_token, expires_in}` |
| GET | `/users/me` | 내 계정 정보 조회 | 없음 | `200 {user_id, email, phone, name, role, status, last_login_at}` |
| POST | `/auth/password-reset/request` | 재설정 코드 요청 | `{email_or_phone}` | `200 {message}` |
| POST | `/auth/temporary-codes` | 잠금 계정 임시번호 재전송 | `{email_or_phone}` | `200 {message, delivery_target}` |
| POST | `/auth/temporary-login` | 임시번호 인증·재설정 전용 로그인 | `{email_or_phone, temporary_code}` | `200 {password_reset_token, must_reset_password:true}` |
| POST | `/auth/password-reset/confirm` | 새 비밀번호 설정·잠금 해제 | `{password_reset_token, new_password}` | `200 {status:"active", password_reset:true}` |
| DELETE | `/users/me` | 탈퇴 요청 | `{password}` | `202 {status:"withdrawal_pending", purge_at}` |
| PATCH | `/users/me` | 30일 내 탈퇴 취소(`{status:"active"}`) | `{status:"active"}` | `200 {status:"active", purge_status:"cancelled"}` |

회원 역할은 `medication_subject`, `guardian`, `caregiver`, `life_support_worker`, `social_worker`, `admin`으로 구분한다. `지원인력`은 `caregiver`, `life_support_worker`, `social_worker`를 통칭한다. `교육자`는 이 지원인력이 신규 복약관리 대상자의 앱 사용 교육을 수행할 때 적용되는 업무 역할이며 별도 로그인 역할이 아니고 `guardian`은 포함하지 않는다. 클라이언트는 탈퇴 전 확인 모달을 표시한다. 서버는 즉시 비활성화 후 30일간 soft delete하고 법적 보존 의무가 없는 개인정보를 영구 삭제한다.

로그인 5회 연속 실패 시 계정을 잠그고 가입 시 인증된 이메일 또는 연락처로 6자리 일회용 임시번호를 자동 전송한다. `/auth/login`은 `423 Locked`와 `{error_code:"ACCOUNT_LOCKED", temporary_code_sent:true, delivery_target}`을 반환하며 대상 주소는 마스킹한다. 임시번호는 원문이 아닌 해시로 저장하고 10분 후 만료되며 한 번만 사용할 수 있다. `/auth/temporary-login` 성공 시 일반 access token 대신 비밀번호 재설정에만 사용할 수 있는 단기 `password_reset_token`을 발급한다. `/auth/password-reset/confirm`이 성공해야 계정 잠금과 실패 횟수를 초기화하고 정상 로그인을 허용한다. 임시번호 재전송·검증 횟수를 제한하고 계정 존재 여부와 관계없이 재전송 응답을 동일하게 반환한다(REQ-039). (v5) 재전송은 새 임시번호 자원을 발급하는 동작이므로 `POST /auth/temporary-code/resend` 대신 컬렉션 생성 형태인 `POST /auth/temporary-codes`로 표현한다. 호출 시 기존 미사용 임시번호는 자동 폐기하고 새 코드만 유효하게 한다.

`access_token`은 API 호출에 사용하는 단기 토큰이고 `refresh_token`은 access token 갱신용 장기 토큰이다. `/auth/refresh` 성공 시 기존 refresh token을 폐기하고 새 토큰으로 순환 발급한다. 만료·폐기·위조된 토큰은 `401 Unauthorized`, `error_code: "INVALID_REFRESH_TOKEN"`을 반환한다. 탈퇴 API의 `purge_at`은 `withdrawal_requested_at + 30일`이며 실제 영구 삭제 완료 증빙은 개인정보를 제거한 별도 감사 기록으로 관리한다.

`DELETE /users/me` 처리 시 서버는 감사 기록(`privacy_purge_audits`)을 조회해 없으면 `purge_status:"scheduled"`로 새로 생성하고, 과거 취소로 남아있는 레코드가 있으면 재사용해 요청·삭제예정 시각을 갱신하고 `purge_status:"scheduled"`로 되돌린다(동일 사용자 재탈퇴 시 UK 충돌 방지). 30일 내 `PATCH /users/me`에 `{status:"active"}`를 보내 탈퇴를 취소하면 계정을 `active`로 되돌리되, 이 감사 기록은 삭제하지 않고 `purge_status:"cancelled"`로 갱신해 취소 이력을 보존한다. (v5) 탈퇴 취소를 `POST /users/me/withdrawal/cancel`이라는 동사형 경로 대신, 이미 존재하는 사용자 리소스의 `status` 필드를 바꾸는 `PATCH /users/me` 요청으로 표현해 리소스 지향적으로 정리했다. `status`에 `active` 외의 값을 보내면 `422 Validation Error`를 반환한다.

(v5) `users.last_login_at`을 응답에 노출한다. `/auth/login` 응답의 `last_login_at`은 이번 로그인이 아닌 직전 로그인 시각이며(첫 로그인은 `null`), 로그인 성공 처리 트랜잭션 안에서 이전 값을 응답에 담은 뒤 현재 시각으로 갱신한다. `GET /users/me`는 갱신된 최신 `last_login_at`을 반환한다.

## 2. 돌봄관계 (REQ-002~004)

(v5) 이 절의 이전 이름은 "신뢰관계"였고 엔드포인트는 `/trust/*`였다. `relation_type`에 `guardian` 외에도 `caregiver`·`life_support_worker`·`social_worker`가 포함되어 "신뢰(trust)"·"보호자(guardian)"라는 이름이 관계 유형 전체를 정확히 담지 못했다. 그래서 테이블·경로·필드명을 도메인 중립적인 "돌봄관계(care relation)"로 통일한다: `trust_invitations`→`care_relation_invitations`, `trust_relations`→`care_relations`, `trustee_id`→`related_user_id`, `trust_id`→`care_relation_id`.

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/care-relations/invitations` | 보호자·지원인력 초대 | `{medication_subject_id, invited_phone, relation_type}` | `201 {invitation_id, invite_token, expires_at}` |
| POST | `/care-relations/invitations/{invite_token}/accept` | 초대 수락·관계 생성 | 없음 | `200 {invitation_id, care_relation_id, status:"approved"}` |
| POST | `/care-relations/invitations/{invite_token}/reject` | 초대 거절 | 없음 | `200 {invitation_id, status:"rejected"}` |
| GET | `/care-relations` | 관계 목록 | `?medication_subject_id=` | `200 [{care_relation_id, medication_subject_id, related_user_id, related_user_name, relation_type, status}]` |
| DELETE | `/care-relations/{care_relation_id}` | 연결 해제/해제 요청 | 없음 | `200 {care_relation_id, status}` |
| PATCH | `/care-relations/{care_relation_id}/revocation` | 해제 승인·반려 결정 | `{revocation_decision}` | `200 {care_relation_id, status, revocation_decision, revocation_decided_by, revocation_decided_at}` |

`relation_type`은 `guardian`, `caregiver`, `life_support_worker`, `social_worker`다. 복약관리 대상자의 최신 `care_level`이 `independent` 또는 `guardian_check`이면 본인의 연결 해제 요청을 즉시 `revoked` 처리한다. 최신 `care_level`이 `third_party_needed`이면 `revocation_pending`으로 전환하고 다른 승인된 보호자·지원인력 또는 관리자의 승인 절차를 거친다. 마지막 연결의 해제가 승인되어 승인 관계가 0명이 되면 REQ-007a 연결 권유 안내를 활성화하되 서비스는 차단하지 않는다.

가입 전 전화번호에도 초대를 발급할 수 있다. 서버는 원문 초대 토큰을 응답으로 한 번만 제공하고 DB에는 해시를 저장한다. 수신자가 동일 전화번호를 인증해 가입·로그인한 뒤 수락하면 `care_relations`를 생성하고 승인자·승인시각을 기록한다. 만료 토큰은 `410 Gone`과 `INVITATION_EXPIRED`, 인증 전화번호 불일치는 `403 Forbidden`과 `INVITATION_RECIPIENT_MISMATCH`를 반환한다.

이미 수락·거절·취소된 초대 토큰을 다시 사용하면 `409 Conflict`, `error_code:"INVITATION_ALREADY_PROCESSED"`를 반환한다.

해제 승인 요청의 `{revocation_decision:"approved"}`는 관계를 `revoked`로 변경한다. `{revocation_decision:"rejected"}`는 해제 요청을 반려하고 관계를 `approved`로 복귀시키며 `revocation_decision:"rejected"`, 결정자, 결정시각을 반환한다. `rejected` 관계 상태는 초대 거절 의미로 사용하지 않고 초대 상태에서만 관리한다. (v5) 요청 바디를 boolean `{approve}`에서 DB 컬럼과 동일한 이름·값의 `{revocation_decision: "approved"|"rejected"}` enum으로 바꾸고, 엔드포인트도 동사 `revocation-approval` 대신 `revocation` 하위자원에 대한 상태 변경(`PATCH`)으로 표현했다.

## 3. 상태·복약가능여부 (REQ-005~007, REQ-007a)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-subjects/{subject_id}/status` | 상태 저장 및 자동 재평가 (보호자·지원인력용) | `{cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness}` | `201 {status_id, care_level_assessment:{assessment_id, care_level, reason, evaluated_at}}` |
| GET | `/medication-subjects/{subject_id}/status` | 최신 상태 (보호자·지원인력용) | 없음 | `200 {status_id, cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness, updated_by, created_at}` |
| GET | `/medication-subjects/{subject_id}/care-level` | 최신 평가 1건 (보호자·지원인력용) | 없음 | `200 {assessment_id, status_id, care_level, reason, evaluated_at}` |
| GET | `/medication-subjects/{subject_id}/care-level/history` | 평가 이력 (보호자·지원인력용) | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/medication-subjects/{subject_id}/care-level-notice` | 보호자·지원인력 연결 권유 표시 여부 (보호자·지원인력용) | 없음 | `200 {should_show, dismissed_until?}` |
| POST | `/medication-subjects/{subject_id}/care-level-notice/dismissals` | 권유 안내 닫기 (보호자·지원인력용) | 없음 | `201 {dismissed_until}` |
| GET | `/users/me/status` | 본인 최신 상태 (v5 추가) | 없음 | `200 {status_id, cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness, updated_by, created_at}` |
| GET | `/users/me/care-level` | 본인 최신 평가 1건 (v5 추가) | 없음 | `200 {assessment_id, status_id, care_level, reason, evaluated_at}` |
| GET | `/users/me/care-level/history` | 본인 평가 이력 (v5 추가) | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/users/me/care-level-notice` | 본인 연결 권유 표시 여부 (v5 추가) | 없음 | `200 {should_show, dismissed_until?}` |
| POST | `/users/me/care-level-notice/dismissals` | 본인 권유 안내 닫기 (v5 추가) | 없음 | `201 {dismissed_until}` |

상태 저장 성공과 평가는 한 트랜잭션이다. 단계는 `independent`, `guardian_check`, `third_party_needed`이며 결과에 따라 보호자 확인 표시와 알림 수신자가 달라진다.

`third_party_needed`이면서 승인된 보호자·지원인력이 없으면 서버는 서비스를 차단하지 않고 연결 권유 표시 여부를 반환한다. 사용자가 안내를 닫으면 서버가 `dismissed_until = dismissed_at + 30일`을 저장한다. 비표시 기간은 평가 단건이 아닌 복약관리 대상자 기준으로 유지하며 새 평가 생성만으로 초기화하지 않는다. 클라이언트는 처방전 업로드 화면 진입 시 표시 여부를 확인하며, 사용자가 계속 거부하더라도 자기결정권을 존중해 서비스 이용을 허용한다(REQ-007a).

(v5) 지금까지 이 절의 모든 조회 API는 `{subject_id}`를 경로에 직접 넣어야 했다. 복약관리 대상자 본인이 자신의 상태·케어레벨을 볼 때도 이 방식만 있으면 먼저 "내 subject_id가 뭔지" 알아내는 절차가 필요했다. 이를 없애기 위해 `/users/me/status`, `/users/me/care-level*` 자기조회 경로를 추가한다 — 인증 토큰(JWT)만으로 호출자 자신의 최신 상태를 반환하며 별도 ID 조회가 필요 없다. 기존 `/medication-subjects/{subject_id}/...` 경로는 그대로 유지하며, 보호자·지원인력이 승인된 `care_relations`를 통해 다른 대상자를 조회할 때 계속 사용한다. 두 경로 모두 실제로는 같은 리소스를 반환하지만 대상 결정 방식이 다르다: `/users/me/...`는 호출자=대상자, `/medication-subjects/{subject_id}/...`는 호출자가 대상자 본인이거나 그 대상자와 승인된 `care_relations`를 가진 사용자여야 한다(그 외 `403 Forbidden`). `dismiss` 동사 경로도 알림 닫힘 이력을 남기는 리소스 생성으로 보고 `care_level_notice_dismissals` 테이블명과 맞춘 `POST .../care-level-notice/dismissals`(`201`)로 바꿨다.

## 4. 진료기록·OCR (REQ-008~011, REQ-023~024)

OCR 제공자는 팀 결정에 따라 **EasyOCR**로 통일한다.

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medical-records` | 이미지 업로드 및 OCR 접수 | multipart `image`, `uploaded_for`(필수) | `202 {record_id, status:"processing"}` |
| GET | `/medical-records/{record_id}/status` | 처리 상태 | 없음 | `200 {record_id, status, progress, stage, failure_reason?}` |
| GET | `/medical-records/{record_id}` | OCR·파싱 결과 | 없음 | `200` 아래 모델 / `202` 처리 중 |
| PATCH | `/medical-records/{record_id}/medications/{medication_id}` | 저신뢰 결과 확인·수정 | `{drug_name, dosage, frequency, diagnosis, drug_class, user_confirmed:true}` | `200 {medication_id, user_confirmed}` |
| POST | `/medical-records/{record_id}/retries` | OCR 재시도 접수 | 없음 | `202 {record_id, status:"processing"}` |
| GET | `/medical-records` | OCR/가이드 이력 | `?date_from=&date_to=&drug_name=&cursor=&limit=` | `200 {items:[...], next_cursor}` |

```json
{
  "record_id": 101,
  "status": "review_required",
  "ocr_provider": "easyocr",
  "ocr_raw_text": "...",
  "uploaded_by": 12,
  "uploaded_for": 7,
  "uploaded_at": "2026-07-01T02:00:00Z",
  "ocr_completed_at": "2026-07-01T02:00:04Z",
  "extracted_medications": [
    {
      "medication_id": 501,
      "drug_name": "암로디핀",
      "dosage": "5mg",
      "frequency": "1일 1회",
      "diagnosis": "고혈압",
      "drug_class": "칼슘채널차단제",
      "confidence": 0.76,
      "user_confirmed": false
    }
  ]
}
```

`uploaded_for`는 항상 필수다. 본인 업로드는 인증 사용자 ID와 같고 대리 업로드는 복약관리 대상자 ID다. `confidence < 0.80`이면 `review_required`로 전환하고 사용자 확인 전 가이드를 확정하지 않는다. OCR 완료 시각은 `ocr_completed_at`, 가이드 완료 시각은 `guide_results.generated_at`에 저장하며 REQ-028의 가이드 생성 10초는 두 시각의 차이로 측정한다.

저신뢰도 OCR은 요청 검증 실패가 아니라 정상 처리 중 사용자 확인이 필요한 작업 상태다. 상태 조회는 `200 {record_id, status:"review_required", error_code:"OCR_REVIEW_REQUIRED"}`를 반환하며 `422`를 사용하지 않는다.

(v5) 재시도는 동사 `retry`가 아니라 새 처리 시도를 만드는 행위이므로 `POST /medical-records/{record_id}/retries`로 표현한다(복수형 컬렉션에 새 시도를 추가).

## 5. 복약·생활습관 가이드 (REQ-012~020, REQ-028, REQ-032~033)

| Method | Endpoint | 설명 | 응답 |
|---|---|---|---|
| GET | `/medical-records/{record_id}/guide` | 최신 가이드(가장 최근 `guide_results` 1건의 단축 경로) | `200 {guide_result_id, medication_guide, lifestyle_guide, source_refs, cached, cache_expires_at?, disclaimer, generated_at}` |
| POST | `/medical-records/{record_id}/guides` | 새 가이드 생성 접수(재생성) | `202 {record_id, status:"processing"}` |
| GET | `/medical-records/{record_id}/guide/stream` | 생성 상태 SSE | `status`, `progress`, `completed`, `failed` 이벤트 |
| GET | `/medical-records/{record_id}/guide/audio` | TTS 음성 | `200 audio/mpeg` |

```json
{
  "guide_result_id": 801,
  "medication_guide": {
    "drugs": [{"drug_name":"암로디핀","dosage_text":"하루 한 번 복용하세요.","caution":"어지러우면 앉아서 쉬세요.","contraindications":[],"guardian_check_required":true}]
  },
  "lifestyle_guide": {
    "diagnosis": "고혈압",
    "related_medications": ["암로디핀"],
    "situational_guidance": [{"situation":"운동 중 어지러울 때","action":"즉시 멈추고 앉아서 쉬세요."}],
    "diet": {"avoid":["짠 음식"],"drug_specific":["자몽 섭취 여부는 의료진에게 확인하세요."]},
    "exercise": {"type":"걷기","duration":"하루 30분","intensity":"가벼운 강도"},
    "caution": ["임의로 복용을 중단하지 마세요."]
  },
  "source_refs": [{"title":"의약품 안전사용 정보","url":"https://...","retrieved_at":"2026-07-01T02:00:00Z"}],
  "cached": false,
  "disclaimer": "본 정보는 의료진의 진단·처방을 대체하지 않습니다.",
  "generated_at": "2026-07-01T02:00:08Z"
}
```

가이드 캐시는 진단명·약물 조합과 출처 데이터 버전을 포함한 `cache_key`로 식별한다. `cache_expires_at`이 지났거나 출처 데이터 버전 변경으로 새 키가 생성되면 기존 결과를 캐시 적중으로 사용하지 않는다.

(v5) 재생성은 동사 `regenerate`가 아니라 `guide_results` 컬렉션에 새 레코드를 만드는 행위이므로 `POST /medical-records/{record_id}/guides`로 표현한다. 기존 `GET .../guide`(단수)는 그대로 유지하며 "가장 최근 `guides` 1건 조회"의 단축 경로로 문서화한다.

## 6. 챗봇 (REQ-021~022)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/chat` | 가이드 기반 질문 | `{guide_result_id, message}` | SSE `chunk`, `source`, `done`, `error` |
| GET | `/chat/{guide_result_id}/history` | 대화 이력 | `?cursor=&limit=` | `200 {items:[{message_id, user_id, role, message, created_at}], next_cursor}` |

챗봇 화면은 대화 중인 `guide_result_id`의 `guide_results.disclaimer`를 항상 표시한다. `/chat` 요청 전 가이드 접근권한과 고지 문구를 함께 조회하며, SSE 연결·오류 여부와 관계없이 고지 영역을 숨기지 않는다(REQ-032).

## 7. 복약 알림·기록·모니터링 (REQ-007, REQ-026a~026d, REQ-036~038)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-schedules` | 복약 일정 등록 | `{medication_subject_id, extracted_medication_id, scheduled_times, timezone, notify_guardian}` | `201 {schedule_ids}` |
| GET | `/medication-schedules` | 일정 조회 | `?medication_subject_id=&active=` | `200 [{schedule_id, drug_name, scheduled_time, timezone, notify_guardian, active}]` |
| PATCH | `/medication-schedules/{schedule_id}` | 일정 변경/중지 | `{scheduled_time?, notify_guardian?, active?}` | `200 {schedule_id, active}` |
| POST | `/medication-intakes` | 복약 여부 기록 | `{schedule_id, scheduled_at, status, note?}` | `201 {intake_id, confirmed_by, confirmed_at}` |
| GET | `/medication-intakes` | 본인 복약 이력 | `?medication_subject_id=&date_from=&date_to=` | `200 [{intake_id, schedule_id, drug_name, status, scheduled_at, confirmed_at, confirmed_by}]` |
| GET | `/monitoring/medication-subjects/{subject_id}` | 승인된 보호자용 요약 | `?date_from=&date_to=` | `200 {care_level, adherence_rate, taken_count, missed_count, recent_intakes}` |
| GET | `/users/me/notification-settings` | 알림 수신 설정 조회 | 없음 | `200 {medication_reminder_enabled, caregiver_alert_enabled, push_enabled, safety_alert_recommendations:[{medication_subject_id, active_safety_recipient_count, should_recommend}]}` |
| PATCH | `/users/me/notification-settings` | 알림 수신 설정 변경 | `{medication_reminder_enabled?, caregiver_alert_enabled?, push_enabled?}` | `200 {medication_reminder_enabled, caregiver_alert_enabled, push_enabled, safety_alert_recommendations:[...]}` |
| PATCH | `/notifications/{notification_id}` | 알림 읽음·확인 처리 | `{acknowledged:true}` | `200 {notification_id, acknowledged_at}` |

`medication_reminder_enabled`는 복약 시간 알림, `caregiver_alert_enabled`는 보호자·요양보호사·생활지원사·사회복지사 돌봄 알림, `push_enabled`는 해당 사용자의 모든 푸시 전달을 허용하는 최종 스위치이며 기본값은 모두 `true`다. 복약관리 대상자·보호자·지원인력은 각 설정을 자유롭게 변경할 수 있다. 돌봄 푸시는 일정별 `notify_guardian`, 수신자의 `caregiver_alert_enabled`, 수신자의 `push_enabled`가 모두 `true`일 때만 해당 수신자에게 발송한다.

`third_party_needed`에서도 서버는 알림 설정을 강제로 켜거나 변경 요청을 거절하지 않는다. 승인 관계는 있으나 `caregiver_alert_enabled=true`와 `push_enabled=true`를 모두 만족하는 관계자가 0명이면 `should_recommend:true`로 최소 한 명의 안전 알림 유지를 권고한다. 사용자가 권고를 거부해도 서비스 이용과 설정 변경을 허용한다. 보호자·지원인력 계정은 여러 복약관리 대상자와 연결될 수 있으므로 권고 정보는 대상자별 배열로 반환한다. 승인 관계 자체가 0명이면 REQ-007a 연결 권유 안내를 표시한다.

`third_party_needed` 복약 알림은 복약관리 대상자와 위 수신 조건에 동의한 승인 보호자·지원인력에게 발송한다. 실제 복약을 확인한 사람이 `/medication-intakes`로 `taken`을 기록하면 서버는 `confirmed_by`, `confirmed_at`을 저장하고 같은 수신 조건을 만족하는 다른 관계자에게 복약 완료 알림을 발송한다. `PATCH /notifications/{notification_id}`의 `{acknowledged:true}`는 알림을 읽었다는 뜻일 뿐 복약 완료로 처리하지 않는다(REQ-026d). (v5) 동사 경로 `/acknowledge` 대신 알림 리소스 자체의 확인 상태를 바꾸는 `PATCH`로 표현한다.

모니터링 API는 승인·배정된 보호자·요양보호사·생활지원사·사회복지사만 접근할 수 있다.

## 8. 교육·추적관리 (REQ-040~044)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-subjects/{subject_id}/education-profiles` | 새 교육·재교육 회차 시작 (교육자·보호자용) | `{education_started_at, assigned_educator_id?, service_program?, eligibility_verified?, restart_reason?}` | `201 {education_profile_id, cycle_number, education_stage, tracking_ends_at}` |
| GET | `/medication-subjects/{subject_id}/education-profile` | 현재 교육 단계·지원 일정 조회 (교육자·보호자용) | 없음 | `200 {education_stage, stage_label, education_started_at, tracking_ends_at, assigned_educator, next_phone_support_at?}` |
| PATCH | `/medication-subjects/{subject_id}/education-profile` | 교육자·전화지원 일정 변경 | `{assigned_educator_id?, next_phone_support_at?, status?}` | `200 {education_profile_id, education_stage, updated_at}` |
| GET | `/medication-subjects/{subject_id}/education-profiles` | 전체 교육 회차 이력 (교육자·보호자용) | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| POST | `/medication-subjects/{subject_id}/education-support-logs` | 교육·전화·방문 지원 기록 | `{support_type, supported_at, note?}` | `201 {support_log_id, educator_id}` |
| GET | `/medication-subjects/{subject_id}/education-support-logs` | 교육 지원 이력 (교육자·보호자용) | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/users/me/education-profile` | 본인 현재 교육 단계·지원 일정 조회 (v5 추가) | 없음 | `200 {education_stage, stage_label, education_started_at, tracking_ends_at, assigned_educator, next_phone_support_at?}` |
| GET | `/users/me/education-profiles` | 본인 전체 교육 회차 이력 (v5 추가) | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/users/me/education-support-logs` | 본인 교육 지원 이력 (v5 추가) | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/educators/me/medication-subjects` | 교육자에게 배정된 대상자 목록 | `?education_stage=&status=` | `200 [{subject_id, name, education_stage, next_phone_support_at}]` |

(v5) 케어레벨과 마찬가지로 이 절의 조회 API도 `{subject_id}`를 몰라도 되도록 `/users/me/education-profile`, `/users/me/education-profiles`, `/users/me/education-support-logs` 자기조회 경로를 추가했다. 복약관리 대상자 본인이 자신의 교육 단계를 확인할 때 사용하며, 교육자·보호자가 배정된 대상자를 조회·수정할 때는 기존 `/medication-subjects/{subject_id}/education-*` 경로를 그대로 쓴다. 교육자·전화지원 일정 변경(`PATCH .../education-profile`)은 교육자·보호자만 수행하는 관리 동작이라 자기조회 대상에서 제외했다.

교육 시작일부터 시작일의 달력상 1개월 후 시점 전까지는 `freshman`(집중교육), 시작일+1개월부터 시작일+2개월 전까지는 `junior`(전화지원), 시작일+2개월 이후는 `senior`(자립단계)로 계산한다. 추적 종료일은 `education_started_at + 2 calendar months`이며 이후에도 일반 복약 서비스는 계속 이용할 수 있다. 교육자는 별도 회원 역할이 아니라 `caregiver`, `life_support_worker`, `social_worker` 사용자가 신규 복약관리 대상자에게 앱 사용 교육을 수행할 때의 업무 역할이다. `assigned_educator_id`는 반드시 이 세 역할 중 하나여야 하며 `guardian`은 지정할 수 없다. 위반 시 `422 Validation Error`를 반환한다. 방문요양 등 사업 자격은 `service_program`, `eligibility_verified`로 별도 관리한다.

완료 후 장기 미사용, 인지·건강 상태 변화 또는 사용자 요청으로 재교육이 필요하면 새 교육 회차를 생성한다. 완료된 회차는 덮어쓰지 않으며 대상자별 현재 회차는 최대 1개다. `paused`는 현재 회차의 일시중지이고 `completed`만 과거 회차로 전환한다. 현재 회차가 있는데 새 회차를 요청하면 `409 EDUCATION_CYCLE_ALREADY_ACTIVE`를 반환한다.

의약품 성상·알약 이미지 인식 기능은 프로젝트 범위에서 제외한다. 대형 글씨 UI는 별도 API가 아니라 프론트엔드 접근성 요구사항(REQ-027, REQ-033)으로 구현한다.

## 상태 코드

`200` 성공, `201` 생성, `202` 비동기 접수, `400` 잘못된 요청 형식, `401` 미인증, `403` 권한 없음, `404` 없음, `409` 상태 충돌/중복, `410` 만료된 리소스, `413` 10MB 초과, `422` 필드·업무규칙 검증 실패, `423` 계정 잠금, `429` 요청 제한, `500` 서버 오류.
