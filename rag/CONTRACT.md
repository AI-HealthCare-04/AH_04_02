# OCR ↔ RAG 인터페이스 계약

두 파트가 다른 브랜치에서 독립적으로 개발되기 때문에(OCR: `origin/feature/ocr-day1-setup_soonhyun`의
`AH_04_02_soonhyun/ocr_interface.py`, RAG: 이 브랜치의 `rag/`), 코드가 서로를 import해서
타입 체크로 강제할 수 없다. 이 문서가 두 파트가 합의한 필드 의미의 단일 참조다.

> 배경: 2026-07-06, RAG 쪽에서 실제 OCR 산출물(Mock + 실측 CLOVA 샘플)로 통합 테스트를 하다가
> OCR의 개별 약 신뢰도가 RAG 최종 응답에 전혀 반영되지 않는 문제를 발견해 이 문서를 만들었다.
> 자세한 경과는 `docs/deviation-log/2026-07-06-ocr-rag-integration.md` 참고.
>
> 6번 항목(의약품 제품허가정보 API)은 OCR↔RAG 경계 얘기는 아니지만, "왜 이 API를 안 쓰기로
> 했는지 + 나중에 필요하면 어떻게 복원하는지"를 팀이 나중에 다시 찾아보기 쉽게 여기 같이 적어둔다.

## 1. 필드 매핑

| OCR `MedicationItem` (dataclass) | RAG `MedicationInput` (pydantic) | 비고 |
|---|---|---|
| `drug_name: str` | `drug_name: str` | 상품명(제품명) 기준. 짧은 이름(예: "암로디핀")으로 옴 — RAG가 MFDS 실시간 조회/유사도 검색으로 폴백 처리 |
| `dosage: str` | `dosage: str = ""` | 예: "5mg" |
| `frequency: str` | `frequency: str = ""` | 예: "1일 1회" |
| `diagnosis: str` | `diagnosis: str = ""` | **콤마로 여러 질환이 join될 수 있음** (예: "고혈압, 제2형 당뇨병"). RAG는 부분 문자열 매칭으로 여러 질환을 동시에 인식한다 (`rag_chain.DIAGNOSIS_DISEASE_ALIASES`) |
| `drug_class: str = ""` | `drug_class: str = ""` | 약효분류, situation 텍스트에만 사용, 구조화 매칭 없음 |
| `confidence: float = 0.0` | `confidence: float = 0.0` | **항상 float, 키 생략 없음** (None 아님). 아래 2번 참고 |

`OCRResult.medications: list[MedicationItem]` → RAG는 `rag_chain.generate_guides_from_medications()` /
`generate_guides_from_ocr_result()`로 리스트를 받아 항목별 `GuideResponse` 리스트를 반환한다
(항목 하나 실패해도 나머지는 격리되어 정상 반환됨).

## 2. `confidence` 임계값 — 두 개의 별개 상수

| 임계값 | 값 | 의미 | 위치 |
|---|---|---|---|
| OCR `_apply_review_flag` threshold | 0.80 | `OCRResult.overall_confidence`(처방전 전체 평균)가 이 미만이면 `OCRResult.review_required=True` (REQ-011) | `ocr_interface.py` |
| RAG `OCR_CONFIDENCE_REVIEW_THRESHOLD` | 0.80 (OCR과 동일 값, 의도적 중복) | `MedicationItem.confidence`(**개별 약** 신뢰도)가 이 미만이면 해당 약의 `GuideResponse.review_required=True` | `rag/config.py` |
| RAG `SELF_CONSISTENCY_SIMILARITY_THRESHOLD` | 0.75 | LLM 답변 self-consistency 점수 임계값. **위 두 confidence 임계값과 의미가 완전히 다름** — 혼동 금지 | `rag/config.py` |

**왜 RAG가 confidence를 다시 체크하는가**: OCR의 `review_required`는 `overall_confidence`(전체 평균)만
보기 때문에 개별 약의 저신뢰를 놓칠 수 있다. 실측 사례(Mock provider): 아스피린 0.92 + 로자탄 0.78 →
평균 0.85 → `OCRResult.review_required=False`. 하지만 로자탄은 OCR 자체 기준(0.80)으로도 검토 대상이다.
RAG의 개별 confidence 체크는 새 기능이 아니라 **이 판정 한계에 대한 보완 통제(compensating control)**다
(`rag/rag_chain.py`의 `_merge_ocr_confidence`).

