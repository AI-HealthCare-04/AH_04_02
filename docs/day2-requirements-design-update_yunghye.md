# Day2 요구사항·설계 문서 변경 내역

작성자: 김영혜  
대상 문서: `요구사항_정의서_업데이트.xlsx`, `ERD.md`, `API명세서.md`

## 1. 변경 목적

복약관리 대상자의 안전한 복약 수행, 보호자·교육자의 공동 모니터링, 앱 사용 교육과 계정 보안을 요구사항 정의서부터 ERD와 API까지 동일한 ID와 필드명으로 연결하기 위해 문서를 보완했다.

## 2. 사용자·역할 변경

- 로그인 역할을 다음과 같이 확장했다.
  - 복약관리 대상자: `medication_subject`
  - 보호자: `guardian`
  - 요양보호사: `caregiver`
  - 생활지원사: `life_support_worker`
  - 사회복지사: `social_worker`
  - 관리자: `admin`
- 보호자·교육자는 승인 또는 배정된 복약관리 대상자의 정보에만 접근하도록 RBAC와 리소스 소유권 검사를 명시했다.
- `trust_relations.relation_type`에도 요양보호사·생활지원사·사회복지사를 반영했다.

## 3. 복약 가능 여부와 연결 권유

### REQ-007

- `third_party_needed`로 평가된 경우 복약관리 대상자와 승인된 보호자·교육자에게 복약 알림을 함께 전송하도록 확장했다.

### REQ-007a

- `third_party_needed`인데 승인된 보호자·교육자가 없으면 연결 권유 안내를 표시한다.
- 사용자가 안내를 닫으면 서버가 `dismissed_at`과 `dismissed_until`을 저장한다.
- 닫은 시점부터 30일 동안 같은 안내를 다시 표시하지 않는다.
- 사용자가 연결을 거부해도 서비스를 차단하지 않는다.

추가 API:

```http
GET  /medication-subjects/{subject_id}/care-level-notice
POST /medication-subjects/{subject_id}/care-level-notice/dismiss
```

추가 ERD:

- `care_level_notice_dismissals`

## 4. 복약 알림 세분화

기존 복약 알림 요구사항을 다음과 같이 세분화했다.

| 요구사항 | 내용 |
|---|---|
| REQ-026a | 복약 알림 일정 등록 |
| REQ-026b | 일정 조회·시간 변경·비활성화 |
| REQ-026c | 복약 알림·돌봄 알림·전체 푸시 수신 설정 |
| REQ-026d | 보호자·교육자 공동 알림 및 복약 완료 결과 공유 |

추가 API:

```http
GET   /users/me/notification-settings
PATCH /users/me/notification-settings
POST  /notifications/{notification_id}/acknowledge
```

알림 설정 필드:

```json
{
  "medication_reminder_enabled": true,
  "caregiver_alert_enabled": true,
  "push_enabled": true,
  "forced_by_care_level": false
}
```

- `third_party_needed`이면 최소 한 명의 승인된 보호자·교육자에게 안전 알림을 유지한다.
- 강제 알림을 해제하려는 요청은 `409 Conflict`로 처리한다.
- `forced_by_care_level`로 강제 적용 여부를 응답한다.

## 5. 알림 확인과 실제 복약 완료 분리

알림의 확인 버튼과 실제 복약 완료를 동일하게 처리하지 않도록 설계했다.

- `/notifications/{notification_id}/acknowledge`: 알림을 읽거나 확인했다는 의미
- `POST /medication-intakes`: 실제 복약 또는 복약 도움 수행을 기록

실제 수행 기록에는 다음 값을 저장한다.

- `status`
- `confirmed_by`
- `confirmed_at`
- `note`

보호자·교육자 중 한 명이 복약 완료를 기록하면 다른 승인된 수신자에게 `intake_confirmed` 알림을 전송해 중복 수행을 방지한다.

추가 ERD:

- `notification_settings`
- `notifications`
- `notification_deliveries`

## 6. 계정 잠금·해제

### REQ-039

