# ERD 수정 검토 기록

이 문서는 `ERD_v2.md`에서 `ERD_v3.md`로 변경하며 반영한 데이터 모델 수정사항과 설계 판단을 기록한 변경 이력이다.

## 1. `trust_invitations` 분리 — 반영 완료

초대는 가입 전 사용자를 대상으로 할 수 있고, 승인된 관계와 생명주기가 다르므로 별도 테이블로 분리한다.

```text
trust_invitations
- id bigint PK
- medication_subject_id bigint FK -> users.id
- invited_phone string
- relation_type enum(guardian, caregiver, life_support_worker, social_worker)
- invite_token_hash string UK
- status enum(pending, accepted, rejected, expired, cancelled)
- expires_at datetime
- matched_user_id bigint FK -> users.id nullable
- accepted_at datetime nullable
- rejected_at datetime nullable
- created_by bigint FK -> users.id
- created_at datetime
- updated_at datetime
```

원문 토큰은 API 응답으로 한 번만 제공하고 DB에는 `invite_token_hash`만 저장한다. `matched_user_id`는 가입·로그인 후 전화번호가 확인됐을 때 채운다.

`trust_relations`는 승인된 실제 관계를 저장하도록 정리한다.

```text
trust_relations
- id bigint PK
- invitation_id bigint FK -> trust_invitations.id nullable
- medication_subject_id bigint FK -> users.id
- trustee_id bigint FK -> users.id NOT NULL
- relation_type enum(...)
- status enum(approved, revocation_pending, revoked)
- approved_by bigint FK -> users.id
- approved_at datetime
- revocation_requested_by bigint FK -> users.id nullable
- revocation_requested_at datetime nullable
- revocation_decided_by bigint FK -> users.id nullable
- revocation_decided_at datetime nullable
- revocation_decision enum(approved, rejected) nullable
- created_at datetime
- updated_at datetime
```

기존 `revocation_approved_by`는 반려까지 표현할 수 없으므로 `revocation_decided_by`와 `revocation_decision`으로 일반화한다. `approve:false`이면 관계 상태를 `approved`로 복귀시킨다.

## 2. 안전 알림 권고 계산값 — DB 컬럼 추가하지 않음

`active_safety_recipient_count`와 `should_recommend`는 최신 `care_level`, 승인 관계 수, 알림 설정을 이용해 대상자별로 계산하는 API 응답 필드다. `notification_settings`에 중복 저장하지 않는다.

`auth_refresh_tokens`에는 refresh token 해시, 만료시각, 폐기시각, 교체 토큰 ID를 저장해 순환 발급과 기존 토큰 폐기를 추적한다.

`auth_temporary_codes`에는 5회 실패 후 자동 전송하는 임시번호 해시, 전달 채널, 마스킹 대상, 만료·사용시각, 검증·재전송 횟수를 저장한다. 계정은 `users.locked_at`으로 잠금 시점을 기록하고 비밀번호 재설정 완료 후 초기화한다.

## 3. 알림 설정 우선순위 — 제약 규칙 추가

- 돌봄 알림은 일정별 `notify_guardian`, 수신자의 `caregiver_alert_enabled`, `push_enabled`가 모두 활성화된 경우 발송한다.
- 모든 사용자의 설정 변경을 허용한다.
- `third_party_needed`에서 수신 가능한 승인 관계자가 0명이면 최소 한 명 유지를 권고한다.
- 승인 관계 자체가 0명이면 REQ-007a 연결 권유 안내를 적용한다.

## 4. 탈퇴 데이터 — `deleted_at` 대신 생명주기 명확화

`users`에 다음 필드를 추가했다.

```text
withdrawal_requested_at datetime nullable
deactivated_at datetime nullable
scheduled_purge_at datetime nullable
```

실제 영구 삭제 후에는 사용자 행이 존재하지 않을 수 있으므로 `users.deleted_at`을 영구 삭제 완료 증빙으로 사용하지 않는다. 완료 증빙은 식별정보를 제거한 별도 `privacy_purge_audits` 테이블에 기록한다.

## 5. 가이드 캐시 — 반영 완료

`guide_results`에 다음 필드를 추가한다.

```text
cache_key string nullable
cache_expires_at datetime nullable
```

`cache_key`에는 진단명·약물 조합뿐 아니라 출처 데이터 버전을 포함한다. 출처가 변경되면 키가 달라져 기존 캐시가 자동으로 적중하지 않게 한다. 별도 강제 무효화 이력이 필요할 때만 `invalidated_at`을 추가한다.

## 6. 연결 권유 안내 — `assessment_id` 제거 권장

현재 정책은 평가 단건이 아니라 대상자별 30일 비표시다. 따라서 `care_level_notice_dismissals.assessment_id`와 해당 관계선을 제거한다.

유지 필드:

```text
id
medication_subject_id
dismissed_by
notice_type
dismissed_at
dismissed_until
```

표시 여부는 최신 케어레벨, 승인 관계 존재 여부, `dismissed_until`을 조합해 계산한다. 새 평가 생성만으로 비표시 기간을 초기화하지 않는다.

## 7. 교육 프로필 — 회차형 이력 구조로 변경 권장

재교육 가능성이 있으므로 `medication_subject_id FK,UK`에서 UK를 제거한다.

```text
education_profiles
- id bigint PK
- medication_subject_id bigint FK
- cycle_number int
- assigned_educator_id bigint FK nullable
- education_stage enum(freshman, junior, senior)
- education_started_at datetime
- tracking_ends_at datetime
- next_phone_support_at datetime nullable
- service_program string nullable
- eligibility_verified boolean
- status enum(active, paused, completed)
- is_current boolean
- restart_reason string nullable
- ended_at datetime nullable
- created_at datetime
- updated_at datetime
- UK(medication_subject_id, cycle_number)
```

대상자별 현재 회차는 최대 1개만 허용한다. 현재 회차 생성·변경 시 대상자 행을 `SELECT ... FOR UPDATE`로 잠근 하나의 애플리케이션 트랜잭션에서 기존 현재 회차를 검사하며 별도 DB unique 제약은 두지 않는다. `paused`는 현재 회차로 유지하고 `completed`만 과거 회차로 전환한다.

## 8. 조사 오타

ERD 핵심 규칙의 `지원인력가 없을 때만`을 `지원인력이 없을 때만`으로 수정한다.

`revocation_decision`은 `approved|rejected` enum의 nullable 컬럼으로 표기하고, API 필드명을 ERD 기준인 `invited_phone`, `revocation_decided_by`, `revocation_decided_at`, `restart_reason`으로 통일했다.

## 관계도 추가·삭제 요약

- 추가: `users ||--o{ trust_invitations : medication_subject_id`
- 추가: `users ||--o{ trust_invitations : matched_user_id`
- 추가: `trust_invitations ||--o| trust_relations : accepted_invitation`
- 삭제: `care_level_assessments ||--o{ care_level_notice_dismissals : assessment_id`
- 유지: `users ||--o{ education_profiles : medication_subject_id` — 단, 대상자당 여러 회차 허용

## 영구 삭제 감사 및 추적표 보완

- 실제 개인정보 삭제 완료를 비식별 상태로 증빙하는 `privacy_purge_audits`를 추가했다.
- 삭제된 사용자와 연결되는 FK나 원본 식별자는 저장하지 않고 `subject_reference_hash`, `purged_at`, `purge_status`를 기록한다.
- 요구사항 추적표에 `REQ-007 → notifications/notification_deliveries`, `REQ-032 → guide_results.disclaimer`를 추가했다.
