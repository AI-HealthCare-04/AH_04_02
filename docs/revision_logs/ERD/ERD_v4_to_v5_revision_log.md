# ERD 수정 검토 기록

이 문서는 `ERD_v4.md`에서 `ERD_v5.md`로 변경하며 반영한 데이터 모델 수정사항과 설계 판단을 기록한 변경 이력이다.

## 1. `users.last_login_at` 추가 — 반영 완료

리뷰 코멘트: "마지막 로그인 시각을 조회할 방법이 없다."

결정: 로그인 성공 시각을 기록하는 컬럼을 추가한다. 최초 가입 후 아직 로그인한 적이 없을 수 있으므로 nullable로 둔다.

```text
users
- last_login_at datetime nullable  // 추가
```

## 팀에 설명할 핵심 결정

1. 로그인 성공 시점마다 `users.last_login_at`을 갱신한다. 실패 시각은 기존 `last_failed_login_at`에 그대로 기록하므로 성공/실패 이력이 컬럼 단위로 분리된다.
