# 진료기록 기반 복약·생활습관 안내 시스템 ERD

> 기준: 요구사항 정의서 / API 명세서. 논리명은 설명용이며, 실제 DB·API 필드명은 모두 `snake_case`로 통일한다.

```mermaid
erDiagram
    users ||--o{ medication_subject_statuses : "medication_subject_id"
    users ||--o{ care_level_assessments : "medication_subject_id"
    users ||--o{ trust_relations : "medication_subject_id"
    users ||--o{ trust_relations : "trustee_id"
    users ||--o{ medical_records : "uploaded_by"
    users ||--o{ medical_records : "uploaded_for"
    users ||--o{ medication_schedules : "medication_subject_id"
    users ||--o{ medication_intake_logs : "confirmed_by"
    users ||--|| notification_settings : "user_id"
    users ||--o{ notification_deliveries : "recipient_id"
    users ||--o{ education_profiles : "medication_subject_id"
    users ||--o{ education_profiles : "assigned_educator_id"
    users ||--o{ education_support_logs : "educator_id"
    medication_subject_statuses ||--|| care_level_assessments : "assessed_from"
    care_level_assessments ||--o{ care_level_notice_dismissals : "assessment_id"
    medical_records ||--o{ extracted_medications : "contains"
    medical_records ||--o{ guide_results : "generates"
    extracted_medications ||--o{ medication_schedules : "scheduled"
    guide_results ||--o{ chat_messages : "context"
    medication_schedules ||--o{ medication_intake_logs : "records"
    medication_schedules ||--o{ notifications : "triggers"
    medication_intake_logs ||--o{ notifications : "completion_event"
    notifications ||--o{ notification_deliveries : "delivered_to"
    education_profiles ||--o{ education_support_logs : "tracks"

    users {
        bigint id PK
        string email UK "nullable"
        string phone UK "nullable"
        string password_hash
        string name
        enum role "medication_subject|guardian|caregiver|life_support_worker|social_worker|admin"
        enum status "active|withdrawal_pending|deleted"
        int failed_login_count
        datetime locked_until "nullable"
        datetime last_failed_login_at "nullable"
        datetime withdrawal_requested_at "nullable"
        datetime created_at
        datetime updated_at
    }
    medication_subject_statuses {
        bigint id PK
        bigint medication_subject_id FK
        bigint updated_by FK
        enum cognitive_level "normal|mild|severe"
        enum mobility_level "normal|mild|severe"
        enum vision_level "normal|mild|severe"
        boolean medication_awareness
        boolean medication_willingness
        datetime created_at
    }
    care_level_assessments {
        bigint id PK
        bigint medication_subject_id FK
        bigint status_id FK
        enum care_level "independent|guardian_check|third_party_needed"
        string reason
        datetime evaluated_at
    }
    care_level_notice_dismissals {
        bigint id PK
        bigint medication_subject_id FK
        bigint assessment_id FK
        bigint dismissed_by FK
        enum notice_type "guardian_connection_recommendation"
        datetime dismissed_at
        datetime dismissed_until
    }
    trust_relations {
        bigint id PK
        bigint medication_subject_id FK
        bigint trustee_id FK
        enum relation_type "guardian|caregiver|life_support_worker|social_worker"
        enum status "pending|approved|revocation_pending|revoked|rejected"
        bigint revocation_approved_by FK "nullable"
        datetime created_at
        datetime updated_at
    }
    medical_records {
        bigint id PK
        bigint uploaded_by FK
        bigint uploaded_for FK "NOT NULL; self upload이면 uploaded_by와 동일"
        string image_url
        enum status "processing|review_required|done|failed"
        text ocr_raw_text
        string ocr_provider "easyocr"
        datetime uploaded_at
        datetime completed_at "nullable"
    }
    extracted_medications {
        bigint id PK
        bigint medical_record_id FK
        string drug_name
        string dosage
        string frequency
        string diagnosis
        string drug_class
        decimal confidence "0.0000~1.0000"
        boolean user_confirmed
        datetime created_at
    }
    guide_results {
        bigint id PK
        bigint medical_record_id FK
        json medication_guide
        json lifestyle_guide
        json source_refs
        boolean cached
        string disclaimer
        datetime generated_at
    }
    chat_messages {
        bigint id PK
        bigint guide_result_id FK
        bigint user_id FK
        enum role "user|assistant"
        text message
        datetime created_at
    }
    medication_schedules {
        bigint id PK
        bigint medication_subject_id FK
        bigint extracted_medication_id FK
        time scheduled_time
        string timezone "Asia/Seoul"
        boolean notify_guardian
        boolean active
        datetime created_at
    }
    medication_intake_logs {
        bigint id PK
        bigint schedule_id FK
        bigint confirmed_by FK
        enum status "taken|missed|skipped"
        datetime scheduled_at
        datetime confirmed_at "nullable"
        string note "nullable"
    }
    notification_settings {
        bigint user_id PK,FK
        boolean medication_reminder_enabled
        boolean caregiver_alert_enabled
        boolean push_enabled
        datetime updated_at
    }
    notifications {
        bigint id PK
        bigint medication_subject_id FK
        bigint schedule_id FK "nullable"
        bigint intake_id FK "nullable"
        enum type "medication_reminder|care_alert|intake_confirmed"
        json payload
        datetime created_at
    }
    notification_deliveries {
        bigint id PK
        bigint notification_id FK
        bigint recipient_id FK
        datetime delivered_at "nullable"
        datetime read_at "nullable"
        datetime acknowledged_at "nullable"
    }
    education_profiles {
        bigint id PK
        bigint medication_subject_id FK,UK
        bigint assigned_educator_id FK "nullable"
        enum education_stage "freshman|junior|senior"
        datetime education_started_at
        datetime tracking_ends_at
        datetime next_phone_support_at "nullable"
        string service_program "nullable"
        boolean eligibility_verified
        enum status "active|completed|paused"
        datetime updated_at
    }
    education_support_logs {
        bigint id PK
        bigint education_profile_id FK
        bigint educator_id FK
        enum support_type "in_app|phone|visit"
        datetime supported_at
        string note "nullable"
    }
```

