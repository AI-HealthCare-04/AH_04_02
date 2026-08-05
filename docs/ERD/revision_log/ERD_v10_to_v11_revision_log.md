# ERD 수정 검토 기록 — v10 → v11

> 버전: v10 → v11 · 날짜: 2026-07-28 · 작성자: 김영혜

## 변경 배경

API명세서_v11과 동일한 근거(v10 이후 dev 90개 커밋)로 스키마를 재작성했다. alembic head를 `48230e8ff2b4`로 재확인(단일 head).

## 주요 변경

- **삭제**: `care_level_assessments` 테이블(자가진단 기능 삭제).
- **신규 테이블 6개**: `revocation_notices`(연결/해제 알림), `record_correction_notices`(처방전 검토 알림), `medication_field_flags`(검토 지적 사항), `push_subscriptions`(Web Push 구독, 백엔드만), `schedule_caregiver_alerts`(일정별 알림 대상), `audit_logs`(최소 감사로그).
- **필드 추가**: `patients.gender`, `caregiver_patients.revocation_reason`/`revocation_requested_at`, `medical_records.pinned`/`prescription_date`/`caregiver_review_status`, `ocr_results.dose_amount`.
- **제약 변경**: `caregivers.email`의 DB unique 제약 제거(app 레벨에서 `relation_type`별로만 검사).
- **JSON 스키마 변경**: `guide_results.lifestyle_guide` 내부 구조가 자유 텍스트에서 `diet`/`exercise`/`other` × `recommended`/`avoid`로 변경(`GUIDE_DATA_VERSION` v1.2로 캐시 무효화).
- **워크플로 재설계**: 돌봄관계 해제(REQ-004)가 `care_level` 기반에서 "요청자가 organization인가" 기반으로 변경, REQ-066으로 상세 절차 분리.
- 요구사항 추적 표를 v11 기준으로 전면 갱신 — REQ-063~075(전부 신규) 추가, REQ-005~007 "보류"→"구현취소" 재정정.

## 남은 후속 과제

- `push_subscriptions`/`schedule_caregiver_alerts`의 복합 유니크 제약은 mermaid ER 다이어그램 문법상 표현이 제한적이라 prose로만 설명 — 실제 SQLModel `UniqueConstraint` 정의와 대조 재확인 필요.
- `revocation_notices`/`record_correction_notices`/`push_subscriptions`/`audit_logs`는 `password_reset_codes`와 동일한 다형 참조(FK 없음) 패턴 — 관계선 없이 표기했다.
