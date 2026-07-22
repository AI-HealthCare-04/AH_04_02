# 진료기록 기반 복약·생활습관 안내 시스템 ERD

> 기준: `backend/models.py`(SQLModel) 실제 구현 + `backend/alembic/versions/` 전체 마이그레이션 체인(head: `c3a413343157`, `uv run alembic heads`로 2026-07-21 재확인 — 단일 head, 분기 없음) / **SQLite**(`backend/app.db`). 논리명은 설명용이며, 실제 DB·API 필드명은 모두 `snake_case`로 통일한다.
>
> **[v9 정정]** 이전 초안은 head를 `66c32a201ba5`로 잘못 표기했다 — 실제로는 그 뒤로 `bfc3d4e49682`(medication_records: patient_medication_id nullable + confirmed_by 컬럼 추가), `849bd15b19a5`(medication_logs→medication_records 데이터 이관), `c3a413343157`(invitations.patient_id nullable, PR #62) 3개 마이그레이션이 더 있다. 이 3개가 만든 스키마 결과(아래 mermaid의 `medication_records`/`invitations` 정의, "이원화 정리" 절)는 이미 반영돼 있었으므로 실제 스키마 서술에는 오류가 없었다 — head 해시 표기만 정정한다.
> 버전: v10 (2026-07-22). v9 대비 변경 내역은 `docs/revision_logs/ERD/ERD_v9_to_v10_revision_log.md` 참고.
>
> **v8(2026-07-13) 이후 PR #29 후속 보안 리뷰, PR #56/#59/#60(REQ-004/007a/020/047), PR #61(챗봇 버그 수정), PR #62(보호자→환자 초대 REQ-058 + REQ-037 Phase2(medication_records 승격) + 복약/RAG 다수 수정)가 순차 병합되며 테이블이 12개→19개로 늘었다.** 이번 v9은 v8에 diff를 얹는 방식이 아니라 `backend/models.py`(517줄, 19개 SQLModel 테이블)를 다시 전수 확인해 작성했다.

```mermaid
erDiagram
    caregivers ||--o{ caregiver_patients : "caregiver_id"
    patients ||--o{ caregiver_patients : "patient_id"
    patients ||--o{ medical_records : "patient_id"
    caregivers ||--o{ medical_records : "uploaded_by_caregiver_id (nullable)"
    medical_records ||--o{ ocr_results : "record_id"
    medical_records ||--o{ guide_results : "record_id"
    medical_records ||--o{ medication_schedules : "record_id (nullable)"
    patients ||--o{ medication_schedules : "patient_id"
    patient_medications ||--o{ medication_schedules : "patient_medication_id (nullable)"
    medication_schedules ||--o{ medication_logs : "schedule_id"
    caregivers ||--o{ medication_logs : "confirmed_by_caregiver_id (nullable)"
    medication_schedules ||--o{ notification_logs : "schedule_id"
    patients ||--o{ notification_logs : "patient_id"
    patients ||--o{ patient_medications : "patient_id"
    medical_records ||--o{ patient_medications : "prescription_id (nullable)"
    patient_medications ||--o{ medication_records : "patient_medication_id (nullable)"
    medication_schedules ||--o{ medication_records : "schedule_id (nullable)"
    caregivers ||--o{ medication_records : "confirmed_by_caregiver_id (nullable)"
    patients ||--o{ care_level_assessments : "patient_id"
    patients ||--o{ invitations : "patient_id (nullable)"
    caregivers ||--o{ invitations : "inviter_caregiver_id (nullable)"
    patients ||--|| notification_settings : "patient_id (PK 겸 FK, 1:1)"
    patients ||--o{ chat_messages : "patient_id"

    patients {
        int id PK
        string name_encrypted "Fernet 암호화, .name 프로퍼티로 투명 암복호화"
        string note "nullable, 자유 텍스트(예: 치매 초기)"
        string phone_encrypted "nullable, Fernet 암호화"
        string phone_hash "nullable, indexed, HMAC-SHA256 (조회 전용, 복호화 불가)"
        string email "nullable, unique"
        string birth_date "nullable, 자유 텍스트"
        string hashed_password "nullable, bcrypt"
        bool push_enabled "default true"
        bool sms_enabled "default false"
        bool email_opt_in "default false"
        datetime created_at
        int failed_login_attempts "default 0, REQ-039"
        datetime locked_at "nullable, REQ-039(5회 실패 시 기록, 30분 후 자동 해제)"
        datetime deactivated_at "nullable, REQ-035(탈퇴 요청 시각)"
        datetime deletion_scheduled_at "nullable, REQ-035(탈퇴+30일)"
        string breakfast_time "nullable, 자가진단 식사시간(HH:MM 자유 텍스트)"
        bool breakfast_regular "nullable, 아침 식사 규칙적 여부"
        string lunch_time "nullable"
        bool lunch_regular "nullable"
        string dinner_time "nullable"
        bool dinner_regular "nullable"
        datetime caregiver_alert_dismissed_at "nullable, REQ-007a(연결 권유 안내 닫음, 30일 재표시 억제)"
    }
    caregivers {
        int id PK
        string name_encrypted "Fernet 암호화, .name 프로퍼티"
        string email "nullable, unique, indexed"
        string hashed_password "nullable, bcrypt"
        string relation_type "guardian/caregiver/life_support_worker/social_worker/organization"
        string phone_encrypted "nullable, Fernet 암호화"
        string phone_hash "nullable, indexed, HMAC-SHA256"
        string birth_date "nullable"
        bool push_enabled "default true"
        bool sms_enabled "default false"
        bool email_opt_in "default false"
        string org_name "nullable, relation_type=organization일 때만"
        string org_type "nullable, 프론트(SignUp.tsx)는 요양원/정부기관/협회/보건소/기타 5개 값만 선택 가능"
        string business_reg_no "nullable"
        string manager_name "nullable, 암호화 대상 아님(계정 본인 PII 아님)"
        string manager_phone "nullable, 암호화 대상 아님"
        datetime created_at
        int failed_login_attempts "default 0, REQ-039"
        datetime locked_at "nullable"
        datetime deactivated_at "nullable, REQ-035"
        datetime deletion_scheduled_at "nullable, REQ-035"
    }
    caregiver_patients {
        int id PK
        int caregiver_id FK
        int patient_id FK
        datetime created_at
        string status "default active — active/revocation_pending/revoked (REQ-004)"
        datetime revoked_at "nullable"
        int revocation_requested_by "nullable, FK 없음(caregivers.id 또는 patients.id 중 하나, 앱 레벨 검증)"
        string requested_by_role "nullable, 'caregiver'|'patient' — 자기승인 방지 가드용"
    }
    password_reset_codes {
        int id PK
        string subject_type "patient/caregiver"
        int subject_id "indexed, FK 없음(다형 참조)"
        string code_hash "indexed, HMAC 해시(원문 미저장)"
        datetime expires_at "발급+10분"
        datetime used_at "nullable"
        int attempts "default 0, 5회 초과 시 코드 무효화"
        datetime created_at
    }
    privacy_purge_audits {
        int id PK
        string subject_type "patient/caregiver"
        int subject_id "indexed"
        datetime requested_at
        datetime deactivated_at
        datetime scheduled_purge_at "requested_at + 30일"
        string status "default pending — pending/completed/cancelled"
        datetime completed_at "nullable"
    }
    medical_records {
        int id PK
        int patient_id FK
        string image_path
        string status "processing/review_required/completed/failed"
        string raw_text "nullable, TEXT"
        string failure_reason "nullable"
        datetime created_at
        int uploaded_by_caregiver_id FK "nullable, 대리 업로드일 때만"
        datetime deleted_at "nullable, 소프트 삭제(등록내역 삭제)"
    }
    ocr_results {
        int id PK
        int record_id FK
        string drug_name
        string drug_code "default ''"
        string dosage "default ''"
        string frequency "default ''"
        string total_days "default '', 총 투약일수"
        string diagnosis "default ''"
        string drug_class "default ''"
        float confidence "default 0.0"
        bool review_required "default false"
        bool user_confirmed "default false"
        string matched_drug_name "default '', drug_matcher 결과"
        float match_score "default 0.0"
        bool needs_review "default false, match_score<0.7"
    }
    guide_results {
        int id PK
        int record_id FK
        string medication_guide "TEXT, JSON 문자열"
        string lifestyle_guide "TEXT, JSON 문자열"
        string source_refs "default '[]', TEXT, JSON 문자열"
        datetime created_at
    }
    medication_schedules {
        int id PK
        int patient_id FK
        string drug_name
        string time_slot "08:00 같은 실제 시각 문자열"
        string dose_timing "nullable, 공복/식전/식후 등"
        bool caregiver_alert "default true"
        string memo "nullable"
        bool active "default true"
        datetime created_at
        int patient_medication_id FK "nullable, indexed — OCR 자동생성 일정은 PatientMedication이 없음"
        string meal_relation "nullable"
        string instructions "nullable"
        string timezone "nullable"
        string days_of_week "nullable, JSON 배열 문자열"
        int record_id FK "nullable, indexed — 이 일정을 만든 처방전(등록내역 삭제 시 cascade 비활성화용)"
    }
    medication_logs {
        int id PK
        int schedule_id FK
        string status "default taken — taken/skipped만 존재(missed 없음)"
        datetime checked_at
        string note "nullable"
        string confirmed_by_type "default patient — patient/caregiver"
        int confirmed_by_caregiver_id FK "nullable"
    }
    notification_logs {
        int id PK
        int schedule_id FK "indexed"
        int patient_id FK "indexed"
        string due_date "indexed, YYYY-MM-DD"
        string time_slot
        string kind "default reminder — reminder/missed"
        string status "default pending — pending/sent/suppressed/failed"
        string channels "default '[]', JSON 배열"
        datetime fired_at
        datetime acknowledged_at "nullable"
    }
    patient_medications {
        int id PK
        int patient_id FK "indexed"
        int drug_id "nullable, indexed, FK 없음(마스터 약물 테이블 아직 없음)"
        string item_seq "nullable, indexed"
        string product_code "nullable"
        string medication_name "필수"
        string manufacturer_name "nullable"
        string dosage_amount "nullable"
        string dosage_unit "nullable"
        int frequency_per_day "nullable"
        string administration_route "nullable"
        string start_date "nullable"
        string end_date "nullable"
        int prescription_id FK "nullable, medical_records.id"
        string source_type "default manual — manual/prescription_ocr/pill_image/api_search"
        string source_raw_text "nullable"
        string verification_status "default unverified — unverified/matched/user_confirmed/pharmacist_confirmed"
        bool is_active "default true"
        datetime created_at
        datetime updated_at
        datetime deleted_at "nullable, 소프트 삭제"
    }
    medication_records {
        int id PK
        int patient_medication_id FK "nullable — OCR 기반 스케줄은 PatientMedication이 없음"
        int schedule_id FK "nullable"
        datetime scheduled_at "nullable"
        datetime taken_at "nullable, 실제 복용 시간"
        string status "default scheduled — scheduled/taken/missed/skipped/duplicate_suspected"
        string verification_method "default self_report — self_report/caregiver/photo/device"
        string evidence_image_url "nullable"
        string memo "nullable"
        string confirmed_by_type "nullable, patient/caregiver — medication_logs와 동일 필드명"
        int confirmed_by_caregiver_id FK "nullable"
        datetime created_at
        datetime updated_at
    }
    care_level_assessments {
        int id PK
        int patient_id FK
        string cognitive_level "normal/mild/severe, default normal"
        string mobility_level "default normal"
        string vision_level "default normal"
        bool medication_awareness "default true"
        bool medication_willingness "default true"
        string care_level "independent/guardian_check/third_party_needed, default independent"
        string reason "default ''"
        datetime evaluated_at
    }
    invitations {
        int id PK
        int patient_id FK "nullable — 보호자→환자 초대(relation_type=patient)는 수락 전까지 환자 계정 자체가 없음"
        int inviter_caregiver_id FK "nullable"
        string relation_type "default guardian — guardian/caregiver/life_support_worker/social_worker/patient"
        string invited_phone_encrypted "nullable, Fernet 암호화(v8까지는 평문이었으나 2026-07-15 보안 리뷰로 암호화 전환)"
        string token_hash "unique, indexed — v8까지는 원문 token이었으나 2026-07-15 보안 리뷰로 해시 전환"
        string status "pending/accepted/rejected/expired/cancelled"
        datetime created_at
        datetime accepted_at "nullable"
        datetime expires_at "nullable — v8까지 없었음, 2026-07-15 추가(발급+7일)"
    }
    refresh_tokens {
        string jti PK "JWT ID 자체가 PK(자동증가 id 없음)"
        int subject_id
        string role
        bool revoked "default false"
        datetime expires_at
        datetime created_at
    }
    notification_settings {
        int patient_id PK,FK "1:1, patients와 동일 PK 공유"
        bool medication_reminder_enabled "default true"
        bool care_alert_enabled "default true"
        bool all_push_enabled "default true"
        string chatbot_name "default '약콩이'"
        datetime updated_at
    }
    chat_messages {
        int id PK
        int patient_id FK
        string question_id "고정 질문 식별자(q1/q2/q3, 동적 질문 dyn:*) 또는 freeform"
        string question_text
        string answer_text
        datetime created_at
    }
    guide_cache {
        int id PK
        string cache_key "unique, indexed — SHA-256(sorted 진단명 + sorted 약물조합 + data_version)"
        string diagnosis "nullable"
        string drug_names "default '[]', TEXT, JSON 배열"
        string data_version "GUIDE_DATA_VERSION 환경변수, 기본 'v1.0'"
        string guide_result "TEXT, medication_guide/lifestyle_guide/source_refs 튜플의 JSON 직렬화"
        datetime created_at
        datetime expires_at "created_at + GUIDE_CACHE_TTL_DAYS(기본 7일)"
    }
```

## v9 → v10 스키마·관계 의미 변경 요약

| 구분 | 내용 |
|---|---|
| 신규 테이블 | 없음 — v10은 새 테이블 추가보다 v9에서 누락된 실제 라우터/상태 의미를 문서화하는 개정 |
| `invitations.status` | `cancelled` 상태를 문서화 — `DELETE /invitations/{invitation_id}` 호출 시 대기중 초대를 물리 삭제하지 않고 취소 상태로 전환 |
| `patient_medications` | v9에 스키마는 이미 있었지만 API명세서 범위 밖이었음 — v10에서 `/patients/{patient_id}/medications*` API와 연결해 추적성 보강 |
| 처방전 삭제 동기화 | `medical_records.deleted_at` 기록 시 연결된 `medication_schedules`와 `patient_medications`를 애플리케이션 레벨에서 함께 비활성화/soft delete |

## v8 → v9 스키마 변경 요약

| 구분 | 내용 |
|---|---|
| 신규 테이블(7개) | `password_reset_codes`, `privacy_purge_audits`, `notification_logs`, `patient_medications`, `medication_records`, `refresh_tokens`, `guide_cache` |
| 필드 추가 — `patients` | `failed_login_attempts`, `locked_at`, `deactivated_at`, `deletion_scheduled_at`(REQ-039/035), `breakfast_time`/`breakfast_regular`/`lunch_time`/`lunch_regular`/`dinner_time`/`dinner_regular`(자가진단 식사시간), `caregiver_alert_dismissed_at`(REQ-007a) |
| 필드 추가 — `caregivers` | `failed_login_attempts`, `locked_at`, `deactivated_at`, `deletion_scheduled_at` (patients와 동일) |
| 필드 추가 — `caregiver_patients` | `status`, `revoked_at`, `revocation_requested_by`, `requested_by_role` (REQ-004 해제 승인 워크플로) |
| 필드 추가 — `medical_records` | `deleted_at` (등록내역 소프트 삭제) |
| 필드 추가 — `ocr_results` | `total_days` |
| 필드 추가 — `medication_schedules` | `patient_medication_id`, `meal_relation`, `instructions`, `timezone`, `days_of_week`, `record_id` |
| 필드 변경 — `invitations` | `token` → `token_hash`(해시 전환), `invited_phone`(평문) → `invited_phone_encrypted`(암호화), `expires_at` 신규 추가, `patient_id` **nullable로 전환**(보호자→환자 초대, REQ-058) |
| 임시로 있다가 제거된 필드 | `patients.needs_caregiver_alert`(boolean) — 마이그레이션 13에서 추가, 14에서 `caregiver_alert_dismissed_at`(datetime)으로 즉시 대체되어 현재 스키마엔 없음. 과거 이력 참고용으로만 기록. |

## 핵심 제약과 조회 규칙 (v9, 실제 구현 기준)

- `patients`/`caregivers`의 `name`/`phone`은 저장은 암호화(`name_encrypted`/`phone_encrypted`)로, 조회는 `.name`/`.phone` 파이썬 프로퍼티가 투명하게 복호화한다 — 생성자 kwarg로는 못 받고(`Patient(**kwargs)` 후 `patient.name = ...` 2단계 생성 필수), 응답 시엔 항상 평문으로 나간다.
- `phone_hash`는 정규화한 전화번호의 HMAC-SHA256이며 로그인 시 `WHERE phone_hash = ?` 조회 전용이다.
- `caregivers.manager_name`/`manager_phone`은 여전히 암호화 대상이 아니다(계정 본인 PII 아님이라는 이유, v8에서 이미 지적됨, 변경 없음).
- **[v9 반영] `invitations.invited_phone`이 이제 암호화된다.** v8 시점엔 평문 저장·응답이 PII 정책 사각지대였으나, 2026-07-15 보안 리뷰(REQ-030/002)에서 `invited_phone_encrypted`로 전환했다. `invitations` 목록 조회 응답(`GET /patients/{patient_id}/invitations`)에서도 이제 복호화된 값만 노출되고, **`token`도 더 이상 원문으로 저장·응답되지 않는다**(`token_hash`만 저장, 발급 시점에 한 번만 평문을 응답하고 이후엔 절대 복원 불가) — v8에서 지적됐던 "보안 주의" 2건이 모두 해소됐다.
- **[v9 신규, 정정] 보호자→환자 초대(REQ-058, 이전 초안은 REQ-037로 오기재 — REQ-037은 복약 여부 기록을 가리키는 별개 번호이며 요구사항_정의서_v9에 REQ-058을 신설해 정정)**: `invitations.relation_type="patient"`이면 초대 생성 시점엔 실제 환자 계정이 없어 `patient_id`가 `NULL`이다. 수락(`accept_invitation`) 시 `_register_patient()`(회원가입과 동일 로직 재사용)로 실제 로그인 가능한 `Patient` 행을 새로 만들고 그 `id`를 `invitations.patient_id`에 채운 뒤 `caregiver_patients` 연결을 생성한다. 기존 4-role(환자→보호자류) 초대 흐름은 변경 없이 그대로 동작한다.
- `caregiver_patients`는 다대다 연결이다. `POST /monitoring/caregivers/{cid}/patients/{pid}`(직접 연결)는 그 `patient_id`에 기존 연결이 하나도 없을 때만 허용한다(방금 만든 환자의 최초 연결 전용) — 이미 다른 보호자가 연결된 환자에 추가로 연결하려면 반드시 `invitations`의 토큰 기반 수락을 거쳐야 한다(v8부터 동일, 변경 없음).
- **[v9 신규] 돌봄관계 해제 승인 워크플로(REQ-004, PR #56)**: `caregiver_patients.status`가 `active`일 때 `DELETE /trust/relations/{trust_id}`를 호출하면, 최신 `care_level_assessments.care_level`이 `independent`/`guardian_check`면 즉시 `revoked`, `third_party_needed`면 `revocation_pending`으로 전환하고 `revocation_requested_by`/`requested_by_role`을 기록한다. `POST .../revocation-approval`로 다른 관계자가 승인(`revoked`)·거부(`active`로 복귀 — v7 설계의 "approved" 상태는 실제로 존재하지 않으며 그냥 `active`로 되돌아간다)할 수 있고, 요청자 본인은 role과 무관하게 자기 자신의 요청을 승인할 수 없다(자기승인 방지 가드).
- **[v9 신규] 보호자 연결 권유 억제(REQ-007a, PR #56)**: 활성 연결이 0명으로 떨어지면 `should_alert_now`가 true가 되어 연결 권유 안내를 표시한다. 사용자가 안내를 닫으면 `patients.caregiver_alert_dismissed_at`이 갱신되고, 이후 30일간(`dismissed_at + 30일`) 같은 환자에게는 이 안내가 다시 표시되지 않는다.
- `ocr_results.confidence`와 무관하게 `medical_records.status`는 항상 `review_required`로 시작한다. 보호자가 `POST /records/{id}/confirm`으로 확정해야 `completed`로 전환되고 그 시점에 `guide_results`가 생성된다(v8과 동일, 변경 없음).
- **[v9 신규] 가이드 캐싱(REQ-020, PR #60)**: `guide_cache.cache_key`(진단명+정규화된 약물조합+`GUIDE_DATA_VERSION` 기반 SHA-256)로 조회해 `expires_at`(기본 발급+7일) 이전이면 캐시를 그대로 재사용하고 LLM을 호출하지 않는다. `RAG_PROVIDER≠real`(stub 모드)일 때는 가짜 데이터가 캐시를 오염시키지 않도록 캐시 저장 자체를 하지 않는다.
- `guide_results`에는 여전히 `disclaimer` 컬럼이 없다. RAG 파이프라인(`rag/rag_chain.py`)의 `GuideResponse`는 `disclaimer` 필드를 생성하지만 `backend/routers/rag_router.py`가 이를 추출하지 않아 API 응답·DB 저장 어디에도 남지 않는다 — 실제 고지 문구는 프론트엔드(`Result.tsx`/`Dashboard.tsx`/`Processing.tsx`) 하드코딩이다(v8과 동일한 상태, REQ-032는 "부분"으로 유지).
- **[v9 신규] 로그인 잠금·비밀번호 재설정(REQ-039)**: `patients`/`caregivers` 양쪽에 `failed_login_attempts`/`locked_at`이 추가됐다. 5회 연속 로그인 실패 시 `locked_at`이 기록되고, `password_reset_codes`(HMAC 해시로 코드 저장, 10분 만료, 5회 시도 제한)를 통해 인증 후 새 비밀번호로 로그인하면 잠금·실패횟수가 초기화된다. 잠금 후 30분이 지나면 코드 없이도 자동 잠금 해제된다.
- **[v9 신규] 회원 탈퇴(REQ-035)**: `deactivated_at`/`deletion_scheduled_at`(탈퇴+30일)이 채워지고, `privacy_purge_audits`에 감사 레코드(`pending`)가 남는다. 30일 이내 `deactivated_at`/`deletion_scheduled_at`을 지우고 감사 레코드를 `cancelled`로 바꾸는 취소가 가능하다. **[v9 정정] 30일 후 영구 삭제 배치(purge)는 `backend/scripts/purge_expired_accounts.py`로 이미 구현·테스트돼 있다**(이전 v9 초안이 "실행 로직 확인 못함"이라 잘못 적었던 항목, 2026-07-21 재조사로 정정) — 단 서버 프로세스가 이 스크립트를 자동 트리거하지는 않으므로 수동 실행 또는 별도 cron 등록이 전제다.
- **[v9 신규] 자가진단 식사시간(회원가입 온보딩)**: `patients.breakfast_time`/`breakfast_regular`/`lunch_time`/`lunch_regular`/`dinner_time`/`dinner_regular` 6개 필드가 존재한다. 회원가입 직후 온보딩 화면에서 입력받으며, 저장은 되지만 **복약 가이드·생활습관 안내 생성 로직(`rag/rag_chain.py`)에서 이 값을 실제로 참조하는 코드는 확인되지 않았다** — "입력만 되고 활용은 안 되는" 상태로 REQ-051(신규, 요구사항_정의서 참고)에 "부분 구현"으로 명시한다.
- **[v9 신규] `medication_logs` vs `medication_records` 이원화 정리(REQ-037, PR #62)**: v8까지는 `medication_logs`(실사용, `taken`/`skipped`만)와 `medication_records`(프론트 어디서도 호출하지 않는 죽은 코드, `missed` 포함 5개 상태)가 공존했다. PR #62에서 `medication_records`를 유일한 실사용 테이블로 승격하고 과거 `medication_logs` 데이터를 이관했다 — 단 `medication_logs` 테이블 자체는 하위호환·롤백 안전을 위해 이번 버전에서 DROP하지 않고 남아 있다(1스프린트 관찰 후 별도 정리 예정). **현재 실제 체크인 응답 흐름은 `medication_records.status`(`scheduled`/`taken`/`missed`/`skipped`/`duplicate_suspected`) 기준이다.**
- `notification_settings.patient_id`는 PK이자 FK다(1:1). 설정을 조회했는데 행이 없으면 저장 없이 기본값 객체만 반환한다(v8과 동일).
- **[v10 신규] 대기중 초대 삭제**는 행 삭제가 아니라 `invitations.status="cancelled"`로 상태만 바꾼다. 이미 전달된 초대 링크가 뒤늦게 수락되는 것을 막기 위한 설계다.
- **[v10 신규] 처방전 등록내역 삭제**(`medical_records.deleted_at`) 시 `MedicationSchedule.record_id`로 연결된 일정뿐 아니라 `PatientMedication.prescription_id`로 연결된 내약도 soft delete하고, 해당 내약 기반 일정도 비활성화한다. DB FK cascade가 아니라 애플리케이션 레벨 동기화 규칙이다.
- `chat_messages.question_id`는 고정 질문(`q1`/`q2`/`q3`)뿐 아니라 환자가 등록한 약 이름 기반 동적 질문(`dyn:*`)과 자유 텍스트("freeform")도 구분하는 식별자다(v8 이후 동적 질문 기능 추가).

## 요구사항 추적 (v9, 실제 구현 기준 — v8 대비 정정 항목 굵게 표시)

| 요구사항 | 테이블/필드 | API | 구현 | 비고 |
|---|---|---|---|---|
| REQ-001 | `caregivers`/`patients` | `POST /auth/login`, `POST /auth/token/refresh` | 완료 | 회원가입은 `/monitoring/patients`·`/monitoring/caregivers`가 겸함(`POST /auth/signup`은 2026-07-14 중복 코드로 제거됨) |
| REQ-002~004 | `invitations`, `caregiver_patients` | `/invitations*`, `/monitoring/caregivers/{cid}/patients/{pid}`, `/trust/relations/*` | **완료로 정정(v8: 부분)** | REQ-004 해제 승인 워크플로(PR #56)로 `revocation_pending`/승인·거부/자기승인 방지까지 구현 완료 |
| REQ-005~007 | `care_level_assessments` | `POST /assessments`, `GET /assessments/latest` | **보류로 정정(v8: 완료)** — API 자체는 정상 동작하나 2026-07-17 회의에서 목적(제3자 도움 필요 판단) 자체를 폐기, 입력 화면 자체가 없어 실사용에서 항상 비어있음 | 2026-07-17 회의 결정, 요구사항_정의서_v9 참고 |
| REQ-007a | `patients.caregiver_alert_dismissed_at` | `POST /trust/relations/{id}/dismiss-alert` | **완료로 정정(v8: 미구현)** | PR #56 |
| REQ-008~011 | `medical_records`, `ocr_results` | `/records*`, `/ocr/*` | 완료 | REQ-009(OCR엔진 EasyOCR→CLOVA)·REQ-011(임계값 정책) 서술은 요구사항_정의서에서 별도 정정 필요(아래 참고) |
| REQ-012~020 | `guide_results`, `guide_cache` | `POST /records/{id}/confirm`(가이드 생성 포함) | **REQ-020 완료로 정정(v8: 미구현)** | PR #60, TTS·재생성 전용 API는 여전히 미구현 |
| REQ-021~022 | `chat_messages` | `/chat/*` | 완료 | `POST /chat/ask/stream`으로 챗봇 답변 SSE 스트리밍 지원. RAG 진행률 전용 SSE는 없음 |
| REQ-023~024 | `medical_records.uploaded_by_caregiver_id` | `GET /records` | 완료 | |
| REQ-026a | `medication_schedules`, `notification_logs` | `/monitoring/schedules*` | 부분 | 60초 주기 스케줄러 실체 확인됨, 실 발송은 이메일만(SMS/Push 없음) |
| REQ-026b | `notification_settings` | `/notification-settings` | 완료 | 설정 저장·조회 정상 동작(요구사항_정의서_v9 참고) |
| REQ-026c | `patients.caregiver_alert_dismissed_at` | `POST /trust/relations/{id}/dismiss-alert` | 부분 | REQ-005/007(자가진단) 보류로 third_party_needed 분기가 실질적으로 항상 independent 폴백만 탐 |
| REQ-026d | 없음 | - | 미구현 | 요구사항_정의서_v9 참고(2026-07-21 3라운드 감사 — REQ-026a~d를 한 행으로 병합하면 026b 완료·026d 미구현이 가려져 REQ-030/031과 같은 방식으로 분리) |
| REQ-028 | 없음 | - | 측정 인프라 미구현(v8과 동일) | |
| REQ-030 | PII 암호화 필드(Fernet/HMAC) | - | **부분(v8과 동일)** | 전송 구간 암호화는 배포 환경(HTTPS) 의존이라 미배포 상태에서는 검증 불가 — 이 캐비어트는 인가 적용 여부와 무관하게 여전히 열려 있음(2026-07-21 3라운드 감사로 REQ-031과 분리해 명시) |
| REQ-031 | `core/dependencies.py`(`get_current_actor` 등) | 전 라우터의 `Depends()` | **완료로 정정(v8: 부분, 이전 v9 초안: chat만 잔존)** — 2·3·4·5·6·7절(monitoring/care/records/ocr/rag/chat) 전부 인가 적용 완료 | chat_router는 2026-07-14부터 이미 `require_actor_patient_access`가 적용돼 있었다(2026-07-21 재조사로 확인, 이전 v9 초안이 v8의 오래된 서술을 그대로 이어받은 오류였음) |
| REQ-032 | 없음(API 응답 필드 아님) | 모든 가이드·챗봇 응답의 `disclaimer` | 부분(프론트 하드코딩, v8과 동일) | |
| REQ-035 | `deactivated_at`/`deletion_scheduled_at`/`privacy_purge_audits` | `POST /auth/withdraw`, `POST /auth/withdraw/cancel` | **완료로 정정(v8: 미구현)** | 30일 유예 삭제 실행 배치(purge)도 `backend/scripts/purge_expired_accounts.py`(142줄, 테스트 `test_purge_expired_accounts.py` 141줄 포함)로 이미 구현·테스트돼 있다(2026-07-21 재조사로 확인 — 이전 v9 초안의 "실행 로직 유무 미확정"은 잘못된 서술이었다). 다만 서버가 이 스크립트를 자동으로 스케줄링하지는 않는다 — 수동/cron 실행 전제 |
| REQ-036~038 | `medication_schedules`, `medication_records` | `/monitoring/schedules*`, `/monitoring/logs`, `/monitoring/today` | **REQ-037 완료로 정정(v8: 부분)** — `medication_records.status`에 `missed` 포함 + `confirmed_by_type`/`confirmed_by_caregiver_id`(확인자)·`scheduled_at`/`taken_at`(예정·확인시각) 전부 존재, 인수조건 충족 확인 | PR #62 통합, `MedicationLog`와 동일 필드명 재사용 |
| REQ-039 | `failed_login_attempts`/`locked_at`, `password_reset_codes` | `POST /auth/login`, `/auth/password-reset/*` | **완료로 정정(v8: 미구현)** | |
| REQ-040~044 | 없음 | - | 구현취소(지원인력 교육지원/교육·추적관리 기능을 제품 범위에서 제외) | `education_profiles`, `education_support_logs` 테이블과 API를 만들지 않음 |
| REQ-045 | `patients`/`caregivers`(`birth_date`) | `POST /monitoring/patients`, `POST /monitoring/caregivers` | 부분(`birth_date`만, `address` 없음, v8과 동일) | |
| REQ-046 | 없음(가입과 초대가 별개 절차) | - | 미구현(v8과 동일) | |
| REQ-047 | `ocr_results.match_score` | `PATCH /records/{id}/medications/{id}` | **완료로 정정(v8: 미구현)** | PR #59, `typo_suggestion` 응답 필드 |
| REQ-048 | 없음(챗봇 컨텍스트로 자연스럽게 처리) | `/chat/ask` | **완료(2026-07-21 제품 결정으로 재정정, v9 초안: 미구현)** | 원래 설계는 "가이드 있으면 guide_result_id로 진입, 없으면 안내 문구만 표시"하는 조건부 분기였다. `Result.tsx`/`PrescriptionReview.tsx`의 챗봇 진입 버튼이 실제로는 이 조건과 무관하게 항상 노출된다는 사실을 확인한 뒤, 조건부 분기 자체를 없애고 "항상 열려 있다"를 목표 사양으로 확정하기로 제품 결정했다 — 현재 코드가 이미 이 결정을 충족하므로 완료로 정정 |
| REQ-049 | 없음(클라이언트 동작 규약) | - | 프론트 확인 필요(v8과 동일) | |
| REQ-050 | `caregivers`(`org_*`) | `POST /monitoring/caregivers` | 완료(v8과 동일) | |
| REQ-051(신규) | `patients`(`breakfast_time` 등 6개 필드) | `POST /monitoring/patients` 등 | **부분(신규)** | 자가진단 식사시간 — 입력·저장은 되나 가이드 생성 로직에서 미활용 |
| REQ-058(신규) | `invitations`(`patient_id` nullable) | `POST /invitations`, `POST /invitations/{token}/accept` | **완료(신규)** | 보호자→환자 초대(PR #62). [2026-07-21 3라운드 감사로 신설] 이전 초안이 "REQ-037"로 잘못 참조하던 항목 — REQ-037은 복약 여부 기록(아래 REQ-036~038)을 가리키는 별개 번호라 요구사항_정의서_v9에 REQ-058을 새로 만들어 정정 |
