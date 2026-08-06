# API 명세서 수정 검토 기록 — v10 → v11

> 버전: v10 → v11 · 날짜: 2026-07-28 · 작성자: 김영혜

## 변경 배경

v10(2026-07-22, 커밋 `8b1e574`) 작성 이후 dev에 90개 커밋이 머지됐다. 백그라운드 조사(90개 커밋 전체 diff 조사)를 근거로 실제 라우터·스키마 변경사항을 문서에 반영한다.

## 주요 변경

| 구분 | v10 | v11 |
|---|---|---|
| 자가진단(3절) | API·테이블이 코드에 남아있음("보류") | `POST /assessments`·`GET /assessments/latest`·`care_level_assessments` 테이블 실제 삭제. 절 자체를 삭제(번호 재부여 안 함) |
| 돌봄관계 해제(REQ-004) | `care_level` 기반 즉시/승인 분기 | `DELETE /trust/relations/{id}` 제거, `DELETE /monitoring/caregivers/{cid}/patients/{pid}`로 흡수 — organization 계정만 사유+승인(14일 자동확정) 필요 |
| 보호자·기관 검토 | 없음 | `POST /records/{id}/request-correction`, `.../mark-reviewed`, `PATCH .../medications/{id}/correct`, `GET /records/notices` 신설 |
| 처방전 사진 | 업로드 후 폐기 | 저장·서빙(`GET /records/{id}/image`) 신설 |
| 계정 전환/세션 | 문서화 안 됨 | `POST /auth/verify-password` 신설, refresh_token 완전 쿠키화 서술 보강 |
| 알림함 | 없음 | `GET /trust/relations/notices`, `GET /records/notices`, `GET /monitoring/patients/{id}/notifications` 신설 |
| Web Push | 없음 | `GET /push/vapid-public-key`, `POST/DELETE /push-subscriptions` 신설 — **백엔드만, 프론트 미연동** 명시 |
| 모니터링/환자관리 | 기존 그대로 | `check-duplicate` 2종, `PATCH /monitoring/caregivers/{id}` 신설, `PatientPublic` 필드 확장(gender/diagnoses/medication_status/today_status) |
| 복약 일정 | `caregiver_alert: bool` | `alert_caregiver_ids: list[int]`로 대체(스케줄별 이름 지정) — 알림이 항상 1인에게만 가던 버그 수정 |
| 생활습관 안내 | 자유 텍스트 | `diet`/`exercise`/`other` × `recommended`/`avoid` 구조화, KDCA 관련성 필터링 버그 수정 |
| 챗봇 | DUR 답변은 출처 항상 빈 배열 | DUR 조회 결과도 `source_refs`에 구조화되어 포함 |
| 등록내역 | 정렬 없음 | `pinned`(즐겨찾기) 필드 + 정렬 변경 |
| 타임존 | 서버 로컬 시각 그대로 | 스케줄러만 `_now_kst()`로 고정(Docker UTC 기동 시 9시간 지연 버그 수정) |

## 남은 후속 과제

- `care_router` prefix 부재는 이번에도 경로 변경 없이 유지(REST 개선 후보로 계속 이월).
- Web Push 프론트엔드 서비스워커 구독 흐름 — HTTPS 배포 이후 작업.
- 이번 버전은 v9→v10처럼 여러 라운드의 코드 재조사(3라운드 감사 등)를 거치지 못했다 — 백그라운드 조사 1건을 근거로 작성했으므로, REQ-063~075(전부 신규)는 다음 리뷰에서 재검증이 필요하다.
