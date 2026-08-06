# ERD 수정 검토 기록 — v9 → v10

> 버전: v9 → v10 · 날짜: 2026-07-22 · 작성자: 김영혜

## 변경 배경

API명세서_v10과 같은 기준으로 현재 dev/PR #69 이후 코드 의미를 ERD에 반영했다. 새 테이블 추가는 없으며, v9에서 이미 존재하던 테이블의 상태값과 애플리케이션 레벨 관계 규칙을 보강했다.

## 주요 변경

| 구분 | 변경 내용 |
|---|---|
| `invitations.status` | `cancelled` 상태 추가 문서화. 대기중 초대 삭제는 물리 삭제가 아니라 상태 전환이다. |
| `patient_medications` 추적성 | v9에는 테이블이 있었지만 API명세서 범위 밖이었으므로, v10에서 실제 `/patients/{patient_id}/medications*` API와 연결해 설명했다. |
| 처방전 삭제 동기화 | `medical_records.deleted_at`과 연결된 `medication_schedules`, `patient_medications` soft delete/비활성화 규칙을 명시했다. |
| REQ-001 endpoint | refresh token 재발급 API를 실제 코드 기준 `POST /auth/token/refresh`로 정정했다. |
| REQ-021~022 | 챗봇 SSE는 `POST /chat/ask/stream`으로 구현돼 있으므로, "SSE 스트리밍 미구현"이라는 오래된 문구를 제거했다. |
| REQ-040~044 | 지원인력 교육지원/교육·추적관리 기능을 제품 범위에서 제외하기로 하여, 추적표 상태를 미구현이 아니라 구현취소로 정정했다. |

## 남은 후속 과제

- DB FK cascade가 아니라 라우터에서 처리하는 동기화 규칙이므로, 향후 마이그레이션이나 배치 정리 시 `medical_records`/`patient_medications`/`medication_schedules` 관계를 다시 점검해야 한다.
- 의약품 마스터 테이블은 아직 없으므로 `patient_medications.drug_id`는 FK가 아닌 nullable 값으로 유지된다.