**엔진별 특성**:
- Tesseract 폴백은 신뢰도를 제공하지 않아 모든 항목이 `confidence=0.0`으로 고정된다 → RAG는 이를 "unavailable"로 분류해 항상 검토 대상으로 fail-safe 처리한다 (`review_flags: ["ocr_confidence_unavailable"]`).
- CLOVA는 `overall_confidence`를 모든 항목에 동일하게 복제해서 채운다 → CLOVA 경로에서 RAG의 "개별" 체크는 사실상 처방전 전체 신뢰도 체크와 같다 (무해하지만 개별성은 없음).
- Mock provider만 항목별로 서로 다른 실제 값을 준다.

## 3. `review_required` — 이름은 같지만 두 개의 다른 개념

| 필드 | 의미 | 계산 기준 |
|---|---|---|
| `OCRResult.review_required` (OCR) | **추출** 신뢰도가 낮아 사람이 원본 이미지를 다시 봐야 함 | `overall_confidence < 0.80` |
| `GuideResponse.review_required` (RAG) | **생성된 가이드**를 사람이 검토해야 함 (통합 플래그) | 아래 `review_flags` 중 하나라도 있으면 True |

두 필드를 rename하지 않기로 결정했다 (OCR 계약은 동결이라 못 바꾸고, RAG 쪽 rename은 `cli.py`의
`model_dump()` JSON 출력·기존 소비자·테스트를 깨뜨림). 대신 `GuideResponse.review_flags: list[str]`로
사유를 기계 판독 가능한 코드로 구분한다:

| 코드 | 의미 |
|---|---|
| `no_citation` | LLM이 참고자료를 하나도 인용하지 않음 |
| `low_self_consistency` | 동일 질의 반복 생성 결과가 서로 낮게 일치함 |
| `ocr_low_confidence` | OCR 개별 인식 신뢰도가 0.80 미만 (0.0 초과) |
| `ocr_confidence_unavailable` | OCR 개별 인식 신뢰도가 0.0 (Tesseract 등 미제공) |
| `dry_run` | `OPENAI_API_KEY` 미설정으로 LLM 생성을 건너뜀 |
| `generation_error` | 배치 처리 중 해당 약 하나의 가이드 생성이 예외로 실패 |
| `dur_taboo_warning` | 같은 처방전의 다른 약과 DUR 병용금기 관계가 확인됨 (`GuideResponse.dur_warnings` 참고, §6 DUR 항목) |

**다운스트림(`ai_worker/` 등)에서 두 `review_required`를 함께 로깅/병합할 때는 반드시 `ocr_review_required`
(OCR용) / `rag_review_required`(RAG용)처럼 접두어를 붙여 구분할 것.** 같은 키로 덮어쓰지 말 것.

## 4. 생활지침(`lifestyle_guidelines.json`) 커버리지

현재 4개 질환만 커버한다: 고혈압(`hypertension`) / 당뇨병(`diabetes`) / 이상지질혈증(`dyslipidemia`) /
만성콩팥병(`chronic_kidney_disease`) — 별칭 매칭 규칙은 `rag_chain.DIAGNOSIS_DISEASE_ALIASES` 참고.

실제 OCR 목업 결과에는 "관상동맥질환", "위염", "골관절염", "불면증", "무릎관절증" 등 커버 밖 진단명도
나온다. 이 경우 `GuideResponse.lifestyle_source_refs`가 빈 배열로 나오는 것이 **의도된 정상 동작**이다
(커버되지 않는 질환에 대해 근거 없이 지어내지 않기 위함). 버그가 아니다 — 커버리지를 넓히려면
`data/lifestyle_guidelines.json`과 `DIAGNOSIS_DISEASE_ALIASES`를 함께 확장할 것.

## 5. 계약 테스트 픽스처 갱신 프로세스

OCR 모듈이 다른 브랜치에 있어 RAG 쪽에서 직접 import해 테스트할 수 없다. 그래서
`tests/contracts/ocr_sample_output.json`에 OCR 실제 산출물(Mock provider)을 복사해두고
`tests/contracts/test_ocr_contract.py`가 이를 검증한다.

- **지금 (머지 전)**: OCR 필드가 바뀌면 이 픽스처가 수동으로 stale해질 수 있다. OCR 쪽 필드 변경 PR에는
  "RAG 담당에게 알리고 `tests/contracts/ocr_sample_output.json` 갱신 필요 여부 확인" 체크박스를 둔다.
