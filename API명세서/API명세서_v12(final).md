# API 명세서 v12(final)

> 기준: `dev` 7f4fcd1 및 PR #153의 알림함 논리 삭제 설계
> 목적: 이 문서는 최종 제공 기능의 개발·연동 기준이다. 버전 간 변경 사유와 제외 범위는 revision log에서 관리한다.

## 1. 공통 규칙

- 기본 형식은 JSON이며, 처방전 사진 업로드만 `multipart/form-data`를 사용한다.
- 인증이 필요한 요청은 `Authorization: Bearer <access_token>`을 사용한다. refresh token은 HttpOnly 쿠키로 전달한다.
- `patient`는 복약관리 대상자, `caregiver`는 보호자·지원인력·기관 계정을 뜻한다.
- 보호자·지원인력 계정은 활성 연결 관계가 있는 복약관리 대상자의 정보만 조회·변경할 수 있다.
- 날짜·시간은 ISO 8601 형식을 사용한다. 다만 코드 전역의 UTC/KST 저장 정책은 아직 하나로 통일되지 않았다. 대부분의 업무 시각은 서버 로컬 시각 기반 `datetime.now()`를 사용하고, 복약 알림 스케줄러는 `_now_kst()`로 한국 시각을 명시한다. 시간대 오프셋이 없는 응답을 모든 API에서 동일한 시간대로 간주해서는 안 된다.
- 이름·전화번호 등 암호화 저장 대상 PII는 API 응답을 만들 때 평문으로 복호화된다. 따라서 응답 구간은 HTTPS로 보호해야 한다. 기관 담당자 필드 `manager_name`, `manager_phone`은 현재 암호화 저장 대상에 포함되지 않는다.
- 삭제된 처방전, 복용 의약품, 알림함 기록은 `deleted_at`이 설정되며 일반 조회에서 제외된다.

### 공통 오류 응답

| 상태 | 의미 |
|---|---|
| 400 | 요청 값 또는 업무 규칙 위반 |
| 401 | 인증 정보 없음·만료·불일치 |
| 403 | 해당 복약관리 대상자에 대한 접근 권한 없음 |
| 404 | 대상 리소스 없음 또는 삭제됨 |
| 409 | 중복 데이터 또는 상태 충돌 |
| 422 | 필드 형식 검증 실패 |
| 500 | 서버 내부 오류 |

## 2. 인증·계정

| Method | Path | 설명 |
|---|---|---|
| POST | `/auth/login` | 복약관리 대상자 또는 보호자·지원인력 로그인 |
| POST | `/auth/token/refresh` | refresh token을 검증하고 access token 재발급 |
| POST | `/auth/switch` | 최근 사용 계정으로 전환 |
| POST | `/auth/switch/forget` | 저장된 계정 전환 정보 해제 |
| POST | `/auth/password-reset/request` | 비밀번호 재설정 코드 발급 |
| POST | `/auth/password-reset/verify` | 재설정 코드 검증 |
| POST | `/auth/password-reset/confirm` | 새 비밀번호 저장 |
| POST | `/auth/verify-password` | 중요 작업 전 현재 비밀번호 확인 |
| POST | `/auth/withdraw` | 계정 즉시 비활성화 및 30일 후 삭제 예약 |
| POST | `/auth/withdraw/cancel` | 삭제 예정일 전 계정 탈퇴 취소 |

계정 탈퇴 후 로그인과 보호 정보 접근은 즉시 차단한다. 삭제 예약일이 지나면 정리 작업이 관련 개인정보를 삭제하고 감사 결과를 `privacy_purge_audits`에 남긴다.

## 3. 복약관리 대상자·보호자 관리

