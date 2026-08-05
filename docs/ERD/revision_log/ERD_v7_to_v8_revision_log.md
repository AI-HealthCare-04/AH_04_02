# ERD 수정 검토 기록

이 문서는 `ERD_v7.md`에서 `ERD_v8.md`로 변경하며 반영한 데이터 모델 수정사항과 설계 판단을 기록한 변경 이력이다. 배경은 API명세서와 동일하게 2026-07-08 멘토링(`멘토링_대화내역_보고서_20260708.docx`, "API 명세서·ERD는 RESTful/실제 구현 기준으로 작성하고 구현 여부를 포함한다")과 2026-07-09 서비스 자체평가("공식 문서가 실제 구현과 불일치한다" 지적)다.

## 결론 요약

| 항목 | 판단 | ERD 수정 방향 |
|---|---|---|
| v7 문서 성격 | v7도 API명세서 v6와 마찬가지로 MySQL·단일 `users` 테이블·해제 승인 워크플로·교육관리 등을 포함한 **목표 설계 문서**였고 실제 구현과 근본적으로 다름이 재확인됨 | v8은 `backend/models.py`의 실제 SQLModel 테이블 12개를 1차 자료로 삼아 새로 작성 |
| PII 암호화 | v7 확정 시점엔 `users.name`/`phone`이 평문 컬럼 설계였음 | `name_encrypted`/`phone_encrypted`(Fernet) + `phone_hash`(HMAC-SHA256, 조회 전용)로 반영, API명세서_v7과 동일한 서술 유지 |
| 사용자 모델 | v7의 단일 `users`(role enum) | 실제로는 `patients`/`caregivers` 완전 분리 테이블 + `caregiver_patients` 다대다 연결. 병합 시 오히려 관계가 더 명확해짐(캐스케이드 삭제 불필요, 역할별 컬럼이 섞이지 않음) |
| 돌봄관계 | v7의 `care_relations`/`care_relation_invitations`(해제 승인 워크플로 포함) | 실제로는 `invitations`(초대) + `caregiver_patients`(연결)만 존재, 해제는 즉시 삭제. PR #29(2026-07-13 병합)로 확정된 "최초 연결은 자유, 추가 연결은 초대 필수" 규칙을 제약사항에 반영 |
| 미구현 기능 | v7에 있던 다수 기능(교육·추적관리, 알림 발송 이력, 가이드 캐싱, 계정 잠금, 탈퇴 유예 삭제 등)이 여전히 미구현으로 확인됨 | 삭제하지 않고 "v7 설계 vs v8 실제" 비교표로 보존, 요구사항 추적표의 구현여부 컬럼과 이중으로 표시 |
| 요구사항 추적 | v7 추적표가 REQ-049까지만 있고 구현 여부 표시가 없었음 | REQ별 구현/부분/미구현 상태를 명시(API명세서_v7과 정합성 유지) |

## 1. v7 문서와 실제 스키마의 근본적 불일치

**발견**: v7은 `users` 단일 테이블(role enum), `care_relations`/`care_relation_invitations`(승인/해제 워크플로), `education_profiles`/`education_support_logs`, `privacy_purge_audits`(탈퇴 유예 삭제), `notification_deliveries`(발송·읽음 이력), `auth_refresh_tokens`/`auth_temporary_codes`, `guide_results.cache_key` 등을 전제로 설계돼 있었다. 실제 `backend/models.py`는 이 중 어느 것도 존재하지 않으며, 대신 `patients`/`caregivers` 분리 + `caregiver_patients` 다대다, `invitations`(단일 테이블), `care_level_assessments`(입력값·평가결과 통합) 등 훨씬 단순한 12개 테이블로 구현돼 있다.

**결정**: API명세서_v7과 같은 원칙으로, v8은 v7에 diff를 얹지 않고 `backend/models.py`(276줄, 12개 SQLModel 클래스)를 그대로 옮겨 새로 작성했다. v7의 세분화된 설계는 삭제하지 않고 "v7 설계 vs v8 실제" 비교표에 남겨, 향후 그 기능(교육관리, 알림 발송 이력, 계정 잠금 등)을 실제로 만들 때 참고할 수 있게 했다.

## 2. PII 암호화 필드를 스키마에 명시적으로 반영

**발견**: `patients.name_encrypted`/`phone_encrypted`(Fernet 대칭키), `phone_hash`(HMAC-SHA256, 조회 전용, 복호화 불가)가 실제 컬럼이지만 v7 mermaid 다이어그램에는 평문 `name`/`phone`으로만 표기돼 있었다. `caregivers.manager_name`/`manager_phone`(단체 담당자 연락처)과 `invitations.invited_phone`은 암호화 범위 밖이라는 사실도 다이어그램만 봐서는 알 수 없었다.

**결정**: 각 테이블 정의에 실제 컬럼명(`*_encrypted`, `*_hash`)과 주석을 그대로 반영하고, "핵심 제약과 조회 규칙"에 암복호화 프로퍼티 동작 방식(2단계 생성 필요, `phone_hash`는 조회 전용)과 암호화 사각지대(`manager_phone`/`invited_phone`)를 API명세서_v7과 동일한 문구로 서술했다 — 두 문서 간 설명이 갈리지 않도록 의도적으로 통일.

## 3. 돌봄관계 최초 연결/추가 연결 규칙(PR #29) 반영