- **두 브랜치가 `dev`로 머지된 뒤**: 이 픽스처 파일 대신 OCR 모듈이 소유한 정본 샘플
  (`AH_04_02_soonhyun/sample_ocr_output.json` 또는 별도 `samples/medication_item.json`)을 직접 읽도록
  `test_ocr_contract.py`를 전환한다. producer(OCR)가 정본을 유지하고, consumer(RAG)는 그것을 읽기만
  하는 방향이 되어야 필드가 바뀌었을 때 자동으로 감지된다.
- 값 비교만으로는 부족하다: `MedicationInput`은 pydantic 기본 `extra="ignore"`라 OCR이 필드를
  추가/삭제/rename해도 조용히 무시된다. 그래서 `test_medication_input_fields_are_subset_of_ocr_output_keys`가
  "RAG가 필요로 하는 필드 키 집합 ⊆ OCR 산출물의 키 집합"을 별도로 검증한다.

## 6. 의약품 제품허가정보 API (`DrugPrdtPrmsnInfoService07`) — [2026-07-14] 활용신청 승인, 재활성화

2026-07-08, "의약품 허가 기반으로 데이터 구축하려던 원래 의도"를 확인하던 중 찾아서 실제
서비스 키로 테스트까지 마쳤지만, **e약은요 + HIRA 약가마스터만으로 우선 조회하기로 결정**하고
당시엔 코드를 지우지 않고 주석 처리(`[보류]`)만 해뒀었다. **[2026-07-14] 활용신청이
승인되어(개발계정, 자동승인, DUR과 같은 계정) 재활성화**했다 — e약은요·HIRA와 조율할 필요
없이 세 번째 인용 소스로 `SourceRef`에 병합했다(`permit_kind_code`/`permit_active` 필드).

### 왜 찾게 됐나

기존에 쓰던 `MFDS_BASE_URL`(`DrbEasyDrugInfoService/getDrbEasyDrugList`)이 사실 "의약품 허가정보"가
아니라 **e약은요**였다는 걸 뒤늦게 확인했다 (필드명이 `efcyQesitm`/`useMethodQesitm`처럼 "~Qesitm"
FAQ 형식인 게 e약은요의 시그니처). "진짜 의약품 허가정보"를 웹 검색으로 다시 찾은 게 아래 API다.

### API 상세 (실제 서비스 키로 호출해 검증 완료, 2026-07-08)

- **서비스명**: 공공데이터포털 "식품의약품안전처_의약품제품허가정보"
- **Base URL**: `http://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07`
- **Operation**: `getDrugPrdtPrmsnInq07`
- **기존 `DATA_GO_KR_SERVICE_KEY`로 별도 활용신청 없이 바로 호출 성공** (e약은요와 같은 계정 키 공유)

**요청 파라미터**:

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `serviceKey` | 필수 | 공공데이터포털 인증키 |
| `pageNo` / `numOfRows` | 선택 | 페이지네이션 |
| `type` | 선택 | 응답 포맷(xml/json) |
| `item_name` | 선택 | 제품명(부분일치) |
| `entp_name` | 선택 | 업체명 |
| `item_ingr_name` | 선택 | 주성분 |
| `prduct_prmisn_no` | 선택 | 제품 허가번호 |
| `induty` | 선택 | 업종 |

**응답 필드** (`item_name=타이레놀`로 실제 호출해 확인한 실측 필드, 효능효과 등 설명문 없음):

| 필드 | 의미 |
|---|---|
| `ITEM_SEQ` / `ITEM_NAME` / `ITEM_ENG_NAME` | 품목일련번호 / 품목명(국문·영문) |
| `ENTP_NAME` / `ENTP_ENG_NAME` / `ENTP_SEQ` / `ENTP_NO` | 업체명(국문·영문)·업체일련번호·업체번호 |
| `ITEM_PERMIT_DATE` | 허가일자 (YYYYMMDD) |
| `INDUTY` | 업종 (예: "의약품 및 의약외품 수입업") |
| `PRDLST_STDR_CODE` | 품목기준코드 |
| `SPCLTY_PBLC` | 전문/일반의약품 구분 |
| `PRDUCT_TYPE` | 제품유형 (예: "[01140]해열.진통.소염제") |
| `PRDUCT_PRMISN_NO` | 허가번호 |
| `ITEM_INGR_NAME` / `ITEM_INGR_CNT` | 주성분명(영문)·주성분 개수 |
| `PERMIT_KIND_CODE` | "허가" \| "신고" |
| `CANCEL_DATE` / `CANCEL_NAME` | 취소일자 / 취소·정상 등 상태명 |
| `EDI_CODE` | 심평원 청구코드 (많은 품목에서 `null`) |
| `BIZRNO` | 사업자등록번호 |
| `BIG_PRDT_IMG_URL` | 제품 이미지 URL (없으면 빈 문자열) |