- 로그인 5회 연속 실패 시 계정을 잠근다.
- 기본 잠금 시간은 30분이다.
- 로그인 응답은 `423 Locked`와 `locked_until`을 포함한다.
- 등록된 연락처의 인증코드 확인 또는 비밀번호 재설정 완료 시 즉시 잠금을 해제한다.
- 인증코드 요청과 확인 횟수를 제한한다.
- 계정 존재 여부 노출을 방지하기 위해 코드 요청 응답은 동일하게 반환한다.

추가 API:

```http
POST /auth/unlock/request
POST /auth/unlock/confirm
```

추가 필드:

- `users.failed_login_count`
- `users.locked_until`
- `users.last_failed_login_at`

## 7. 앱 사용 교육·추적관리

### REQ-040 교육 단계 자동 분류

| 기간 | 시스템 단계 | 화면 표시 | 지원 방식 |
|---|---|---|---|
| 시작일~29일 | `freshman` | 집중교육 | 앱 사용법 중심 교육 |
| 30~59일 | `junior` | 전화지원 | 스스로 앱을 사용하도록 전화 지원 |
| 60일 이후 | `senior` | 자립단계 | 자율 사용과 예외 상황 지원 |

### REQ-041 단계별 교육 강도

- 교육 단계에 따라 교육 강도와 집중 지원 대상을 구분한다.

### REQ-042 최대 2개월 추적관리

- 교육 시작일부터 최대 60일까지 교육 진행과 지원 이력을 집중 추적한다.
- 60일이 지나도 일반 복약관리 서비스는 계속 이용할 수 있다.

### REQ-043 교육자 배정·역할

- 요양보호사·생활지원사·사회복지사를 교육자로 배정할 수 있다.
- 앱 교육, 전화 지원, 방문 지원의 수행일과 메모를 기록한다.
- 방문요양 등 외부 사업의 대상 자격은 `service_program`, `eligibility_verified`로 별도 관리한다.
- 계정 역할 자체에는 연령 제한을 직접 적용하지 않는다.

추가 API:

```http
POST  /medication-subjects/{subject_id}/education-profile
GET   /medication-subjects/{subject_id}/education-profile
PATCH /medication-subjects/{subject_id}/education-profile
POST  /medication-subjects/{subject_id}/education-support-logs
GET   /medication-subjects/{subject_id}/education-support-logs
GET   /educators/me/medication-subjects
```

추가 ERD:

- `education_profiles`
- `education_support_logs`

## 8. 기존 문서 정합성 수정

- OCR 제공자를 EasyOCR로 통일했다.
- OCR 응답과 ERD에 `confidence`, `user_confirmed`를 반영했다.
- `confidence < 0.80`이면 사용자 확인 전 가이드를 확정하지 않도록 했다.
- `uploaded_for`를 필수값으로 정의했다.
- 본인 업로드는 `uploaded_by = uploaded_for`로 정의했다.
- 상태 등록 시 복약 가능 여부를 자동 재평가하도록 했다.
- 최신 평가 조회 기준을 `evaluated_at DESC, id DESC`로 명시했다.
- 의약품 성상·알약 이미지 인식 기능은 범위에서 제외했다.
- 사용자 표현을 `복약관리 대상자`로 통일했다.
- API 접수 P95 3초와 OCR 완료 후 가이드 생성 10초를 별도 기준으로 구분했다.

## 9. 생성·수정된 파일

- `요구사항_정의서_업데이트.xlsx`
- `API명세서.md`
- `ERD.md`
- `문서_일관성_검토표.md`
- `tools/generate_requirements.ps1`
- `README.md`
- `docs/architecture_dataflow.html`
- `docs/architecture_system.html`
- `docs/week1-tickets.md`

## 10. 검토 시 확인할 정책

- `third_party_needed` 안전 알림을 받을 최소 인원을 1명으로 유지할지
- 교육 단계 계산을 일수 기준으로 고정할지 달력 월 기준으로 계산할지
- 전화지원 주기와 담당 교육자 변경 절차
- 방문요양 등 외부 사업 자격 검증 주체와 갱신 주기
- 30일 연결 권유 비표시 기간이 적절한지
