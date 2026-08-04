# API 명세서 수정 검토 기록

이 문서는 `API명세서_v2.md`에서 `API명세서_v3.md`로 변경하며 반영한 수정사항과 설계 판단을 기록한 변경 이력이다.

## 결론 요약

| 항목 | 판단 | API 수정 방향 |
|---|---|---|
| `지원인력가` 오타 | 적용 | `지원인력이`로 수정 |
| OCR과 일반 검증의 `422` 충돌 | 적용 | `422`는 검증 실패 전용, OCR 저신뢰도는 정상 작업 상태 `review_required`로 처리 |
| Refresh token 갱신 API | 적용 | `POST /auth/refresh` 추가 |
| 초대 토큰·가입 전 초대 | 적용 | 초대와 승인 관계를 분리하고 `invitation_id` 기준으로 명세 |
| 해제 승인 `approve:false` | 적용 | 해제 요청 반려, 관계는 `approved`로 복귀 |
| 알림 설정·권고 | 적용 | 모든 사용자의 설정 선택권을 보장하고 최소 한 명 유지는 권고 |
| 안전 알림 권고 정보 | 계산 필드 | 대상자별 `active_safety_recipient_count`, `should_recommend` 반환 |
| 재교육 | 적용 | 현재 프로필 API와 교육 회차 이력 API를 구분 |

## 1. 인증·사용자

### Refresh token 갱신

로그인 응답에 `refresh_token`이 있으므로 다음 엔드포인트를 추가한다.

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/auth/refresh` | access token 갱신 및 refresh token 순환 | `{refresh_token}` | `200 {access_token, refresh_token, expires_in}` |

- 유효하지 않거나 만료·폐기된 refresh token은 `401 Unauthorized`, `error_code: "INVALID_REFRESH_TOKEN"`을 반환한다.
- 갱신 성공 시 기존 refresh token을 폐기하고 새 refresh token을 발급한다.
- 탈퇴 대기·삭제·잠금 정책에 따라 갱신을 제한할 수 있으며 제한 사유를 `error_code`로 구분한다.

### 탈퇴 시각

`DELETE /users/me`의 `purge_at`은 `withdrawal_requested_at + 30일`로 반환한다. 실제 영구 삭제 완료 기록은 개인정보가 제거된 별도 감사 로그에 기록한다. `users.deleted_at`을 영구 삭제 완료 시각으로 사용하는 안은 행 자체가 삭제될 수 있어 채택하지 않는다.

## 2. 신뢰관계·초대

### 초대와 승인 관계 분리

가입 전 전화번호 초대를 지원하므로 `trust_invitations`와 `trust_relations`를 분리한다. 초대 생성 시 아직 관계가 없으므로 기존 응답의 `trust_id`를 `invitation_id`로 변경한다.

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/trust/invitations` | 보호자·지원인력 초대 | `{medication_subject_id, invited_phone, relation_type}` | `201 {invitation_id, invite_token, expires_at}` |
| POST | `/trust/invitations/{invite_token}/accept` | 초대 수락 및 관계 생성 | 없음 | `200 {invitation_id, trust_id, status:"approved"}` |
| POST | `/trust/invitations/{invite_token}/reject` | 초대 거절 | 없음 | `200 {invitation_id, status:"rejected"}` |

- 미가입 전화번호도 초대할 수 있다. 수신자가 동일 전화번호로 가입·로그인한 뒤에만 수락할 수 있다.
- 서버는 URL에 전달되는 원문 토큰을 그대로 저장하지 않고 해시로 저장한다.
- 토큰 만료 시 `410 Gone`, `error_code: "INVITATION_EXPIRED"`를 반환한다.
- 로그인 사용자의 인증된 전화번호와 초대 전화번호가 다르면 `403 Forbidden`, `error_code: "INVITATION_RECIPIENT_MISMATCH"`를 반환한다.
- 수락 시 `trust_relations.trustee_id`, `approved_by`, `approved_at`을 수락 사용자로 기록한다.

### 해제 승인과 반려

`POST /trust/relations/{trust_id}/revocation-approval`의 결과를 다음과 같이 확정한다.

- `{approve:true}`: 관계를 `revoked`로 변경한다.
- `{approve:false}`: 해제 요청을 반려하고 관계 상태를 `approved`로 되돌린다.
- `rejected`는 초대 거절 의미로만 사용하며 해제 반려 상태로 사용하지 않는다.

응답은 결정 결과를 명시한다.

```json
{
  "trust_id": 31,
  "status": "approved",
  "revocation_decision": "rejected",
  "revocation_decided_by": 9,
  "revocation_decided_at": "2026-07-02T03:00:00Z"
}
```

## 3. OCR 상태와 HTTP 상태코드

