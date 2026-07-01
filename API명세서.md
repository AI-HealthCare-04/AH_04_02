# API 명세서 — 진료기록 기반 복약·생활습관 안내 시스템

Base URL은 `/api`, 필드명은 `snake_case`, 시간은 ISO 8601 UTC 저장·표시 시 사용자 시간대로 변환한다. 로그인 제외 모든 요청은 `Authorization: Bearer {JWT}`가 필요하다.

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
| POST | `/auth/login` | 로그인 | `{email_or_phone, password}` | `200 {access_token, refresh_token, user_id, role}` |
| POST | `/auth/password-reset/request` | 재설정 코드 요청 | `{email_or_phone}` | `200 {message}` |
| POST | `/auth/password-reset/confirm` | 비밀번호 변경 | `{code, new_password}` | `200 {message}` |
| POST | `/auth/unlock/request` | 잠금 해제 인증코드 요청 | `{email_or_phone}` | `200 {message}` |
| POST | `/auth/unlock/confirm` | 인증코드 확인 및 즉시 잠금 해제 | `{email_or_phone, code}` | `200 {status:"active"}` |
| DELETE | `/users/me` | 탈퇴 요청 | `{password}` | `202 {status:"withdrawal_pending", purge_at}` |
| POST | `/users/me/withdrawal/cancel` | 30일 내 탈퇴 취소 | 없음 | `200 {status:"active"}` |

회원 역할은 `medication_subject`, `guardian`, `caregiver`, `life_support_worker`, `social_worker`, `admin`으로 구분한다. 클라이언트는 탈퇴 전 확인 모달을 표시한다. 서버는 즉시 비활성화 후 30일간 soft delete하고 법적 보존 의무가 없는 개인정보를 영구 삭제한다.

로그인 5회 연속 실패 시 계정을 30분 동안 잠그고 `423 Locked`와 `locked_until`을 반환한다. 잠금은 시간이 지나면 자동 해제되며, 등록된 연락처로 발급한 인증코드를 `/auth/unlock/confirm`에서 확인하거나 비밀번호 재설정을 완료하면 즉시 해제한다. 코드 요청·확인 횟수는 제한하고 계정 존재 여부와 관계없이 요청 응답을 동일하게 반환한다(REQ-039).

## 2. 신뢰관계 (REQ-002~004)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/trust/invitations` | 보호자·교육자 초대 | `{medication_subject_id, trustee_phone, relation_type}` | `201 {trust_id, invite_token, expires_at}` |
| POST | `/trust/invitations/{invite_token}/accept` | 초대 수락 | 없음 | `200 {trust_id, status:"approved"}` |
| POST | `/trust/invitations/{invite_token}/reject` | 초대 거절 | 없음 | `200 {trust_id, status:"rejected"}` |
| GET | `/trust/relations` | 관계 목록 | `?medication_subject_id=` | `200 [{trust_id, medication_subject_id, trustee_id, trustee_name, relation_type, status}]` |
| DELETE | `/trust/relations/{trust_id}` | 연결 해제/해제 요청 | 없음 | `200 {trust_id, status}` |
| POST | `/trust/relations/{trust_id}/revocation-approval` | 해제 승인 | `{approve}` | `200 {trust_id, status}` |

`relation_type`은 `guardian`, `caregiver`, `life_support_worker`, `social_worker`다. `independent`, `guardian_check`는 본인 해제 시 즉시 `revoked` 처리한다. `third_party_needed`는 즉시 해제하지 않고 `revocation_pending`으로 전환하며, 다른 승인된 보호자·교육자 또는 관리자의 승인이 필요하다.

