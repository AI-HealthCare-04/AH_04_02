# ERD 수정 검토 기록

이 문서는 `ERD_v3.md`에서 `ERD_v4.md`로 변경하며 반영한 데이터 모델 수정사항과 설계 판단을 기록한 변경 이력이다.

## 1. 탈퇴 취소 감사 로그 처리 — 반영 완료

리뷰 코멘트: "30일 이내 탈퇴 취소 API가 있습니다. 취소 시 감사 레코드를 삭제하는지, cancelled로 바꾸는지 정의되지 않았습니다."

결정: cancelled로 남긴다(로그 유지, 레코드는 삭제하지 않는다).

```text
privacy_purge_audits
- purge_status enum(scheduled, cancelled, completed, partial, failed)  // cancelled 추가
- cancelled_at datetime nullable  // 추가
```

핵심 제약에 다음 규칙을 추가한다: "탈퇴 신청 시점에 `privacy_purge_audits` 레코드를 `purge_status=scheduled`로 즉시 생성한다. 30일 내 탈퇴를 취소해도 이 레코드는 삭제하지 않고 `purge_status=cancelled`, `cancelled_at`을 기록해 감사 이력을 보존한다."

### 1-1. 자체 검토로 발견 — 재탈퇴 시 UK 충돌 위험 보완

`subject_reference_hash`는 UK(유니크)다. 최초 결정대로 "취소해도 레코드를 삭제하지 않는다"만 적용하면, 같은 사용자가 탈퇴→취소→재탈퇴를 반복할 때 재탈퇴 시점에 새 레코드를 만들면서 UK 위반이 발생한다. 이를 막기 위해 규칙을 다음과 같이 보완한다: 탈퇴 신청 시 `subject_reference_hash`로 기존 레코드를 조회해, 없으면 새로 생성하고 과거 취소 레코드가 남아있으면 그 레코드를 재사용해 `withdrawal_requested_at`·`scheduled_purge_at`을 갱신하고 `purge_status=scheduled`, `cancelled_at=NULL`로 되돌린다.

## 2. 요구사항 추적표 REQ-028 누락 — 반영 완료

리뷰 코멘트: "요구사항 추적표에 REQ-028 행 누락. 핵심 제약 본문(274번 줄)에는 REQ-028 계산식이 명시돼 있는데 추적표에는 없음."

| 요구사항 | 테이블/필드 | API |
|---|---|---|
| REQ-028 | `medical_records.ocr_completed_at`, `guide_results.generated_at` | `/medical-records/{record_id}` |

## 3. auth_temporary_codes.purpose / care_level_notice_dismissals.notice_type enum — 변경 없음(검토 완료)

리뷰 코멘트: "enum 값이 1개뿐이라 실익이 적다. 향후 다른 용도 추가를 대비한 설계라면 괜찮고, 아니라면 상수로 둬도 무방하다."

결정: 일반 비밀번호 재설정, 회원가입 인증 등 향후 용도 확장을 대비해 현행 enum 구조를 그대로 유지한다. 스키마 변경 없음. 결정 사유는 핵심 제약에도 "(v4) `auth_temporary_codes.purpose`, `care_level_notice_dismissals.notice_type`은 현재 값이 각각 1개뿐이지만..." 문장으로 명시해 revision log뿐 아니라 ERD 본문에서도 확인 가능하도록 했다.

## 팀에 설명할 핵심 결정

1. 탈퇴 취소는 계정 상태만 되돌리고, 감사 레코드는 삭제 대신 `cancelled` 상태로 보존해 탈퇴·취소 이력을 추적할 수 있게 한다.
2. `subject_reference_hash` UK 제약 때문에 재탈퇴 시에는 새 레코드가 아니라 기존 취소 레코드를 재사용해야 한다. 단순히 "삭제하지 않는다"만 정의하면 재탈퇴 시나리오에서 깨진다.
3. REQ-028 추적 누락은 본문 규칙과 추적표 간 불일치였으므로 추적표에 행을 추가해 일치시킨다.
4. purpose/notice_type enum은 지금은 값이 하나뿐이지만 실제 확장 가능성이 있어 상수화하지 않으며, 그 이유를 ERD 본문에도 남긴다.
