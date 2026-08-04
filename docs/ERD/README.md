# ERD

전체 관계도(ERD)는 아래 링크에서 다이어그램으로 확인할 수 있습니다.

https://dbdiagram.io/d/Medication-guide-6a71a41135ee2e87b0292440

원본 스키마 정의는 `ERD_v12(final).dbml`이며, 이 파일 내용을 dbdiagram.io 편집창에 붙여넣으면 위 다이어그램을 다시 만들 수 있습니다. 테이블·관계에 대한 설명은 `ERD_v12(final).md`를 참고하세요.

## 정규화 수준

모든 테이블이 단일 컬럼 surrogate PK(`id`)를 사용해 복합키가 없고, 대부분의 FK가 정상적으로 정규화된 참조 관계라 핵심 트랜잭션 테이블들은 실질적으로 **3NF** 수준입니다.

다만 다음은 오류가 아니라 의도적인 설계 트레이드오프로 정규화를 깨뜨린 부분입니다:

- `channels`, `days_of_week`, `drug_names`, `source_refs`, `medication_guide`/`lifestyle_guide` — 배열/객체를 JSON 문자열 하나로 저장(엄밀히는 1NF 위반이나, 별도 자식 테이블을 둘 정도는 아닌 선택적 부가 데이터라 실용적으로 이렇게 처리)
- `revocation_notices.patient_name`/`counterpart_name` — 환자 이름을 알림 테이블에 스냅샷으로 중복 저장(나중에 이름이 바뀌거나 계정이 삭제돼도 그 시점 알림 기록은 그대로 남아야 하므로 의도적 중복)
- `guide_cache`, `ocr_results.matched_drug_name`/`match_score` — 캐시·계산 결과를 그대로 저장(성능을 위한 의도적 비정규화)
