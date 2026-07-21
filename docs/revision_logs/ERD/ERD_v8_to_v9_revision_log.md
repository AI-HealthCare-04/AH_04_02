# ERD 수정 검토 기록 — v8 → v9

> 버전: v8 → v9 · 날짜: 2026-07-21 · 작성자: 김영혜

배경: API명세서_v9와 동일 — 정합성 검토(권순현, 2026-07-15) + PR #56/#59/#60/#61/#62 병합 + 2026-07-17 회의 결정 반영. v8(2026-07-13) 시점엔 12개 테이블이었으나 이번 조사로 `backend/models.py`(517줄) 전수 확인 결과 19개 테이블로 늘어난 것을 처음 문서화한다.

## 결론 요약

| 항목 | 판단 | ERD 수정 방향 |
|---|---|---|
| 테이블 수 | v8: 12개 → v9: 19개 | 신규 7개 테이블(`password_reset_codes`, `privacy_purge_audits`, `notification_logs`, `patient_medications`, `medication_records`, `refresh_tokens`, `guide_cache`) 전체 반영 |
| `invitations` 보안 필드 | v8까지 `token`(평문)/`invited_phone`(평문)이었으나, 2026-07-15 보안 리뷰(REQ-030/002)로 `token_hash`/`invited_phone_encrypted`/`expires_at`으로 전환됨 — v8 작성 시점엔 이 변경 전이라 반영 못 함 | v9에서 필드명·주석 전면 갱신, v8의 "보안 주의" 항목이 해소됐음을 명시 |
| `invitations.patient_id` | v8까지 non-nullable | REQ-037(보호자→환자 초대)로 nullable 전환 — 초대 생성 시점엔 환자 계정이 없을 수 있음 |
| `caregiver_patients` | v8은 상태 컬럼 없이 존재 자체만 다룸 | REQ-004(해제 승인 워크플로, PR #56)로 `status`/`revoked_at`/`revocation_requested_by`/`requested_by_role` 추가된 것 반영 |
| `medication_logs` vs `medication_records` | v8은 `medication_logs`만 실사용 테이블로 서술 | PR #62로 `medication_records`가 유일한 실사용 체크인 테이블로 승격된 것 반영(`medication_logs`는 하위호환용으로만 잔존) |
| `patients`/`caregivers` 필드 | v8은 인증·탈퇴·식사시간 관련 필드 전혀 없음 | 로그인 잠금(`failed_login_attempts`/`locked_at`)·탈퇴(`deactivated_at`/`deletion_scheduled_at`)·식사시간(`breakfast_time` 등 6개)·연결권유 억제(`caregiver_alert_dismissed_at`) 필드 전부 반영 |
| 요구사항 추적표 | v8은 API명세서_v7 기준 판정 | API명세서_v9·요구사항_정의서_v9와 동일 판정으로 갱신(REQ-004/007a/020/035/037/039/047 완료 승격, REQ-005/006/007 보류로 하향, REQ-032 부분 유지) |

## 1. 신규 테이블 7개 — 전수 반영

`password_reset_codes`(비밀번호 재설정 코드, HMAC 해시·10분 만료), `privacy_purge_audits`(탈퇴 감사 기록, pending/completed/cancelled), `notification_logs`(알림 발송 로그, reminder/missed 종류 + pending/sent/suppressed/failed 상태), `patient_medications`(환자가 직접 등록한 약, source_type으로 OCR/수동/사진/API검색 구분), `medication_records`(REQ-037 실사용 복약기록, missed 포함), `refresh_tokens`(jti가 PK, 회전·재사용 탐지), `guide_cache`(REQ-020 가이드 캐싱, SHA-256 키+7일 TTL) — 이 7개는 모두 alembic 마이그레이션 체인(마이그레이션 2~16, head `66c32a201ba5`)으로 실제 DB에 적용된 스키마이며 모델 정의뿐인 "설계"가 아니다.

## 2. `invitations` 보안 필드 전환(v8 지적사항 해소)

**발견**: v8 작성 시점(2026-07-13)엔 `invitations.token`이 평문 저장·목록조회 응답에 그대로 노출되고 `invited_phone`도 암호화 없이 평문 저장되는 것이 알려진 취약점이었다. 이틀 뒤(2026-07-15) 별도 보안 리뷰에서 `token_hash`(해시 저장, 발급 시 1회만 원문 응답)와 `invited_phone_encrypted`(Fernet 암호화)로 전환하고 `expires_at`(발급+7일)을 추가했다.

**결정**: v9는 이 전환 이후 상태를 반영한다. v8이 "보안 주의"로 남겼던 두 항목이 모두 코드 수정으로 실제 해소됐음을 명시한다.

## 3. 요구사항 추적표 갱신 — API명세서_v9·요구사항_정의서_v9와 3자 정합성 유지

REQ-004(완료로 승격, PR #56), REQ-007a(완료로 승격, PR #56), REQ-020(완료로 승격, PR #60), REQ-030/031(records/ocr/rag 완료로 범위 축소, chat만 잔존), REQ-035(완료로 승격, auth_router.py 전수조사로 확인), REQ-037(완료로 승격, PR #62), REQ-039(완료로 승격, auth_router.py 전수조사로 확인), REQ-047(완료로 승격, PR #59) — 전부 API명세서_v9·요구사항_정의서_v9와 동일한 판정을 사용해 3개 문서 간 상태값 불일치가 없도록 했다.

**REQ-005/006/007(자가진단)은 "완료"에서 "보류"로 하향했다** — 2026-07-17 회의에서 이 기능의 원래 목적(care_level 기반 제3자 도움 필요 판단)을 서비스 방향에서 제외하기로 결정했고, 프론트엔드 조사 결과 이 값을 입력하는 화면 자체가 만들어진 적이 없다는 사실을 이번에 처음 확인했기 때문이다. ERD 관점에서는 `care_level_assessments` 테이블과 API는 그대로 존재하므로 스키마 자체를 삭제하지 않았다 — 다만 이 테이블이 사실상 항상 비어 있고, 이를 참조하는 다른 REQ(004/007a/026c)의 `third_party_needed` 분기는 "평가 이력이 없으면 independent로 간주" 폴백만 실질적으로 작동한다는 점을 "핵심 제약과 조회 규칙"에 명시했다.

## PR 전 3라운드 서브에이전트 감사(2026-07-21)로 발견·수정된 오류

- **head revision 오표기**: 초안이 head를 `66c32a201ba5`로 적었으나 `uv run alembic heads`로 재확인한 실제 head는 `c3a413343157`다(그 사이 `bfc3d4e49682`/`849bd15b19a5`/`c3a413343157` 3개 마이그레이션이 더 있었음). 단일 head로 분기(브랜치) 없음도 함께 확인.
- **REQ-030/031 chat_router 인가 오류**: API명세서_v9와 동일한 오류(chat_router는 실제로 2026-07-14부터 인가 적용돼 있었음) — 완료로 정정.
- **REQ-035 purge 배치 "미확정" 오류**: `backend/scripts/purge_expired_accounts.py`(142줄, 테스트 포함)가 이미 구현·테스트돼 있음을 확인하고 "확정 못함"을 "존재하나 자동 스케줄링은 아님"으로 정정.

## Round 2(문서 간 정합성) 감사로 추가 발견·수정된 오류

- **REQ-037/REQ-058 번호 중복(가장 심각한 발견)**: ERD가 "보호자→환자 초대"와 "복약 여부 기록"(진짜 REQ-037) 두 가지를 모두 "REQ-037"로 표기해 문서 자체가 내부적으로 모순돼 있었다 — 요구사항_정의서_v9에 신설된 REQ-058로 초대 기능 참조를 전부 정정했다.
- **REQ-030/031·REQ-026a~d 병합 표기가 개별 상태를 가림**: "REQ-030/031 완료"로 병합해 REQ-030 자체의 "전송구간 암호화 미검증(부분)" 캐비어트가 사라졌던 것과, "REQ-026a~026d 부분"으로 병합해 026b(완료)·026d(미구현)가 가려졌던 것을 각각 행 분리로 정정.

## PR #63 병합 전 추가 발견·수정된 오류(2026-07-21, status 파일 작성 중)

- **REQ-048 문서 간 불일치**: ERD가 "완료(전용 API 아님, v8과 동일)"로 서술하고 있었으나, 요구사항_정의서_v9는 이미 "미구현"으로 정확했다. 코드 재확인 결과 `Result.tsx`/`PrescriptionReview.tsx`의 챗봇 진입 버튼은 `guide_result_id` 유무와 무관하게 항상 노출돼(대신 `diagnosis`만 전달), REQ-048이 요구하는 조건부 분기(가이드 없으면 안내 문구만 표시) 자체가 없다 — ERD를 "미구현"으로 정정해 요구사항_정의서와 통일했다.

## 팀에 설명할 핵심 결정

1. **테이블 수가 12→19개로 늘어난 것은 v8 작성 이후 실제로 여러 PR이 병합됐기 때문이지, v8 조사가 부실했기 때문이 아니다** — v8은 2026-07-13 시점의 정확한 스냅샷이었다.
2. **`invitations`의 보안 필드 전환(token_hash/invited_phone_encrypted)은 v8이 지적한 취약점이 실제로 코드 수정을 통해 해소된 사례다** — 문서가 문제를 지적하고 실제 개발로 이어진 좋은 선례로 남긴다.
3. **자가진단(REQ-005/006/007)을 "보류"로 재분류한 것은 버그가 아니라 제품 방향 결정이다** — 2026-07-17 회의에서 명시적으로 그 목적을 폐기하기로 했고, 온보딩 화면 구조만 식사시간 입력(REQ-051)으로 재사용했다.
4. **이전 버전 파일(`ERD_v8.md`)은 수정하지 않고 보존, 이번 개정은 새 버전 파일로 버전업한다.**