`422 Unprocessable Entity`는 역할 위반·필드 제약 등 일반 검증 실패 전용으로 통일한다.

OCR 저신뢰도는 요청 실패가 아니라 OCR 작업의 정상적인 후속 상태이므로 HTTP 오류로 처리하지 않는다.

- 업로드 접수: `202 {record_id, status:"processing"}`
- OCR 완료 후 확인 필요: 상태 조회에서 `200 {record_id, status:"review_required", error_code:"OCR_REVIEW_REQUIRED"}`
- 교육자 역할 위반 등 검증 실패: `422 {error_code:"VALIDATION_ERROR", ...}`

상태 코드 표의 `422 OCR 결과 확인 필요` 문구는 `422 검증 실패`로 수정한다.

## 4. 복약 알림 우선순위

복약관리 대상자·보호자·지원인력은 각자 알림 설정을 자유롭게 변경한다. 돌봄 알림은 `notify_guardian`, 수신자의 `caregiver_alert_enabled`, `push_enabled`가 모두 `true`일 때만 발송한다.

`third_party_needed`에서 수신 가능한 승인 관계자가 0명이면 서버는 최소 한 명 유지를 권고하지만 설정을 강제로 켜거나 변경 요청을 거절하지 않는다. 대상자별 `active_safety_recipient_count`와 `should_recommend`를 계산해 응답하고, 승인 관계 자체가 0명이면 REQ-007a 연결 권유를 표시한다.

## 5. 가이드 캐시

가이드 응답의 `cached` 판단 근거를 명시한다.

- `cache_key`: 진단명·약물 조합·출처 데이터 버전을 포함한 해시
- `cache_expires_at`: 시간 기준 캐시 만료 시각
- 출처 버전이 변경되면 새로운 `cache_key`가 생성되어 기존 캐시를 재사용하지 않는다.

`cache_expired_at`보다 만료 예정 시각을 뜻하는 `cache_expires_at`을 사용한다.

## 6. 연결 권유 안내

`승인된 보호자·지원인력가 없으면`을 `승인된 보호자·지원인력이 없으면`으로 수정한다.

권유 안내는 대상자 단위 30일 비표시 정책으로 확정한다. 새 케어레벨 평가가 생성됐다는 이유만으로 비표시 기간을 초기화하지 않는다.

## 7. 재교육 회차

재교육 이력을 보존하기 위해 기존 API를 현재 회차 기준으로 명확히 하고 이력 조회를 추가한다.

| Method | Endpoint | 설명 | 요청 | 응답 |
|---|---|---|---|---|
| POST | `/medication-subjects/{subject_id}/education-profiles` | 새 교육·재교육 회차 시작 | `{education_started_at, assigned_educator_id?, service_program?, eligibility_verified?, restart_reason?}` | `201 {education_profile_id, cycle_number, education_stage, tracking_ends_at}` |
| GET | `/medication-subjects/{subject_id}/education-profile` | 현재 교육 회차 조회 | 없음 | `200 {...}` / 현재 회차 없으면 `404` |
| GET | `/medication-subjects/{subject_id}/education-profiles` | 전체 교육 회차 이력 | `?cursor=&limit=` | `200 {items:[...], next_cursor}` |

- 새 회차 시작 시 기존 현재 회차가 있으면 `409 EDUCATION_CYCLE_ALREADY_ACTIVE`를 반환한다.
- 완료된 회차는 수정하지 않고 새 행으로 재교육을 시작한다.
- `paused`는 종료가 아니라 현재 회차의 일시중지 상태다.

## 8. 해제 승인·반려 응답 구체화

`POST /trust/relations/{trust_id}/revocation-approval`의 표 응답을 본문 로직과 맞춰 `{trust_id, status, revocation_decision, revocation_decided_by, revocation_decided_at}`으로 명시했다.

## 9. 챗봇 의료 고지

챗봇 화면은 연결된 `guide_result_id`의 `guide_results.disclaimer`를 SSE 상태와 관계없이 항상 표시하도록 명시했다.

## 10. 처리 완료 초대 토큰

이미 수락·거절·취소된 초대 토큰을 다시 사용하면 `409 INVITATION_ALREADY_PROCESSED`를 반환하도록 추가했다.

## 11. 로그인 5회 실패 복구

5회 연속 실패 시 가입 당시 인증된 이메일 또는 연락처로 6자리 임시번호를 자동 전송한다. 임시번호 인증은 일반 로그인 권한이 아닌 `password_reset_token`만 발급하며 새 비밀번호 설정 완료 후 잠금과 실패 횟수를 초기화한다. `/auth/unlock/*` 대신 `/auth/temporary-code/resend`, `/auth/temporary-login`, `/auth/password-reset/confirm` 흐름으로 통일했다.
