# API 명세서 수정 검토 기록 — v7 → v8

v7→v8: 권순현 담당 라우터 갱신 (PR #56/59/60 반영)

## 변경 요약

| 절 | 변경 내용 | 관련 PR |
|---|---|---|
| 인가 섹션 | 4·5절(records/ocr/rag) 인가 적용 완료로 갱신, 6절(chat)만 미적용 | #56/#59/#60 |
| 2절 돌봄관계 | `DELETE /trust/relations/{id}`, `POST .../revocation-approval` 추가 (REQ-004) | #56 |
| 3절 상태·복약가능여부 | `POST .../dismiss-alert` 추가, REQ-007a 미구현 해소 | #56 |
| 4절 진료기록·OCR | records_router 전체 인가 X→O, `PATCH .../medications/{id}` 추가(REQ-047), GET /ocr/drug-info 응답 5필드 확장 | #59 |
| 5절 가이드 | confirm·rag/test 인가 X→O, `cached`/`cache_expires_at` 응답 필드 추가, 캐싱 미구현→완료 | #60 |
| 상태 코드 | `403` 항목 추가 | — |