## 핵심 제약과 조회 규칙

- `medical_records.uploaded_for`는 항상 값이 있다. 본인 업로드는 `uploaded_by = uploaded_for`, 대리 업로드는 두 값이 다르다.
- 상태 등록과 평가는 한 트랜잭션이다. `medication_subject_statuses` 생성 직후 `care_level_assessments`를 생성하며, 최신 평가는 `evaluated_at DESC, id DESC`로 1건 조회한다.
- `extracted_medications.confidence < 0.80`이면 기록 상태를 `review_required`로 두고 사용자 확인 전 가이드를 확정하지 않는다.
- `third_party_needed` 상태에서 승인된 보호자·요양보호사 연결은 단독 즉시 해제하지 않고 `revocation_pending`과 제3자 승인 절차를 거친다.
- `third_party_needed`이면서 승인된 보호자·교육자가 없을 때만 연결 권유를 표시한다. `care_level_notice_dismissals.dismissed_until`까지 숨기며 서비스 자체는 차단하지 않는다.
- 가이드 재생성 시 기존 결과를 보존하고 새 `guide_results` 레코드를 생성하며, 최신 결과는 `generated_at DESC, id DESC`로 조회한다.
- 복약 완료는 `medication_intake_logs`, 알림 읽음·확인은 `notification_deliveries`에 분리해 저장한다. 한 사람이 복약 완료를 기록하면 다른 승인 수신자에게 `intake_confirmed` 알림을 생성한다.
- `third_party_needed`에서는 최소 한 명의 승인된 보호자·교육자에게 돌봄 알림이 유지되어야 하며, 이 규칙은 `notification_settings`보다 우선한다.
- 교육 단계는 `education_started_at` 기준 0~29일 `freshman`, 30~59일 `junior`, 60일 이후 `senior`로 계산한다. `tracking_ends_at`은 시작일로부터 60일이다.

## 요구사항 추적

| 요구사항 | 테이블/필드 | API |
|---|---|---|
| REQ-005~006 | `medication_subject_statuses`, `care_level_assessments.evaluated_at` | `POST /medication-subjects/{subject_id}/status`, `GET /medication-subjects/{subject_id}/care-level` |
| REQ-008~011 | `medical_records`, `extracted_medications.confidence` | `/medical-records*` |
| REQ-012~020 | `guide_results` | `GET /medical-records/{record_id}/guide*` |
| REQ-021~022 | `chat_messages.role`, `created_at` | `/chat*` |
| REQ-023~024 | `uploaded_by`, `uploaded_for`, `uploaded_at` | `GET /medical-records` |
| REQ-007a | `care_level_notice_dismissals.dismissed_until` | `/medication-subjects/{subject_id}/care-level-notice*` |
| REQ-026a~026d, REQ-036~038 | `medication_schedules`, `medication_intake_logs`, `notification_settings`, `notifications`, `notification_deliveries` | `/medication-schedules*`, `/medication-intakes*`, `/users/me/notification-settings`, `/notifications*`, `/monitoring*` |
| REQ-035 | `users.status`, `withdrawal_requested_at` | `DELETE /users/me`, `POST /users/me/withdrawal/cancel` |
| REQ-039 | `users.failed_login_count`, `locked_until` | `/auth/unlock/request`, `/auth/unlock/confirm` |
| REQ-040~043 | `education_profiles`, `education_support_logs`, `users.role` | `/medication-subjects/{subject_id}/education-*`, `/educators/me/medication-subjects` |