## 3. 상태·복약가능여부 (REQ-005~007, REQ-007a)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-subjects/{subject_id}/status` | 상태 저장 및 자동 재평가 | `{cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness}` | `201 {status_id, care_level_assessment:{assessment_id, care_level, reason, evaluated_at}}` |
| GET | `/medication-subjects/{subject_id}/status` | 최신 상태 | 없음 | `200 {status_id, cognitive_level, mobility_level, vision_level, medication_awareness, medication_willingness, updated_by, created_at}` |
| GET | `/medication-subjects/{subject_id}/care-level` | 최신 평가 1건 | 없음 | `200 {assessment_id, status_id, care_level, reason, evaluated_at}` |
| GET | `/medication-subjects/{subject_id}/care-level/history` | 평가 이력 | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/medication-subjects/{subject_id}/care-level-notice` | 보호자·교육자 연결 권유 표시 여부 | 없음 | `200 {should_show, dismissed_until?}` |
| POST | `/medication-subjects/{subject_id}/care-level-notice/dismiss` | 권유 안내 닫기 | 없음 | `200 {dismissed_until}` |

상태 저장 성공과 평가는 한 트랜잭션이다. 단계는 `independent`, `guardian_check`, `third_party_needed`이며 결과에 따라 보호자 확인 표시와 알림 수신자가 달라진다.

`third_party_needed`이면서 승인된 보호자·교육자가 없으면 서버는 서비스를 차단하지 않고 연결 권유 표시 여부를 반환한다. 사용자가 안내를 닫으면 서버가 `dismissed_until = dismissed_at + 30일`을 저장한다. 클라이언트는 처방전 업로드 화면 진입 시 표시 여부를 확인하며, 사용자가 계속 거부하더라도 자기결정권을 존중해 서비스 이용을 허용한다(REQ-007a).

## 4. 진료기록·OCR (REQ-008~011, REQ-023~024)

OCR 제공자는 팀 결정에 따라 **EasyOCR**로 통일한다.

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medical-records` | 이미지 업로드 및 OCR 접수 | multipart `image`, `uploaded_for`(필수) | `202 {record_id, status:"processing"}` |
| GET | `/medical-records/{record_id}/status` | 처리 상태 | 없음 | `200 {record_id, status, progress, stage, failure_reason?}` |
| GET | `/medical-records/{record_id}` | OCR·파싱 결과 | 없음 | `200` 아래 모델 / `202` 처리 중 |
| PATCH | `/medical-records/{record_id}/medications/{medication_id}` | 저신뢰 결과 확인·수정 | `{drug_name, dosage, frequency, diagnosis, drug_class, user_confirmed:true}` | `200 {medication_id, user_confirmed}` |
| POST | `/medical-records/{record_id}/retry` | OCR 재시도 | 없음 | `202 {record_id, status:"processing"}` |
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

`uploaded_for`는 항상 필수다. 본인 업로드는 인증 사용자 ID와 같고 대리 업로드는 복약관리 대상자 ID다. `confidence < 0.80`이면 `review_required`로 전환하고 사용자 확인 전 가이드를 확정하지 않는다.

## 5. 복약·생활습관 가이드 (REQ-012~020, REQ-028, REQ-032~033)

| Method | Endpoint | 설명 | 응답 |
|---|---|---|---|
| GET | `/medical-records/{record_id}/guide` | 최신 가이드 | `200 {guide_result_id, medication_guide, lifestyle_guide, source_refs, cached, disclaimer, generated_at}` |
| POST | `/medical-records/{record_id}/guide/regenerate` | 가이드 재생성 접수 | `202 {record_id, status:"processing"}` |
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

## 6. 챗봇 (REQ-021~022)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/chat` | 가이드 기반 질문 | `{guide_result_id, message}` | SSE `chunk`, `source`, `done`, `error` |
| GET | `/chat/{guide_result_id}/history` | 대화 이력 | `?cursor=&limit=` | `200 {items:[{message_id, user_id, role, message, created_at}], next_cursor}` |

## 7. 복약 알림·기록·모니터링 (REQ-007, REQ-026a~026d, REQ-036~038)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-schedules` | 복약 일정 등록 | `{medication_subject_id, extracted_medication_id, scheduled_times, timezone, notify_guardian}` | `201 {schedule_ids}` |
| GET | `/medication-schedules` | 일정 조회 | `?medication_subject_id=&active=` | `200 [{schedule_id, drug_name, scheduled_time, timezone, notify_guardian, active}]` |
| PATCH | `/medication-schedules/{schedule_id}` | 일정 변경/중지 | `{scheduled_time?, notify_guardian?, active?}` | `200 {schedule_id, active}` |
| POST | `/medication-intakes` | 복약 여부 기록 | `{schedule_id, scheduled_at, status, note?}` | `201 {intake_id, confirmed_by, confirmed_at}` |
| GET | `/medication-intakes` | 본인 복약 이력 | `?medication_subject_id=&date_from=&date_to=` | `200 [{intake_id, schedule_id, drug_name, status, scheduled_at, confirmed_at, confirmed_by}]` |
| GET | `/monitoring/medication-subjects/{subject_id}` | 승인된 보호자용 요약 | `?date_from=&date_to=` | `200 {care_level, adherence_rate, taken_count, missed_count, recent_intakes}` |
| GET | `/users/me/notification-settings` | 알림 수신 설정 조회 | 없음 | `200 {medication_reminder_enabled, caregiver_alert_enabled, push_enabled, forced_by_care_level}` |
| PATCH | `/users/me/notification-settings` | 알림 수신 설정 변경 | `{medication_reminder_enabled?, caregiver_alert_enabled?, push_enabled?}` | `200 {medication_reminder_enabled, caregiver_alert_enabled, push_enabled, forced_by_care_level}` |
| POST | `/notifications/{notification_id}/acknowledge` | 알림 읽음·확인 처리 | 없음 | `200 {notification_id, acknowledged_at}` |