### 코드 위치

| 파일 | 내용 |
|---|---|
| `rag/config.py` | `PERMIT_INFO_BASE_URL` (Base URL + operation 조합, HTTP→HTTPS로 정정) |
| `rag/schemas.py` | `DrugPermitInfo` 모델 (위 응답 필드 전부 alias로 매핑, `is_active` 프로퍼티 포함) |
| `rag/mfds_client.py` | `search_permit_info(item_name)` / `is_officially_approved(item_name)` |
| `rag/rag_chain.py` | `_lookup_permit_entry()` — e약은요 item_name으로 조회해 `SourceRef.permit_kind_code`/`permit_active`를 채움(HIRA 조회와 동일한 캐시·fail-safe 패턴) |
| `rag/schemas.py` | `SourceRef.permit_kind_code`/`permit_active` 필드 추가 — `hira_active`(약가 등재 상태)와는 다른 개념, 이건 제조·판매 허가 자체의 취소여부 |
| `backend/routers/rag_router.py` | `permit_kind_code`/`permit_active`를 `source_refs` 배열에 병합 |
| `frontend/src/api/records.ts` | `SourceRef` 인터페이스에 필드 추가(표시 텍스트는 HIRA 필드와 동일하게 화면에 노출하지 않고 데이터로만 보유) |
| `tests/test_mfds_client.py` | `search_permit_info`/`is_officially_approved` 테스트 6건 (mock 기반, 재활성화) |
| `tests/test_rag_chain.py` | `_build_context`의 permit 통합 테스트 3건(정상 매칭/미매칭/조회 실패 격리, HIRA 테스트와 동일 패턴) |
| `tests/conftest.py` | `_no_real_dur_lookups` autouse fixture에 `search_permit_info` 기본값도 빈 리스트로 추가(실제 API 실수 호출 방지) |

2026-07-14 실제 API로 e2e 검증 완료: "타이레놀정500밀리그람"으로 `permit_kind_code="신고"`,
`permit_active=True`가 `source_refs`에 정확히 채워짐을 확인.

## 7. DUR(의약품안전사용서비스) 연동 — [2026-07-13] 로컬 CSV 방식, 5개 카테고리 전부 구현 완료

RAG 파트에 DUR(의약품안전사용서비스) 주의/금기 경고를 붙였다.
**[2026-07-10] API(`DURPrdlstInfoService03/getUsjntTabooInfoList03`, 병용금기만)로 처음
시도했으나 403 Forbidden(별도 활용신청 필요)**이 나와서, **[2026-07-13] 공공데이터포털에서
받은 CSV(건강보험심사평가원_의약품안전사용서비스(DUR) 의약품 목록_202606)를
`backend/data/`에 두고 로컬 조회로 대체**했다 — HIRA 약가마스터와 동일한 패턴(API 대신
로컬 파일). API 활용신청이 나중에 승인되면 그때 다시 API 연동을 검토할 수 있지만, 지금은
이 CSV들이 정본이다.

**처음엔 병용금기 카테고리 하나만 연동했다가, 실제로 받은 폴더에 카테고리가 5개 다 있다는
걸 뒤늦게 인지해서 나머지 4개도 이번에 함께 추가했다** — 아래 표 참고.

### 데이터 정보

건강보험심사평가원 "의약품안전사용서비스(DUR) 의약품 목록_202606" 폴더의 CSV 5개, 전부 연동함:

| 카테고리 | 파일 | 행 수 | 관계 종류 |
|---|---|---|---|
| 병용금기 | `backend/data/dur_usjnt_taboo_202606.csv` | 약 87만 | **약 두 개 사이의 관계** — 처방전에 상대 약이 실제로 있어야 경고 (`DurWarning`) |
| 노인주의 | `backend/data/dur_elderly_caution_202606.csv` | 약 558 | 약 하나의 속성 (`DurCaution`) |
| 노인주의(해열진통소염제) | `backend/data/dur_elderly_caution_nsaid_202606.csv` | 약 1035 | 약 하나의 속성 (`DurCaution`) |
| 연령금기 | `backend/data/dur_age_taboo_202606.csv` | 약 2867 | 약 하나의 속성 (`DurCaution`) |
| 임부금기 | `backend/data/dur_pregnancy_taboo_202606.csv` | 약 19521 | 약 하나의 속성 (`DurCaution`) |

