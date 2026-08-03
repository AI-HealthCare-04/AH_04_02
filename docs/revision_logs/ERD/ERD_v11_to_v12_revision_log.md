# ERD 수정 검토 기록 — v11 → v12

> 버전: v11 → v12 · 날짜: 2026-08-03 · 작성자: 김영혜(Claude 세션)

## 변경 배경

API명세서_v12(final)와 동일한 근거(v11 이후 dev 100개 커밋)로 스키마를 재검토했다. `models.py` 전체 diff와 alembic 신규 마이그레이션 diff를 교차 확인해, 이번 100개 커밋 동안 스키마 변경이 정확히 1건뿐임을 확인했다.

## 주요 변경

- **신규 테이블**: 없음. 테이블 수 24개 그대로 유지.
- **신규 컬럼**: `caregiver_patients.notifications_enabled`(bool, NOT NULL, 기본값 true) 1개뿐 — (보호자,환자) 관계 단위 push 알림 on/off. 기존 환자 단위 `notification_settings`(모든 보호자 공유)와는 별개 개념(커밋 `24dbb8f`).
- **변경된 컬럼**: 없음(타입/제약/nullable/이름 변경 전부 없음).
- **관계선(mermaid erDiagram)**: `notifications_enabled`는 FK가 없어 관계선 추가 불필요 — 필드 블록에 한 줄만 추가.
- **v11 자체 문서 갭 보정**: `invitations.invited_phone_hash`(2026-07-22 추가, v11 당시 head보다도 이전 마이그레이션)가 v11 필드 블록에서 누락돼 있던 것을 이번에 추가.
- **alembic head**: `46e60aff6632`(부모 `48230e8ff2b4`=v11 당시 head) — v11 이후 순수 신규 마이그레이션 정확히 1개. 전체 마이그레이션 파일 37개.
- **삭제된 테이블**: 없음(`care_level_assessments`는 v11에서 이미 삭제된 상태 유지).

## 검증

- `backend/models.py` 전체(24개 테이블 클래스 전부)를 v11 mermaid 블록과 1:1 재대조.
- `cd backend && uv run alembic heads` — 단일 head 확인.
- 정확성 비평(alembic 마이그레이션 생성일과 엔드포인트 구현 커밋일 분리 서술, `notification_settings` 표기 casing 등)을 1라운드 반영.

## 남은 후속 과제

- `caregiver_patients.notifications_enabled`를 실제로 읽고 쓰는 라우터 핸들러·알림 발송 로직·프론트 "알림 관리 페이지" 라우팅은 이번 감사가 스키마 레벨(models.py+alembic)로만 확인한 것이라, 엔드투엔드 동작 확인은 API명세서_v12(final)/요구사항_정의서_v12(final)(REQ-082)에서 별도로 참고할 것.
- 이번 v12는 ERD 감사 1건 + 정확성/일관성 비평 1라운드만 거쳤다(원래 계획한 3라운드 중 세션 한도 문제로 1라운드만 완주). 다음 버전에서 추가 검증 라운드를 거치는 것을 권장한다.
- REQ-048(챗봇 진입버튼 항상노출) 관련 문서-코드 모순은 API명세서_v12(final)·요구사항_정의서_v12(final)에서 플래그했다 — ERD 자체에는 영향 없음.
