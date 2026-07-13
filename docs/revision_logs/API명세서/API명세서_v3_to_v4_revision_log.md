# API 명세서 수정 검토 기록

이 문서는 `API명세서_v3.md`에서 `API명세서_v4.md`로 변경하며 반영한 수정사항과 설계 판단을 기록한 변경 이력이다.

## 결론 요약

| 항목 | 판단 | API 수정 방향 |
|---|---|---|
| 탈퇴 취소 시 감사 레코드 처리 | 적용 | 레코드 삭제 대신 `purge_status:"cancelled"`로 보존 |

## 1. 인증·사용자 — 탈퇴 취소 감사 로그 처리 반영 완료

리뷰 코멘트: "30일 이내 탈퇴 취소 API가 있습니다. 취소 시 감사 레코드를 삭제하는지, cancelled로 바꾸는지 정의되지 않았습니다."

결정: cancelled로 남긴다(로그 유지).

- `DELETE /users/me` 처리 시 감사 기록(`privacy_purge_audits`)을 조회해 없으면 `purge_status:"scheduled"`로 생성하고, 과거 취소 레코드가 있으면 재사용해 요청·삭제예정 시각을 갱신하고 `purge_status:"scheduled"`로 되돌린다.
- `POST /users/me/withdrawal/cancel` 응답에 `purge_status:"cancelled"`를 추가한다.
- 본문에 "취소 시 감사 기록은 삭제하지 않고 `purge_status:"cancelled"`로 갱신해 취소 이력을 보존한다" 설명을 추가한다.

### 1-1. 자체 검토로 수정 — 응답 필드명, 재탈퇴 처리

- 최초 초안은 응답 필드를 `purge_audit_status:"cancelled"`로 지었으나, ERD 실제 컬럼명(`purge_status`)과 다르고 다른 응답들(`status:"active"` 등)이 DB 컬럼명을 그대로 쓰는 관례와 어긋나 `purge_status`로 통일했다.
- `privacy_purge_audits.subject_reference_hash`가 UK이므로 재탈퇴 시 새 레코드를 만들면 UK 위반이 난다. `DELETE /users/me` 설명에 기존 취소 레코드 재사용 로직을 추가했다.

## 팀에 설명할 핵심 결정

1. 탈퇴 취소는 계정을 `active`로 되돌리는 동시에 감사 기록을 `cancelled`로 갱신해, 탈퇴 신청과 취소 이력이 모두 남도록 한다.
2. 감사 기록 관련 응답 필드는 실제 DB 컬럼명(`purge_status`)과 동일하게 맞춰 API·ERD 간 필드명을 일치시킨다.
3. 재탈퇴 시나리오(탈퇴→취소→재탈퇴)에서 UK 위반이 나지 않도록 기존 레코드 재사용 로직을 명시한다.
4. 이번 리뷰의 REQ-028 추적표 누락, enum 값 개수 이슈는 API 계약 자체에는 영향이 없어 ERD·요구사항 정의서 문서에서만 반영한다.
