# API 명세서 수정 검토 기록

이 문서는 `API명세서_v4.md`에서 `API명세서_v5.md`로 변경하며 반영한 수정사항과 설계 판단을 기록한 변경 이력이다.

## 결론 요약

| 항목 | 판단 | API 수정 방향 |
|---|---|---|
| `신뢰관계` 절 명칭·경로 | 적용 | `돌봄관계`로 개칭, `/trust/*` → `/care-relations/*` |
| care_level·교육 조회 시 subject_id 선지식 필요 | 적용 | `/users/me/...` 자기조회 경로 추가(기존 경로는 유지) |
| RESTful 위반(동사 경로, boolean 액션 바디) | 적용 | 하위자원/상태변경 패턴으로 재작성 |
| `users.last_login_at` 노출 누락(ERD v5 대비 stale) | 적용 | 로그인 응답·`GET /users/me`에 노출 |

## 1. 신뢰관계 → 돌봄관계 개칭 반영 완료

리뷰 코멘트: "필드명을 entity에 맞게 수정. 예를 들면 trust면 guardian, 이렇게 바꾸고."

결정: `relation_type`에 `guardian` 외 `caregiver`·`life_support_worker`·`social_worker`가 포함되어 있어 전체를 "guardian"으로 바꾸면 의미가 틀어진다. ERD와 짝을 맞춰 `care_relations`(돌봄관계)로 통일한다.

- `/trust/invitations*` → `/care-relations/invitations*`
- `/trust/relations*` → `/care-relations*`
- 응답 필드 `trust_id`→`care_relation_id`, `trustee_id`→`related_user_id`, `trustee_name`→`related_user_name`
- 섹션 제목 "2. 신뢰관계" → "2. 돌봄관계"

## 2. care_level·교육 조회의 subject_id 선지식 문제 반영 완료

리뷰 코멘트: "care_level이 subject_id를 알아야 조회할 수 있게 되어 있는데, 그렇게 말고 굳이 뭔가를 통해서 들어갈 수 있게 되어 있는 구조를 수정해달라. 교육도 마찬가지로 확인해달라."

결정: `/medication-subjects/{subject_id}/...` 계열은 그대로 두고(보호자·지원인력이 승인된 `care_relations`로 다른 대상자를 조회할 때 계속 필요), 복약관리 대상자 본인이 자신의 정보를 볼 때는 JWT만으로 대상을 특정하는 `/users/me/...` 경로를 추가한다(기존 경로를 없애는 breaking 변경이 아니라 additive 확장).

- `GET /users/me/status`, `GET /users/me/care-level`, `GET /users/me/care-level/history`, `GET /users/me/care-level-notice`, `POST /users/me/care-level-notice/dismissals` 추가
- `GET /users/me/education-profile`, `GET /users/me/education-profiles`, `GET /users/me/education-support-logs` 추가 (교육자·보호자만 수행하는 `PATCH`는 자기조회 대상에서 제외)
- 권한 규칙 명시: `/users/me/...`는 호출자=대상자, `/medication-subjects/{subject_id}/...`는 호출자가 대상자 본인이거나 승인된 `care_relations`를 가진 사용자여야 하며 그 외 `403 Forbidden`

## 3. RESTful 위반 정리 반영 완료

리뷰 코멘트: "뭐든지 RESTful하게 만들 수 있도록 검토해달라."

발견한 위반과 수정:

- `POST .../revocation-approval` `{approve}` → `PATCH .../{care_relation_id}/revocation` `{revocation_decision:"approved"|"rejected"}` (동사 경로·boolean 액션 바디 제거, DB 컬럼명과 요청 필드명 통일)
- `POST .../care-level-notice/dismiss` → `POST .../care-level-notice/dismissals` (동사 대신 `care_level_notice_dismissals` 테이블과 이름을 맞춘 리소스 생성)
- `POST .../retry` → `POST .../retries` (동사 대신 재시도 컬렉션에 새 항목 생성)
- `POST .../guide/regenerate` → `POST .../guides` (동사 대신 `guide_results` 컬렉션에 새 레코드 생성; 기존 `GET .../guide`는 "최신 1건" 단축 경로로 유지)
- `POST /users/me/withdrawal/cancel` → `PATCH /users/me` `{status:"active"}` (동사 경로 대신 이미 존재하는 사용자 리소스의 상태 필드 변경)
- `POST /auth/temporary-code/resend` → `POST /auth/temporary-codes` (동사 대신 임시번호 컬렉션에 새 코드 생성)
- `POST /notifications/{id}/acknowledge` → `PATCH /notifications/{id}` `{acknowledged:true}` (동사 경로 대신 알림 리소스 상태 변경)

## 4. `users.last_login_at` 노출 누락 반영 완료

리뷰 코멘트: (ERD v5 대비 stale 발견) `users.last_login_at`이 ERD v5에 존재하지만 API v4 응답에는 없었다.

결정: `POST /auth/login` 응답에 `last_login_at`(직전 로그인 시각, 첫 로그인은 `null`)을 추가하고, 계정 정보를 조회할 API 자체가 없었으므로 `GET /users/me`를 신설해 최신 `last_login_at`을 노출한다.

## 팀에 설명할 핵심 결정

1. "trust → guardian" 예시를 그대로 적용하지 않고 `care_relations`로 명명했다 — `relation_type`이 guardian 외 3개 역할을 더 포함하기 때문이며, ERD v5→v6 변경과 반드시 짝을 맞춰야 한다.
2. subject_id 선지식 문제는 기존 경로를 없애는 대신 `/users/me/...`를 추가하는 additive 방식으로 풀었다. 대상자 본인 조회와 보호자·지원인력의 대리 조회는 애초에 인가 규칙이 다르므로, 두 경로를 유지하며 인가 규칙을 명시하는 편이 단일 경로에 조건부 인가를 욱여넣는 것보다 명확하다.
3. RESTful 정리는 전부 "동사 경로 → 하위자원 생성/상태변경"으로 통일된 패턴을 따른다. 응답 바디의 필드명은 가능한 한 DB 컬럼명과 그대로 맞춰 API·ERD 간 어휘 불일치를 줄인다.
4. 이번 버전은 문서(ERD, API 명세서, 요구사항 정의서) 변경만 반영하며, 실제 FastAPI 라우터(`app/apis`)에는 아직 해당 도메인 코드가 없어 애플리케이션 코드 변경은 별도 작업으로 남긴다.