전부 CP949 인코딩, 컬럼명은 카테고리마다 다르지만 품목명 컬럼은 공통으로 `제품명`이다
(병용금기만 `제품명A`/`제품명B` 쌍). HIRA CSV처럼 `backend/data/`에 실물만 두고
git 미추적(`.gitignore`의 `data/*.csv`) — 각자 로컬에 받아서 채워야 한다.

노인주의/연령금기/임부금기는 "이 환자에게 실제로 해당하는지"(나이·임신 여부)를 이 시스템이
알 방법이 없어서, 조건 판단 없이 "이 약에 이런 조건부 주의사항이 있다"는 사실만 정보성으로
전달한다 — 특히 노인주의는 이 서비스의 주 사용자층(고령 만성질환자)과 직접 관련된다.

### 코드 위치

| 파일 | 내용 |
|---|---|
| `rag/dur_master.py` | `search_usjnt_taboo`(병용금기, 양방향 인덱스), `search_elderly_caution`/`search_age_taboo`/`search_pregnancy_taboo`(단일 약 속성, 공통 로더 `_lookup_single_drug_rows`) — 전부 정확/부분일치 조회 + 브랜드 중복 제거(`_dedupe_cautions`), hira_master.py와 동일한 최초 1회 파싱·프로세스 캐시 패턴 |
| `rag/schemas.py` | `DurTabooInfo`/`DurWarning`(병용금기), `DurCaution`(나머지 4개 카테고리 공용), `GuideResponse.dur_warnings`/`dur_cautions` |
| `rag/rag_chain.py` | `_check_dur_taboo()`(병용금기 — 처방전에 실제로 함께 있는 약과만 대조), `_check_dur_cautions()`(나머지 4개 카테고리 — 다른 약과 무관, 약 하나만으로 판단) |
| `backend/routers/rag_router.py` | `dur_warnings`/`dur_cautions`를 `source_refs` 배열에 병합해 프론트로 전달 |
| `frontend/src/api/records.ts` | `SourceRef.mixture_item_name`/`prohbt_content`(병용금기), `dur_category`/`dur_detail`/`dur_extra`(나머지), `formatSourceRef`가 "⚠️ OO와 병용금기" / "⚠️ 노인주의(...): ..." 형태로 표시 |
| `tests/test_dur_master.py` | 5개 카테고리 전부 픽스처 기반 테스트 (`tests/fixtures/dur_*_sample.csv`), 실제 CSV로도 e2e 검증 완료 |
| `tests/test_rag_chain.py` | `_check_dur_taboo`/`_check_dur_cautions` mock 기반 테스트 (경고 매칭, 브랜드 중복 제거, 조회 실패 격리) |
| `tests/conftest.py` | `_no_real_dur_lookups` autouse fixture — DUR 조회 함수 기본값을 빈 리스트로 고정해, DUR과 무관한 테스트가 로컬에 실제 대용량 CSV가 있는지 여부에 따라 결과가 갈리지 않게 함 |

### 설계 노트

- 병용금기는 "약 하나의 속성"이 아니라 "두 약 사이의 관계"라 `DurWarning`으로, 나머지 4개
  카테고리는 "약 하나"의 속성이라 공용 `DurCaution`으로 분리했다 (HIRA처럼 `SourceRef`에
  필드를 추가하는 방식은 쓰지 않음).
- 모든 DUR 조회 함수는 실패(CSV 파일 부재 등 어떤 이유든)해도 예외를 삼키고 빈 리스트를
  반환한다 — 나머지 가이드 생성 흐름(HIRA/e약은요 인용, LLM 생성)은 전혀 영향받지 않는다.
- **브랜드 단위 중복 제거**: CSV는 전부 제품(브랜드) 단위라 같은 성분이 제조사별로
  수십~수천 건 중복 등재돼 있다(실측: 병용금기는 "아스피린"+"메토트렉세이트"만으로 1728건,
  노인주의는 "아스피린" 하나로 47건 발생). 병용금기는 CSV의 브랜드명 대신 **처방전에 실제로
  적힌 약 이름**으로, 나머지는 **(카테고리, 사유, 부가정보) 조합**으로 한 번씩만 보여주도록
  전부 중복 제거 처리했다 (1728건 → 2건, 47건 → 2건으로 확인).
