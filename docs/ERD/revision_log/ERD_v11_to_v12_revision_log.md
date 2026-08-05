# ERD v11 → v12(final) Revision Log

## 기준

- 코드 기준: `dev` 7f4fcd1
- 병합 전 최종 반영 범위: PR #153 `notification_logs.deleted_at`
- v12(final)의 Markdown과 DBML을 같은 데이터 모델로 맞췄다.

## 변경 사항

1. 테이블을 계정, 연결, 처방전, 가이드, 복약, 알림, 챗봇, 감사 영역으로 다시 분류했다.
2. `caregiver_patients.notifications_enabled`를 관계별 기기 알림 수신 설정으로 설명하고 `notification_settings`와의 차이를 명확히 했다.
3. `medical_records`와 `patient_medications`의 `deleted_at`을 **논리 삭제**로 용어 통일하고 일반 조회 제외 규칙을 명시했다.
4. PR #153을 반영해 `notification_logs.deleted_at`을 Markdown과 DBML에 추가했다. 알림함에서 삭제한 행은 목록·확인·후속 삭제 조회에서 제외하되 감사와 장애 분석을 위해 보존한다.
5. 공공 데이터 마스터 자체는 애플리케이션 파일·벡터 저장소로 관리되므로 업무 DB 테이블로 표현하지 않는다는 경계를 유지했다. 생성 결과와 캐시는 `guide_results`, `guide_cache`에 저장한다.
6. 변경 과정 설명과 요구사항별 구현 상태표를 본문에서 제거하고 최종 데이터 구조와 제약만 남겼다.

## 구현 취소로 삭제한 개념

- REQ-005~REQ-007의 자가진단 및 care level 테이블·관계
- REQ-040~REQ-044의 교육 콘텐츠·교육 추적 테이블
- REQ-028~REQ-029의 별도 건강 측정 장치·측정값 테이블
- REQ-026d의 음성 알림 설정 데이터

이 개념들은 최종 업무 데이터 모델에 포함하지 않으며 v12(final) 본문과 DBML에 빈 테이블이나 예정 구조로 남기지 않았다.