| Method | Path | 설명 |
|---|---|---|
| POST/GET | `/monitoring/patients` | 복약관리 대상자 등록/목록 조회 |
| GET | `/monitoring/patients/check-duplicate` | 복약관리 대상자 중복 확인 |
| PATCH/DELETE | `/monitoring/patients/{patient_id}` | 기본 정보 수정/연결 범위에서 삭제 |
| PUT | `/monitoring/patients/{patient_id}/meal-times` | 아침·점심·저녁 시간 설정 |
| POST/GET | `/monitoring/caregivers` | 보호자·지원인력 등록/목록 조회 |
| GET | `/monitoring/caregivers/check-duplicate` | 보호자·지원인력 중복 확인 |
| PATCH | `/monitoring/caregivers/{caregiver_id}` | 보호자·지원인력 정보 수정 |
| GET | `/monitoring/caregivers/{caregiver_id}/patients` | 연결된 복약관리 대상자 조회 |
| GET | `/monitoring/patients/{patient_id}/caregivers` | 연결된 보호자·지원인력 조회 |
| POST/DELETE | `/monitoring/caregivers/{caregiver_id}/patients/{patient_id}` | 직접 연결/연결 해제 |
| PATCH | `/monitoring/caregivers/{caregiver_id}/patients/{patient_id}/notifications` | 해당 관계의 기기 알림 수신 설정 |

## 4. 초대·연결·알림 설정

| Method | Path | 설명 |
|---|---|---|
| POST | `/invitations` | 전화번호 기반 초대 생성 |
| GET | `/invitations/{token}` | 초대 정보 확인 |
| POST | `/invitations/{token}/accept` | 초대 수락 및 관계 생성 |
| POST | `/invitations/{token}/reject` | 초대 거절 |
| DELETE | `/invitations/{invitation_id}` | 대기 중 초대 취소 |
| GET | `/caregivers/{caregiver_id}/pending-invitations` | 받은 초대 조회 |
| GET | `/trust/relations/notices` | 연결·해제 결과 알림 조회 |
| POST | `/trust/relations/notices/{notice_id}/read` | 관계 알림 읽음 처리 |
| GET/PUT | `/notification-settings` | 인증된 현재 계정의 복약 알림·돌봄 알림·전체 Push 설정 조회/변경 |
| GET | `/trust/relations/pending` | 승인 대기 중인 연결 해제 요청 조회 |
| POST | `/trust/relations/{trust_id}/revocation-approval` | 연결 해제 승인 또는 거절 |
| GET | `/push/vapid-public-key` | Web Push 공개키 조회 |
| POST/DELETE | `/push-subscriptions` | 현재 계정·기기의 Web Push 구독 등록/해제 |

## 5. 처방전 목록·OCR·검토

| Method | Path | 설명 |
|---|---|---|
| POST | `/records` | 처방전 사진 저장 및 OCR 처리 시작 |
| POST | `/records/manual` | 처방전 직접 등록 |
| GET | `/records` | 권한 범위의 처방전 목록 조회 |
| GET | `/records/{record_id}` | 처방전 상세 조회 |
| GET | `/records/{record_id}/image` | 권한 검증 후 처방전 사진 조회 |
| DELETE | `/records/{record_id}` | 처방전과 연결 의약품을 논리 삭제 |
| POST | `/records/{record_id}/medications` | 처방전 의약품 추가 |
| PATCH/DELETE | `/records/{record_id}/medications/{medication_id}` | 처방전 의약품 수정/삭제 |
| POST | `/records/{record_id}/confirm` | OCR 결과 사용자 확인 |
| POST | `/records/{record_id}/request-correction` | 보호자·지원인력의 수정 요청 |
| POST | `/records/{record_id}/mark-reviewed` | 검토 완료 처리 |
| PATCH | `/records/{record_id}/medications/{medication_id}/correct` | 특정 의약품의 수정 내용 반영 |
| PATCH | `/records/{record_id}/pin` | 즐겨찾기 설정/해제 |
| GET | `/records/notices` | 처방전 수정 관련 알림 조회 |
| POST | `/records/notices/{notice_id}/read` | 처방전 알림 읽음 처리 |
| GET | `/ocr/ping` | OCR 서비스 상태 확인 |
| GET | `/ocr/drug-info` | 의약품 정보 검색 |

OCR 결과는 사용자가 확인하기 전 확정 정보로 취급하지 않는다. 용량·횟수·복용 시점 등 필수 값이 비어 있거나 신뢰도가 낮으면 확인 항목으로 표시하며, 연고제의 `소량`처럼 수치가 아닌 용량 표현도 유효한 값으로 처리한다.

## 6. 생활습관 가이드·복약 주의사항 RAG

