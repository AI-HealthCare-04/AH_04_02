# API 명세서 수정 검토 기록

이 문서는 `API명세서_v6.md`에서 `API명세서_v7.md`로 변경하며 반영한 수정사항과 설계 판단을 기록한 변경 이력이다. 배경은 2026-07-08 멘토링(`멘토링_대화내역_보고서_20260708.docx`)에서 "API 명세서는 RESTful 원칙에 맞춰 작성하고, 개인정보 암호화 적용 여부와 구현 여부·미구현 여부를 포함한다"고 확정받은 것과, 서비스 자체평가(2026-07-09, `AH04_2조_서비스평가_2026-07-09.docx`)에서 "공식 문서(API명세서/ERD)가 실제 구현과 불일치한다"고 지적받은 것이다.

## 결론 요약

| 항목 | 판단 | API 수정 방향 |
|---|---|---|
| v6 문서 성격 | v6은 실제 구현이 아니라 MySQL·단일 `users` 테이블·SSE·교육관리 등을 포함한 **목표 설계 문서**였음이 코드 감사로 확인됨 | v7은 `backend/routers/` 7개 라우터를 전수 조사해 **실제 존재하는 엔드포인트만** 기준으로 재작성 |
| 인가(authorization) | 작성 착수 시점엔 로그인은 구현됐으나 토큰 검증 엔드포인트가 전무했음(issue #21). 작성 도중 PR #29가 병합돼 2·3·7절은 적용 완료로 전환됨 | 문서 최상단에 전용 경고 섹션 신설, 모든 엔드포인트 표에 "인증" 컬럼 추가 — 2·3·7절은 O, 4·6절(records/ocr/rag/chat)은 여전히 X |
| 미구현 기능 | v6에 있던 기능 다수(탈퇴, 비밀번호 재설정, 계정 잠금, 돌봄관계 해제 승인, SSE, TTS, 캐싱, 교육·추적관리 전체)가 미구현으로 확인됨 | 요구사항 자체를 지우지 않고, 각 절 끝에 "미구현 항목" 목록으로 보존 |
| PII 암호화 | `patients`/`caregivers`의 `name`/`phone`은 Fernet 암호화 저장, 응답 시 항상 평문 복호화. `Invitation.invited_phone`/`Caregiver.manager_phone`은 암호화 범위 밖 | 1·2절에 명시적으로 서술 |
| RESTful 일관성 | `care_router`만 다른 6개 라우터와 달리 prefix가 없어 `/assessments`, `/invitations` 등이 루트에 노출됨 | 문서 상단에 라우터 prefix 표로 명시, 다음 버전에서 `/care` prefix 검토 권고 |

## 1. v6 문서와 실제 구현의 근본적 불일치

**발견**: v6은 Base URL `/api`, MySQL 8.0, 단일 `users` 테이블(role enum), `care_relations`/`care_relation_invitations`(해제 승인 워크플로 포함), `education_profiles`(교육 단계 자동 분류), SSE 스트리밍, TTS 음성, 캐시 버전 관리(`cache_key`/`cache_expires_at`) 등을 전제로 작성돼 있었다. 실제 `backend/`는 SQLite, `patients`/`caregivers` 분리 테이블, 동기 처리(SSE 없음), 캐싱 없음, 교육관리 기능 자체가 없다.

**결정**: v7은 v6에 diff를 얹는 방식이 아니라, 라우터 코드를 1차 자료로 삼아 사실상 새로 작성했다. 다만 v6가 설계한 기능(REQ 번호로 추적되는 요구사항)은 문서에서 완전히 삭제하지 않고 각 절 "미구현 항목"으로 남겨, 다음에 이 기능을 실제로 구현할 때 v6의 설계를 참고할 수 있게 했다.

## 2. 인가(authorization) 상태를 문서 최상단에 전용 섹션으로

**발견**: `backend/dependencies.py`에 `get_current_caregiver`/`get_current_patient`가 정의돼 있지만, 7개 라우터 어디에서도 `Depends()`로 사용되지 않는다. 로그인(`POST /auth/login`)이 JWT를 발급하지만 그 토큰을 검증하는 엔드포인트가 시스템에 하나도 없다 — 즉 모든 엔드포인트가 `caregiver_id`/`patient_id`를 요청 파라미터로 그대로 신뢰한다(IDOR).

**결정**: 이 갭이 사실상 전 절에 적용되는 공통 사항이라, 절마다 반복 서술하는 대신 문서 최상단에 `## ⚠️ 인가(Authorization)` 섹션을 신설해 한 번에 설명하고, 각 엔드포인트 표의 "인증" 컬럼에서는 이 섹션을 참고하도록 짧게만 표기한다. [PR #29](https://github.com/AI-HealthCare-04/AH_04_02/pull/29)(monitoring_router/care_router 인가 적용)가 이 문서 작성 도중 2026-07-13에 병합됐다 — 리뷰 과정에서 잔여 IDOR(초대 없이 임의 환자 자가 연결)를 발견해 같은 PR에서 즉시 수정·재검증까지 마친 뒤 병합됐음을 확인하고, v7 문서를 그 최종 병합 상태 기준으로 갱신했다.

## 3. RESTful 일관성 — `care_router`의 prefix 누락

**발견**: `auth`/`records`/`ocr`/`rag`/`monitoring`/`chat` 6개 라우터는 라우터명과 일치하는 prefix를 쓰지만, `care_router`(`APIRouter(tags=["Care"])`)만 prefix가 없어 `/assessments`, `/invitations`, `/notification-settings`, `/patients/{id}/invitations`가 다른 라우터와 다른 규칙으로 루트에 노출된다.

**결정**: 이번 버전에서 코드를 고치지는 않되(문서 버전업 범위 밖), 멘토링에서 요청받은 "RESTful 원칙에 맞춰 작성"을 지키기 위해 이 불일치를 문서 상단에 명시하고 다음 버전에서 prefix 정리를 검토하도록 남겼다.

## 4. PII 암호화 적용 여부 명시

**발견**: `patients.name_encrypted`/`phone_encrypted`(Fernet 대칭키) + `phone_hash`(HMAC-SHA256, 조회용)로 저장되고, 응답 시에는 `.name`/`.phone` 프로퍼티가 투명하게 복호화해 평문으로 내려준다. 다만 `Caregiver.manager_name`/`manager_phone`(단체 담당자 연락처)과 `Invitation.invited_phone`은 암호화 범위 밖에 있다.

**결정**: 멘토링 요청사항인 "개인정보 암호화 적용 여부"를 1·2절에 명시적인 PII 문단으로 추가했다. 특히 `Invitation.invited_phone` 평문 저장·응답은 PII 정책의 사각지대이므로 "보안 주의"로 강조 표시했다.

## 5. 구현/미구현 구분을 절마다 명시

**발견**: v6의 기능 중 상당수(회원 탈퇴, 비밀번호 재설정·계정 잠금, 돌봄관계 해제 승인 워크플로, OCR 재시도 전용 엔드포인트, 오타 제안, 가이드 캐싱·재생성·TTS, 알림 실제 발송, 교육·추적관리 전체)가 구현되지 않았다.

**결정**: 표의 "구현" 컬럼에 완료/부분/미구현을 표기하고, 절 끝에 "미구현 항목" 목록을 두어 한눈에 파악할 수 있게 했다(멘토링 요청 2.1항 "구현 여부 및 미구현 여부" 반영). 요구사항_정의서_v8에서 REQ별로 다시 한번 구현여부를 종합 정리할 예정이다.

## 6. (후속 수정) 서브에이전트 2라운드 교차검증으로 발견한 오류 6건

**배경**: 요구사항_정의서_v8의 백로그 오류("개인/단체 회원가입 구분은 설계 미확정" — 실제로는 이미 구현됨)를 계기로 API명세서_v7도 서브에이전트 1라운드 감사 → 2라운드 독립 재검증으로 전수 재검토했다(사용자 지시). 기관가입 관련 서술(39~43행)은 이미 정확했으나, 그 외 다음 6건의 실제 오류를 발견해 정정했다.

1. **"상태 코드" 절 자기모순**: "생성도 `200`으로 통일"이라 적었으나 같은 문서에 `POST /auth/signup`이 스스로 `201`을 명시하고, `auth_router.py`(`status_code=status.HTTP_201_CREATED`)도 실제로 201을 반환한다. "대부분 200, `POST /auth/signup`만 예외로 201"로 정정.
2. **502/503/504 상태 코드 누락**: `ocr_router.py`가 CLOVA 타임아웃(504)·연결실패(503)·HTTP오류(502)를 실제로 반환하는데 "상태 코드" 절엔 500까지만 있었다. 추가.
3. **`POST /assessments` 표 행 파손**: 다른 행은 7컬럼인데 이 행만 "응답" 컬럼이 빠져 6컬럼이었다. `care_router.py`의 `response_model=CareLevelAssessment`를 근거로 `200 CareLevelAssessment` 추가.
4. **문서화 누락 엔드포인트 5종 추가**: `GET /monitoring/patients`, `PATCH /monitoring/patients/{id}`, `DELETE /monitoring/patients/{id}`, `GET /monitoring/caregivers`, `POST /rag/test/{record_id}` — 전부 코드엔 있지만 v7 어디에도 문서화돼 있지 않았다(전체 grep으로 재확인). 1절·5절 표에 추가.
5. **"미구현 항목"의 `GET /users/me` 서술 정정**: "애초에 '나'를 식별할 인가 수단이 없다"는 이유로 미구현이라 적었으나, PR #29 이후 `get_current_actor`/`get_current_caregiver`가 생겨 `GET /monitoring/patients`·`GET /monitoring/caregivers`가 사실상 그 역할을 한다. 실제 미구현은 "보호자 본인 정보 수정·삭제 엔드포인트 없음"뿐이라고 좁혀 정정.
6. **면책 고지(REQ-032) 서술 오류**: "매 응답에 disclaimer 고정 문구 포함"이라 적었으나, `rag_router.py`의 `_generate_via_rag_prototype()`이 `rag-prototype`이 생성한 `disclaimer` 필드를 추출하지 않아 API 응답엔 포함되지 않는다 — 실제로는 프론트 하드코딩. `ERD_v8`의 REQ-032 정정과 동일한 사실을 반영.

## 팀에 설명할 핵심 결정

1. **v6은 폐기하지 않고 "목표 설계 참고 자료"로 남긴다** — v7이 실제 구현 기준이지만, v6의 세분화된 설계(돌봄관계 해제 워크플로, 교육관리 등)는 향후 그 기능을 만들 때 그대로 참고할 수 있다.
2. **인가 갭은 v7 전체에 영향을 주는 사안이라 절마다 반복하지 않고 최상단 한 곳에서 설명한다** — 실제 코드에서도 이 갭이 라우터별 개별 이슈가 아니라 시스템 전체의 공통 원인(토큰 검증 미적용)이기 때문에, 문서 구조도 그 실제 원인 구조를 따라간다.
3. **PR #29(인가 적용) 진행 상황을 문서 작성 중 실시간으로 반영한다** — 처음 v7을 쓸 때는 PR #29가 리뷰 중이라 "전 엔드포인트 인증 X"로 썼는데, 작성 도중 그 PR이 병합돼서 2·3·7절(monitoring_router/care_router)을 O로 다시 갱신했다. 리뷰 과정에서 발견한 잔여 IDOR(보호자가 초대 없이 임의 환자에 자가 연결 가능)도 같은 PR에서 바로 수정·재검증됐음을 확인하고 반영했다. 4·6절(records_router/ocr_router/rag_router/chat_router)은 이 PR 범위 밖이라 여전히 X로 남아있다.
4. **RESTful 일관성 문제(`care_router` prefix 누락)는 이번엔 코드를 고치지 않고 문서에만 기록한다** — 문서 버전업과 코드 리팩터링을 같은 PR에 섞지 않기 위함이며, prefix 변경은 프론트 API 클라이언트 경로까지 함께 바꿔야 하는 별도 작업이라 분리했다.
5. **이전 버전 파일은 수정하지 않고 보존, 이번 개정은 새 버전 파일로 버전업한다.**
