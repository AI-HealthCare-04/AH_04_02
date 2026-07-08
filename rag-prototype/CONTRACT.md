# OCR ↔ RAG 인터페이스 계약

두 파트가 다른 브랜치에서 독립적으로 개발되기 때문에(OCR: `origin/feature/ocr-day1-setup_soonhyun`의
`AH_04_02_soonhyun/ocr_interface.py`, RAG: 이 브랜치의 `rag-prototype/`), 코드가 서로를 import해서
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
| RAG `OCR_CONFIDENCE_REVIEW_THRESHOLD` | 0.80 (OCR과 동일 값, 의도적 중복) | `MedicationItem.confidence`(**개별 약** 신뢰도)가 이 미만이면 해당 약의 `GuideResponse.review_required=True` | `rag_prototype/config.py` |
| RAG `SELF_CONSISTENCY_SIMILARITY_THRESHOLD` | 0.75 | LLM 답변 self-consistency 점수 임계값. **위 두 confidence 임계값과 의미가 완전히 다름** — 혼동 금지 | `rag_prototype/config.py` |

**왜 RAG가 confidence를 다시 체크하는가**: OCR의 `review_required`는 `overall_confidence`(전체 평균)만
보기 때문에 개별 약의 저신뢰를 놓칠 수 있다. 실측 사례(Mock provider): 아스피린 0.92 + 로자탄 0.78 →
평균 0.85 → `OCRResult.review_required=False`. 하지만 로자탄은 OCR 자체 기준(0.80)으로도 검토 대상이다.
RAG의 개별 confidence 체크는 새 기능이 아니라 **이 판정 한계에 대한 보완 통제(compensating control)**다
(`rag_prototype/rag_chain.py`의 `_merge_ocr_confidence`).

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

## 6. [보류] 의약품 제품허가정보 API (`DrugPrdtPrmsnInfoService07`)

2026-07-08, "의약품 허가 기반으로 데이터 구축하려던 원래 의도"를 확인하던 중 찾아서 실제
서비스 키로 테스트까지 마쳤지만, **e약은요 + HIRA 약가마스터만으로 우선 조회하기로 결정**하고
지금은 코드를 지우지 않고 주석 처리(`[보류]`)만 해뒀다. 나중에 이 API가 다시 필요해지면(예:
"이 약이 취소·취하되지 않은 정식 허가 의약품인지"를 HIRA 약가마스터보다 더 신뢰도 높게
검증해야 하는 문제가 생기는 경우) 아래 정보로 바로 복원하면 된다.

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

### 코드 위치 (전부 `[보류]` 주석 처리됨 — 검색해서 주석만 풀면 복원)

| 파일 | 내용 |
|---|---|
| `rag_prototype/config.py` | `PERMIT_INFO_BASE_URL` (Base URL + operation 조합) |
| `rag_prototype/schemas.py` | `DrugPermitInfo` 모델 (위 응답 필드 전부 alias로 매핑, `is_active` 프로퍼티 포함) |
| `rag_prototype/mfds_client.py` | `search_permit_info(item_name)` / `is_officially_approved(item_name)` |
| `tests/test_mfds_client.py` | 위 두 함수에 대한 테스트 6건 (mock 기반) |

재활성화 시 체크할 것: `mfds_client._request()`는 이미 `base_url` 파라미터를 받도록 일반화돼
있어 e약은요 호출부(`search_by_name`/`fetch_page`)는 그대로 두고 permit 함수만 살리면 된다.