| Method | Path | 설명 |
|---|---|---|
| GET | `/rag/ping` | RAG 서비스 상태 확인 |
| POST | `/rag/test/{record_id}` | 처방전 기준 가이드 생성·조회 |

- 입력은 처방전의 진단명과 확정 의약품이다.
- 의약품 정보는 공공 API에서 구축한 마스터 데이터와 벡터 저장소를 검색한다.
- 생활습관 정보는 질병관리청 출처 기반 문서를 검색한다. 질병명 정규화와 유의어 확장 후 검색하고, 검색 결과가 충분하지 않으면 근거 없는 내용을 생성하지 않는다.
- 결과는 `복약 주의사항`, `생활습관 가이드`, `출처 참조`로 구분한다. 같은 진단·의약품·데이터 버전 조합은 `guide_cache`를 사용한다.
- 검색과 LLM 생성 과정은 Langfuse trace로 연결해 입력, 검색 문서, 응답, 지연 시간을 추적한다.

## 7. 챗봇

| Method | Path | 설명 |
|---|---|---|
| GET | `/chat/questions` | 시작 질문 목록 조회 |
| POST | `/chat/ask` | 질문에 대한 답변 생성 |
| POST | `/chat/ask/stream` | 답변 스트리밍 생성 |
| GET | `/chat/history` | 복약관리 대상자의 대화 이력 조회 |

챗봇은 최근 처방전을 기본 의료 맥락으로 사용하고 답변에 그 기준을 명시한다. 시스템 프롬프트·내부 정책·개발 지시를 요구하는 질문에는 RAG 검색을 수행하지 않는다. 의료 답변은 처방전, 확정 의약품, 검색 근거 범위 안에서 생성하고 진단이나 처방을 대신하지 않는다는 안내를 포함한다. RAG 검색과 LLM 생성은 하나의 Langfuse trace에서 확인할 수 있다.

## 8. 복용 의약품·복약 일정·복약 기록

| Method | Path | 설명 |
|---|---|---|
| POST/GET | `/patients/{patient_id}/medications` | 복용 의약품 등록/목록 조회 |
| GET/PATCH/DELETE | `/patients/{patient_id}/medications/{medication_id}` | 복용 의약품 상세/수정/논리 삭제 |
| POST | `/patients/{patient_id}/medications/{medication_id}/schedules` | 의약품 기준 복약 일정 생성 |
| POST/GET | `/patients/{patient_id}/medication-records` | 복약 수행 기록 생성/조회 |
| POST/GET | `/monitoring/schedules` | 복약 일정 생성/조회 |
| PATCH/DELETE | `/monitoring/schedules/{schedule_id}` | 복약 일정 수정/삭제 |
| POST/DELETE | `/monitoring/schedules/{schedule_id}/check` | 복약 완료 표시/취소 |
| GET | `/monitoring/logs` | 복약 기록 조회 |
| GET | `/monitoring/today` | 오늘의 복약 일정과 수행 상태 조회 |
| GET | `/monitoring/patients/{patient_id}/known-drugs` | 등록된 의약품명 자동완성 |

## 9. 알림함

| Method | Path | 설명 |
|---|---|---|
| GET | `/monitoring/patients/{patient_id}/notifications` | 삭제되지 않은 복약 알림 기록 조회 |
| POST | `/monitoring/patients/{patient_id}/notifications/acknowledge` | 화면에 표시한 알림을 확인 처리 |
| DELETE | `/monitoring/patients/{patient_id}/notifications/{notification_id}` | 알림 한 건 논리 삭제 |
| POST | `/monitoring/patients/{patient_id}/notifications/delete` | 선택한 여러 알림 논리 삭제 |
| DELETE | `/monitoring/patients/{patient_id}/notifications` | 확인한 알림 또는 전체 알림 논리 삭제 |

삭제 요청은 `notification_logs.deleted_at`을 설정한다. 삭제된 기록은 알림함 목록, 확인 처리, 삭제 대상 조회에서 제외하되 감사와 장애 분석을 위해 데이터베이스에 보존한다. 일괄 삭제 요청은 ID 배열과 `delete_all` 또는 `acknowledged_only` 조건 중 하나를 사용한다.