**발견**: v7의 `care_relations`는 해제 시 승인 대기(`revocation_pending`) 상태를 두는 워크플로였다. 실제 구현은 그런 상태 자체가 없고, 대신 이 문서 작성 도중 병합된 PR #29에서 "이미 다른 보호자가 연결된 환자에는 초대 없이 추가 연결할 수 없다"는 IDOR 방지 제약이 신설됐다(2026-07-13, `has_any_caregiver` 체크).

**결정**: "핵심 제약과 조회 규칙"에 이 규칙을 명시했다 — `caregiver_patients` 직접 연결은 해당 `patient_id`에 기존 연결이 하나도 없을 때만 허용되고, 이미 연결된 환자에 대한 추가 연결은 반드시 `invitations`의 토큰 기반 수락을 거쳐야 한다. API명세서_v7의 인가 섹션과 서술을 맞췄다.

## 4. 요구사항 추적표 — 구현 여부 컬럼 정합성

**발견**: v7 추적표는 REQ-001~049를 테이블/API에 매핑했지만 구현 여부 표시가 없어, API명세서_v7에서 이미 "미구현"으로 밝힌 항목(교육·추적관리 REQ-040~044, 계정 잠금 REQ-039, 회원 탈퇴 REQ-035 등)이 ERD만 보면 구현된 것처럼 보일 위험이 있었다.

**결정**: 추적표에 "구현" 컬럼을 추가해 완료/부분/미구현을 표시하고, API명세서_v7과 동일한 판정을 사용했다(같은 REQ가 두 문서에서 다른 상태로 보이지 않도록). 다음 버전인 요구사항_정의서_v8에서 이 판정을 클라이언트 그룹별로 종합할 예정이다.

## 5. (후속 수정) Figma 회원가입 UI 대조 + 서브에이전트 2라운드 교차검증으로 발견한 오류 3건

**Figma 대조**: 2026-07-13, 회원가입 화면 스크린샷과 `frontend/src/pages/SignUp.tsx` 소스를 직접 대조해 `ERD_v8.md`에 "Figma 회원가입 UI 대조" 절을 신설했다 — 개인 가입엔 주소·특이사항 입력란이 UI에도 없다는 점, 기관가입 "담당자 이메일"이 `Caregiver.email`(로그인 아이디)을 재사용하는 의도된 설계라는 점(`monitoring_router.py`의 `CaregiverCreate.email` 주석으로 확인), `org_type` 드롭다운이 실제로는 5개 값(요양원/정부기관/협회/보건소/기타)으로 제한된다는 점을 반영했다.

**서브에이전트 2라운드 교차검증**(사용자 지시, 1라운드 감사 → 2라운드 독립 재검증): 요구사항_정의서_v8의 백로그 오류("개인/단체 회원가입 구분은 설계 미확정")를 계기로 API명세서_v7·ERD_v8도 전수 재검토했다. ERD_v8 자체에는 그 백로그 오류(기관가입 미구현 서술)는 없었지만, 다음 3건의 실제 오류를 발견해 정정했다.

1. **REQ-032(의료 고지) "완료" → "부분"으로 정정**: `disclaimer`는 API 응답 필드가 아니다. `rag-prototype`의 `GuideResponse`는 이 필드를 생성하지만 `backend/routers/rag_router.py`의 `_generate_via_rag_prototype()`이 추출하지 않아 중간에 버려진다 — 실제로는 프론트(`Result.tsx`/`Dashboard.tsx`/`Processing.tsx`) 하드코딩 텍스트다. "핵심 제약과 조회 규칙"에 이 데이터 흐름을 명시했다.
2. **`care_level_assessments.care_level` 기본값(`default="independent"`) 표기 누락 보완**: 같은 엔티티의 다른 필드(`cognitive_level` 등)는 default가 표기돼 있었는데 `care_level`만 빠져 있었다.
3. **`models.py:103`의 `org_type` 코드 주석 stale 여부 명시**: 코드 주석은 "재가센터"인데 실제 프론트(`SignUp.tsx`)는 "정부기관"을 쓴다 — ERD 자체는 Figma·프론트 기준으로 올바르게 작성돼 있었지만, 이 불일치가 ERD에 명시적으로 드러나 있지 않아 추가했다(코드 주석 수정은 이 문서 범위 밖 후속 작업으로 남김).

## 팀에 설명할 핵심 결정

1. **v7도 v6/API명세서_v6처럼 "목표 설계 참고 자료"로 보존한다** — 폐기하지 않고, 교육관리·알림 발송 이력·계정 잠금·탈퇴 유예 삭제 등을 실제로 만들 때 그대로 참고할 수 있게 남겨둔다.
2. **PII 암호화·인가 규칙 서술은 API명세서_v7과 문구를 통일했다** — 같은 사실(암호화 범위, 초대 규칙)이 두 문서에서 다르게 읽히면 팀원이 어느 쪽을 믿어야 할지 혼란스러워지기 때문이다.
3. **PR #29의 IDOR 방지 규칙(추가 연결은 초대 필수)이 ERD 제약사항에 처음 명문화됐다** — 이 규칙은 코드(`monitoring_router.py`)에만 있고 이전 어떤 버전의 ERD에도 문서화된 적이 없었다.
4. **구현 여부 판정은 API명세서_v7과 100% 동일하게 맞췄다** — 다음 단계인 요구사항_정의서_v8(클라이언트 그룹별) 작성 시 이 두 문서의 판정을 그대로 가져다 쓸 수 있다.
5. **이전 버전 파일(`ERD_v7.md`/`.dbml`)은 수정하지 않고 보존, 이번 개정은 새 버전 파일로 버전업한다.**
