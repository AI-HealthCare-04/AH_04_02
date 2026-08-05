# API 명세서 수정 검토 기록 — v9 → v10

> 버전: v9 → v10 · 날짜: 2026-07-22 · 작성자: 김영혜

## 변경 배경

PR #69 이후 dev 기준 라우터와 API명세서_v9를 다시 대조한 결과, 실제 구현은 존재하지만 명세서에 없거나 Method가 다른 항목이 발견됐다. 이번 v10은 새 기능 구현이 아니라 **문서가 실제 코드 계약을 따라오도록 최신화**하는 목적이다.

## 주요 변경

| 구분 | v9 | v10 |
|---|---|---|
| refresh token 재발급 | `GET /auth/token/refresh`로 문서화 | 실제 코드 기준 `POST /auth/token/refresh`로 정정 |
| 초대 삭제 | 미문서화 | `DELETE /invitations/{invitation_id}` 추가, pending 초대를 `cancelled` 상태로 전환 |
| 받은 초대함 | 미문서화 | `GET /caregivers/{caregiver_id}/pending-invitations`, `POST /invitations/{invitation_id}/accept-as-caregiver`, `POST /invitations/{invitation_id}/reject-as-caregiver` 추가 |
| 환자 내약 등록 | `patient_medications_router.py`를 범위 밖으로 표기 | `/patients/{patient_id}/medications*`, `/patients/{patient_id}/medication-records` 절 신설 |
| 처방전 삭제 | 처방전 + schedule 비활성화 중심 | 처방전 삭제 시 연결된 PatientMedication soft delete 및 해당 내약 기반 schedule 비활성화까지 명시 |
| REST 관점 | care_router prefix 부재만 지적 | 현재 경로는 유지하되 리소스 의미와 후속 개선 후보를 분리해 명시 |
| SSE 서술 | 공통 설명에 "SSE 스트리밍은 없다"는 v8 계열 문구가 남아 있음 | `POST /chat/ask/stream`은 챗봇 SSE 지원, RAG 진행률 전용 SSE만 미구현으로 정정 |
| 교육·추적관리 | REQ-040~044를 전체 미구현/다음 스프린트 결정 후보로 표기 | 지원인력 교육지원 기능을 제품 범위에서 제외하기로 하여 REQ-040~044를 구현취소로 표기 |

## 남은 후속 과제

- `care_router` prefix 부재는 실제 프론트 호출부 영향이 커서 이번 문서 버전업에서는 경로 변경 없이 알려진 개선 후보로 유지한다.
- 교육·추적관리(REQ-040~044)는 구현취소로 정리했으므로 후속 구현 후보에서 제외한다.
- 요구사항 번호와 endpoint의 1:1 매핑표는 v10에서 핵심 누락분을 보강했지만, 전체 REQ 전수 매핑은 추가 점검이 필요하다.
