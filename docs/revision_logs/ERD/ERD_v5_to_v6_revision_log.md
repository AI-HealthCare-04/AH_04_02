# ERD 수정 검토 기록

이 문서는 `ERD_v5.md`에서 `ERD_v6.md`로 변경하며 반영한 데이터 모델 수정사항과 설계 판단을 기록한 변경 이력이다.

## 1. `trust_invitations`/`trust_relations`/`trustee_id` → `care_relation_invitations`/`care_relations`/`related_user_id` — 반영 완료

리뷰 코멘트: "필드명을 entity에 맞게 수정해달라. 예를 들면 trust면 guardian처럼."

결정: 사용자 제안대로 `guardian`으로 바꾸면 의미가 틀어진다. `relation_type`에 `guardian` 외 `caregiver`·`life_support_worker`·`social_worker`도 포함되어 있어, 이 관계를 전부 "보호자(guardian)"라고 부르면 요양보호사·생활지원사·사회복지사 관계까지 잘못 지칭하게 된다. 대신 4개 관계 유형을 모두 포괄하는 도메인 중립적 이름인 `care_relations`(돌봄관계)를 사용한다.

```text
trust_invitations → care_relation_invitations   // 테이블명 변경, 컬럼 구성은 동일
trust_relations   → care_relations              // 테이블명 변경
- trustee_id → related_user_id                  // 컬럼명 변경 (같은 테이블 내)
```

mermaid 다이어그램의 관계선(`users ||--o{ ...`)과 `accepted_invitation` FK 관계, "핵심 제약과 조회 규칙"의 서술, "요구사항 추적" 표의 REQ-002~004 행을 모두 새 이름으로 갱신했다.

## 2. 해제 승인 필드명 `approve` boolean → `revocation_decision` enum 반영 완료

리뷰 코멘트: (API 명세서 RESTful 검토 과정에서 함께 발견) 요청 바디의 `approve` boolean과 DB 컬럼 `revocation_decision`(`approved|rejected`)이 서로 다른 이름·타입을 쓰고 있었다.

결정: API 요청 바디도 `revocation_decision` enum(`approved|rejected`)으로 통일해 DB·API가 같은 어휘를 쓰도록 맞춘다. 상세 내용은 `docs/revision_logs/API명세서/API명세서_v4_to_v5_revision_log.md` 참고.

## 팀에 설명할 핵심 결정

1. "trust → guardian" 예시를 문자 그대로 적용하지 않고, 4개 관계 유형을 모두 포괄하는 `care_relations`로 명명했다. `guardian`이라는 이름은 이후 실제 "보호자" 개념(예: `role` enum의 `guardian` 값)과 혼동을 일으킬 수 있어 의도적으로 피했다.
2. 이번 버전업은 API 명세서 v4→v5 RESTful 재검토와 짝을 이룬다. ERD의 테이블/필드명 변경은 API 경로·요청 바디 변경과 항상 함께 반영해야 하며, 한쪽만 갱신하면 두 문서가 어긋난다.
3. `care_level`/`education_profiles` 조회가 `{subject_id}`를 몰라도 되도록 `/users/me/...` 자기조회 경로를 추가한 것은 API 계약 확장(additive)이며 ERD 테이블 구조 자체는 바뀌지 않는다 — "요구사항 추적" 표의 API 열만 갱신했다.
