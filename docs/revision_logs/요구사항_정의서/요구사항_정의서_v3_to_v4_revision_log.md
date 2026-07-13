# 요구사항 정의서 수정 검토 기록

이 문서는 `요구사항_정의서_v3.xlsx`에서 `요구사항_정의서_v4.xlsx`로 변경하며 반영한 요구사항 수정사항과 3번 시트 변경·추적성 내용을 분리해 기록한 변경 이력이다.

## 1번 시트 수정안

### REQ-035 탈퇴 취소 감사 로그 보완

리뷰 코멘트: "30일 이내 탈퇴 취소 API가 있습니다. 취소 시 감사 레코드를 삭제하는지, cancelled로 바꾸는지 정의되지 않았습니다."

결정: cancelled로 남긴다(로그 유지).

비고를 "확인 모달, 30일 내 취소 지원"에서 "확인 모달, 30일 내 취소 지원; 취소 시 감사 레코드(privacy_purge_audits)는 삭제하지 않고 cancelled로 보존(v4)"로 갱신한다.

## 3번 시트 변경·추적성 반영 내역

| 검토항목 | 1번 시트 반영 결과 | 연계 문서 | 검증 상태 |
|---|---|---|---|
| 탈퇴 취소 감사로그 | REQ-035: 30일 내 탈퇴 취소 시 privacy_purge_audits 레코드는 삭제하지 않고 purge_status=cancelled로 보존(로그 유지) | privacy_purge_audits.purge_status/cancelled_at; POST /users/me/withdrawal/cancel | 반영 완료 |
| REQ-028 추적표 누락 | ERD 요구사항 추적표에서 REQ-028 행 누락 발견, medical_records.ocr_completed_at·guide_results.generated_at 기준으로 행 추가 | ERD 요구사항 추적 섹션; GET /medical-records/{record_id} | 반영 완료 |
| 임시코드·안내닫기 enum 검토 | auth_temporary_codes.purpose, care_level_notice_dismissals.notice_type enum 값이 1개뿐이나 향후 용도 확장(비밀번호 재설정, 가입 인증 등) 대비를 위해 현행 enum 구조 유지 결정 | ERD auth_temporary_codes / care_level_notice_dismissals | 검토 완료(변경 없음) |

## 팀에 설명할 핵심 결정

1. 탈퇴 취소는 사용자 상태만 복구하고, 감사 기록은 삭제 대신 `cancelled`로 남겨 탈퇴·취소 시도 이력을 추적할 수 있게 한다.
2. REQ-028은 원래 요구사항 정의서(1번 시트)에는 존재했고, ERD 추적표에서만 누락되어 있었으므로 ERD 쪽만 수정한다.
3. enum 값이 1개인 필드는 향후 확장 가능성을 감안해 지금은 상수화하지 않는다.
