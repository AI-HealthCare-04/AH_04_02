# 밸리데이션 결과 종합 (2026-07-09)

- **작성**: 김영혜
- **목적**: 2026-07-08 멘토링에서 요청된 "밸리데이션 돌리고 deviation log 작성 → CAPA 수립" 흐름의 1차 종합. 현재는 통합 대시보드/CI가 없어 4곳에 흩어져 있는 테스트·회귀·검증 결과를 한 문서로 모음.
- **기준 브랜치**: `dev`(`232f91d`) — PR #18(PII 암호화), #19(챗봇·약물상세 버그수정)는 아직 미병합이라 별도 표시함.

## 1. 결과 요약

| 영역 | 방법 | 결과 | 실행 명령 |
|---|---|---|---|
| RAG 파이프라인 | `pytest`(rag-prototype) | **29/29 통과** | `cd rag-prototype && pytest -v` |
| OCR 파싱 회귀 | `batch_regression.py`(24개 목업) | **포맷 인식 24/24(100%), 검증조건 39/40(97.5%)** | `cd backend && python scripts/batch_regression.py` (스크립트 내 `BACKEND` 경로를 본인 환경에 맞게 수정 필요 — 순현님 로컬 경로로 하드코딩돼 있음) |
| drug_class 분류 정확도 | 위 회귀 스크립트 포함 | **8/9(88.9%)** — 잔여 1건은 HIRA/e약은요 데이터 없을 때 알려진 폴백 한계 | 〃 |
| drug_code 매칭(실 파이프라인) | CLOVA OCR e2e 1건 | **4/4(100%)** | `docs/etc/results_soonhyun.md` §11 참고 |
| review_required 오탐율 | 〃 | **0/4(0%)** | 〃 |
| 백엔드 PII/보안(신규, PR #18) | `pytest`(backend/tests) | **14/14 통과** | `cd backend && pytest tests/ -v` (PR #18 병합 전엔 해당 브랜치에서만 실행 가능) |
| 챗봇·약물상세 버그(PR #19) | 코드 분석 + `TestClient` 재현 | **원인 확정·수정 완료**, 실제 real 환경 재현은 소정님 확인 대기 | `docs/troubleshooting_log/troubleshooting-log.md` 하단 2건 참고 |

## 2. 편차(Deviation) 종합 — 상세는 각 원문서 링크 참고

| ID | 편차 | 심각도 | 상태 |
|---|---|---|---|
| D1 | RAG 배치 처리 진입점 부재(약 여러 건 처리 함수 없음) | 중 | ✅ 해결 (`rag-prototype/docs/deviation_log/deviation-log-2026-07-06-ocr-rag-integration.md`) |
| D2 | OCR 개별 신뢰도가 RAG 최종 응답에 반영 안 됨(가장 심각, 실측 확인) | **높음** | ✅ 해결 (〃) |
| D3 | OCR/RAG `review_required` 필드명 충돌 | 낮음 | ✅ 해결, rename 대신 `review_flags` 도입 (〃) |
| D4 | 생활지침 커버리지 4개 질환 한정 | 정보성(버그 아님) | 문서화만, 3주차 커버리지 확장 예정 |
| D5 | RAG가 "의약품 허가정보" API로 오인하고 있던 게 실제로는 e약은요였음 | 중 | ✅ 해결, HIRA 약가마스터로 대체 (`rag-prototype/docs/deviation_log/deviation-log-2026-07-08-medication-data-source-capa.md`) |
| D6 | `rag_router.py`의 `source_refs` 매핑이 새 HIRA 필드 누락(배포 전 발견) | 중 | ✅ 해결 (〃) |
| D7 | HIRA CSV가 `rag-prototype/data`·`backend/data` 두 곳에 중복 보관 | 낮음(용량/일관성) | ✅ 해결, PR #14 (병합 완료) |
| D8 | `Result.tsx`/`PrescriptionDetail.tsx`가 RAG stub/real 응답 모양 차이로 크래시 | **높음**(실사용 크래시) | ✅ 해결, PR #16 (병합 완료). 이후 Figma 재구성으로 로직이 `MedGuide.tsx`로 이동하며 재발 → PR #13 폐기 후 재작업 |
| D9(신규) | `DrugInfo.tsx`가 D8 수정 대상에서 빠져 real 모드에서 주의사항 미표시 | 중 | ✅ 해결, PR #19(미병합) |
| D10(신규) | 챗봇(`/chat/ask`) 실LLM 호출이 axios 전역 10초 타임아웃보다 느려 "무응답"으로 보임 | **높음**(실사용 체감 장애) | ✅ 해결, PR #19(미병합) |

## 3. Corrective / Preventive Action 요약

**Corrective(즉시 조치)**
- D8/D9: stub↔real 두 응답 모양을 처리하는 방어 로직을 `Result.tsx`/`MedGuide.tsx`/`DrugInfo.tsx` 3개 화면 모두에 적용(PR #16, #19).
- D10: LLM 호출 엔드포인트(`/chat/ask`)만 타임아웃 30초로 개별 연장(PR #19).
- D6: `rag_router.py`의 `source_refs` 필드 매핑 즉시 보완.
- D7: HIRA CSV 중복 제거, `backend/data/` 한 곳으로 통일(PR #14).

**Preventive(재발 방지)**
- `docs/etc/rag-real-response-sample.md`에 stub vs 실제 응답 모양 차이표 유지 — 새 화면 추가 시 이 표로 "이 필드 stub 전용 아닌가?" 확인하는 걸 습관화(D8/D9 재발 원인이 "새 화면이 이 문서를 안 보고 만들어짐"이었음).
- `rag/contract.md`에 데이터 소스 3종(e약은요/허가정보/HIRA)의 원천·용도·중복 관계 명시(D5).
- 외부 API(LLM 등)를 동기 호출로 감싸는 엔드포인트는 공용 클라이언트의 전역 타임아웃에 의존하지 않고 개별 타임아웃을 지정하는 걸 관례로 삼음(D10).
- rag-prototype↔backend처럼 스키마와 소비 코드가 물리적으로 분리된 구조에서는, 스키마에 필드 추가 시 소비 지점 grep으로 확인하는 걸 체크리스트화(D6 재발 원인).

## 4. 아직 밸리데이션 안 된 영역 / 남은 이슈

- **개인정보 암호화(PII, PR #18)** — 단위 테스트·`TestClient` e2e는 통과했지만, `monitoring_router.py` 등 다른 라우터가 여전히 `caregiver_id`/`patient_id`를 쿼리파라미터로 신뢰하는 구조라 **인가(authorization) 검증은 이번 범위에 없음** — 별도 논의 필요(2026-07-09 팀 결정: 지금은 보류).
- **생활지도 DB(REQ-004)** — 국가건강정보포털 API 미수신으로 보류.
- **CI/자동화** — 이 문서 자체가 "매번 사람이 수동으로 모아야 하는" 상태라는 증거이기도 함. 여유 생기면 최소한 `pytest`(rag-prototype, backend) 두 개만이라도 GitHub Actions로 자동화하는 걸 제안.
- **OCR 회귀 스크립트 이동성** — `batch_regression.py`의 하드코딩된 경로(`/Users/admin/backend`)를 상대경로로 바꿔서 누구나 바로 돌릴 수 있게 하는 게 필요.

## 5. 참고 문서

- `rag-prototype/docs/deviation_log/deviation-log-2026-07-06-ocr-rag-integration.md`
- `rag-prototype/docs/deviation_log/deviation-log-2026-07-08-medication-data-source-capa.md`
- `docs/etc/results_soonhyun.md` (OCR 정확도, e2e 통합테스트)
- `docs/troubleshooting_log/troubleshooting-log.md` (UI 버그 로그, 챗봇/약물상세 건 포함)
- PR #14, #16, #18, #19