`medication_reminder_enabled`는 복약 시간 알림, `caregiver_alert_enabled`는 보호자·요양보호사·생활지원사·사회복지사 돌봄 알림, `push_enabled`는 전체 푸시 수신 설정이며 기본값은 모두 `true`다. `third_party_needed`이면 복약관리 대상자가 돌봄 알림을 임의로 끌 수 없고, 최소 한 명의 승인된 보호자·교육자에게 안전 알림이 유지되어야 한다. 강제 유지 상태는 `forced_by_care_level: true`로 표시하며 해제 불가능한 변경 요청에는 `409 Conflict`를 반환한다.

`third_party_needed` 복약 알림은 복약관리 대상자와 승인된 보호자·교육자에게 동시에 발송한다. 실제 복약을 확인한 사람이 `/medication-intakes`로 `taken`을 기록하면 서버는 `confirmed_by`, `confirmed_at`을 저장하고 다른 수신자에게 복약 완료 알림을 발송한다. `/notifications/{notification_id}/acknowledge`는 알림을 읽었다는 뜻일 뿐 복약 완료로 처리하지 않는다(REQ-026d).

모니터링 API는 승인·배정된 보호자·요양보호사·생활지원사·사회복지사만 접근할 수 있다.

## 8. 교육·추적관리 (REQ-040~043)

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-subjects/{subject_id}/education-profile` | 교육 시작·교육자 배정 | `{education_started_at, assigned_educator_id?, service_program?, eligibility_verified?}` | `201 {education_profile_id, education_stage, tracking_ends_at}` |
| GET | `/medication-subjects/{subject_id}/education-profile` | 현재 교육 단계·지원 일정 조회 | 없음 | `200 {education_stage, stage_label, education_started_at, tracking_ends_at, assigned_educator, next_phone_support_at?}` |
| PATCH | `/medication-subjects/{subject_id}/education-profile` | 교육자·전화지원 일정 변경 | `{assigned_educator_id?, next_phone_support_at?, status?}` | `200 {education_profile_id, education_stage, updated_at}` |
| POST | `/medication-subjects/{subject_id}/education-support-logs` | 교육·전화·방문 지원 기록 | `{support_type, supported_at, note?}` | `201 {support_log_id, educator_id}` |
| GET | `/medication-subjects/{subject_id}/education-support-logs` | 교육 지원 이력 | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |
| GET | `/educators/me/medication-subjects` | 교육자에게 배정된 대상자 목록 | `?education_stage=&status=` | `200 [{subject_id, name, education_stage, next_phone_support_at}]` |

교육 시작일부터 0~29일은 `freshman`(집중교육), 30~59일은 `junior`(전화지원), 60일 이후는 `senior`(자립단계)로 계산한다. 최대 60일까지 교육·전화지원 이력을 집중 추적하며 그 이후에도 일반 복약 서비스는 계속 이용할 수 있다. 요양보호사·생활지원사·사회복지사를 교육자로 배정할 수 있다. 방문요양 등 사업 자격은 `service_program`, `eligibility_verified`로 별도 관리하며 계정 역할 자체에 연령 제한을 직접 적용하지 않는다.

의약품 성상·알약 이미지 인식 기능은 프로젝트 범위에서 제외한다. 대형 글씨 UI는 별도 API가 아니라 프론트엔드 접근성 요구사항(REQ-027, REQ-033)으로 구현한다.

## 상태 코드

`200` 성공, `201` 생성, `202` 비동기 접수, `400` 검증 실패, `401` 미인증, `403` 권한 없음, `404` 없음, `409` 상태 충돌/중복, `413` 10MB 초과, `422` OCR 결과 확인 필요, `423` 계정 잠금, `429` 요청 제한, `500` 서버 오류.
