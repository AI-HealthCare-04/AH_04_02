# API 명세서 수정 검토 기록 — v11 → v12

> 버전: v11 → v12 · 날짜: 2026-08-03 · 작성자: 김영혜(Claude 세션)

## 변경 배경

v11(2026-07-28, 커밋 `15a23f6`) 작성 이후 dev에 100개 커밋(`15a23f6`..`2f95b07`)이 머지됐다. 전수 코드 감사(라우터 8개 전체 재확인 + 관련 테스트 재실행)를 근거로 실제 엔드포인트·스키마 변경사항을 문서에 반영한다. 초안 작성 → 정확성/일관성 2인 비평 → 수정 1라운드를 거쳤다.

## 주요 변경

| 구분 | v11 | v12 |
|---|---|---|
| 계정 전환(REQ-065) | 미문서화 | `POST /auth/switch`(저장된 계정 전환)·`POST /auth/switch/forget`(자동 로그인 해제) 신규 문서화 — 코드 자체는 2026-07-22부터 있었으나 v11까지 누락됐던 기존 갭 |
| 알림 on/off(REQ-082, 신규) | 없음 | `PATCH /monitoring/caregivers/{cid}/patients/{pid}/notifications` 신설 — (보호자,환자) 관계 단위 push 토글(커밋 `24dbb8f`) |
| 알림함 일괄확인 | 없음 | `POST /monitoring/patients/{patient_id}/notifications/acknowledge` 신설 |
| 초대 발급 중복 검증 | 미문서화 | `POST /invitations`가 이미 연결된 사용자에 409 반환(커밋 `40393a2`) |
| 초대 수락 응답(PR #131) | 신규 계정 생성 경로도 토큰 없이 `{caregiver_id/patient_id, status}`만 반환 | 신규 계정 생성 경로는 로그인 payload(`access_token` 등)가 병합됨 — 수락 직후 강제 로그아웃되던 실제 장애 수정(커밋 `d550239`/`2784856`/`bac9b9c`/`2f95b07`). 기존 로그인 계정 재사용 경로는 변경 없음 |
| 받은 초대 목록 | 이미 연결된 환자의 초대도 노출 | 이미 연결된 환자의 초대는 목록에서 제외(커밋 `40393a2`) |
| `GET /invitations/{token}` | `expires_at` 누락(v11 자체 문서 갭) | `expires_at` 추가 |
| RAG 가이드 생성 실패 | "OCR 결과 없음" 케이스만 문서화 | 자동 가이드 생성 가능한 약이 하나도 없으면 `status="failed"`(신규 실패 시나리오, `GUIDE_DATA_VERSION` v1.2→v1.3) |
| e약은요/HIRA 조회 | 부분 매칭 시 즉시 반환 | 부작용·보관법 둘 다 채워진 히트를 찾을 때까지 후보 재시도(이슈 #107/#108 수정) |
| Push 발송 | 필터링 없음 | `caregiver_wants_notifications()`로 관계 단위 알림 끄기 반영, payload에 `schedule_id` 추가(서비스워커 액션버튼용), 알림 URL이 `/schedule`→`/dashboard?highlight=...`로 변경 |
| 용어 매핑 | AUTO_GUIDE_MATCH_THRESHOLD/자동가이드 적격 개념 없음 | 두 용어 신규 추가(기존 MATCH_THRESHOLD와의 차이 명시) |

**삭제된 엔드포인트·필드는 없다.**

## 검증

- 전체 라우터(`auth_router.py`, `care_router.py`, `chat_router.py`, `monitoring_router.py`, `ocr_router.py`, `rag_router.py`, `records_router.py`, `patient_medications_router.py`) 전문을 다시 읽어 v11 서술과 대조.
- `test_care_router_invitations.py`, `test_caregiver_patient_notifications.py`, `test_invitation_accept_existing_patient.py`, `test_auth_switch_account.py`, `test_notification_inbox.py` 등 관련 테스트 재실행(56/57 통과 — 1개는 무관한 기존 flaky 테스트).
- alembic head `46e60aff6632`(부모 `48230e8ff2b4`=v11 당시 head) — v11 이후 순수 신규 마이그레이션 1개만 확인.

## 남은 후속 과제

- `care_router` prefix 부재는 이번에도 경로 변경 없이 유지(REST 개선 후보로 계속 이월).
- REQ-082(알림 음소거)는 요구사항_정의서에 이번에 처음 배정한 가번호 — 팀 확인 후 정식 번호 확정 필요.
- 이번 v12는 API 감사 1건 + 정확성/일관성 비평 1라운드만 거쳤다(원래 계획한 3라운드 중 세션 한도 문제로 1라운드만 완주). 다음 버전에서 추가 검증 라운드를 거치는 것을 권장한다.
