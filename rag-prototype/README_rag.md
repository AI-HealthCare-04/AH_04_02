# RAG Prototype — 복약·생활습관 가이드 생성

AH04_2조 파이널 프로젝트의 "② RAG·가이드생성" 파트 프로토타입입니다.
식약처(공공데이터포털) 의약품 데이터와 만성질환 생활지침 데이터를 ChromaDB에 임베딩해두고,
약품명(+진단명)으로 질의하면 LangChain 기반으로 복약 안내 + 생활습관 가이드를 생성합니다.
최종적으로는 `ai_worker/`의 RAG Worker로 이식하는 것을 목표로 하는 독립 프로토타입입니다.

## 구성 (요약)

- 검색: 식약처 `DrbEasyDrugInfoService/getDrbEasyDrugList`(e약은요, 품목명 부분검색/전체 목록 페이징) + `backend/data/hira_drug_master_20251031.csv`(HIRA 약가마스터, 표준코드·ATC코드·허가/취소 상태 로컬 조회 — OCR 파트 `drug_reference.py`와 파일 공유, 아래 참고)
- 만성질환 생활지침: `data/lifestyle_guidelines.json` (고혈압·당뇨병·이상지질혈증·만성콩팥병, 학회/질병관리청 출처)
- 임베딩: `sentence-transformers` 로컬 모델 (`jhgan/ko-sroberta-multitask`) — **OpenAI 키 없이 동작**
- 벡터DB: ChromaDB (로컬 영속 저장, `./chroma_db`), 의약품·생활지침이 같은 컬렉션에 공존
- 생성: OpenAI `gpt-4o-mini` (LangChain) — **키가 없으면 dry-run 모드**로 검색 결과만 반환
- Hallucination 최소화: (1) 참고자료 번호를 강제 인용(source_refs/lifestyle_source_refs), (2) JSON 형식 강제, (3) self-consistency (동일 질의 N회 생성 후 서로 가장 일치하는 답 채택, 낮으면 `review_required=True`)
- OCR 연동: `generate_guide_from_medication()`이 OCR 파트(`AH_04_02_soonhyun/ocr_interface.py`)의 `MedicationItem`과 동일한 필드(drug_name/dosage/frequency/diagnosis/drug_class/confidence)를 그대로 받는다. 여러 약(`OCRResult.medications`)은 `generate_guides_from_ocr_result()`로 일괄 처리하며, 항목 하나가 실패해도 나머지는 격리되어 정상 반환된다. OCR 개별 신뢰도(`confidence`)가 낮으면 `GuideResponse.review_required`가 강제로 True가 되고 `review_flags`에 사유 코드가 남는다 — 필드 매핑/임계값/명명 규칙은 `CONTRACT.md` 참고.

아래 "데이터 파이프라인 상세"에서 각 항목이 실제로 어디서 와서 어떤 코드를 거쳐 벡터DB에 들어가고,
질의 시점에 어떻게 다시 꺼내 쓰이는지 코드를 몰라도 따라갈 수 있도록 설명한다.

## 데이터 파이프라인 상세

이 프로토타입은 **서로 다른 출처의 데이터 2종**을 각각 다른 방식으로 수집해서,
**하나의 ChromaDB 컬렉션**(`mfds_drug_info`)에 함께 저장한다. 질의할 때는 메타데이터
(`item_name` 완전일치 vs `disease_code` 완전일치)로 어느 쪽 데이터인지 구분해서 꺼낸다.

### 출처 1 — 의약품 정보 (식약처 공공데이터, 실시간 외부 API)

| 단계 | 코드 | 설명 |
|---|---|---|
| 수집 | `rag_prototype/mfds_client.py` | `search_by_name()`(품목명 부분검색), `fetch_page()`(전체 목록 페이징). `requests`로 공공데이터포털 API를 직접 호출하고 재시도 로직 포함 |
| 데이터 모양 | `rag_prototype/schemas.py`의 `DrugInfo` | API가 내려주는 원본 필드(품목명·업체명·효능효과·용법용량·경고·주의사항·상호작용·부작용·보관법)를 그대로 담는 pydantic 모델 |
| 청킹 | `rag_prototype/chunking.py`의 `drug_to_documents()` | 약 1건을 **필드 단위**로 쪼개 여러 개의 `Document`로 만든다(효능효과 1개, 주의사항 1개, ... 빈 필드는 건너뜀). 필드별로 쪼개는 이유: 나중에 "이 문장이 부작용 항목에서 나왔다"처럼 출처를 정확히 추적하기 위함 |
| 적재 | `rag_prototype/vectorstore.py`의 `add_documents()` | id = `{item_seq}::{field}` 로 ChromaDB에 upsert (같은 약을 다시 넣어도 중복 저장되지 않음) |
| 실행 시점 | ① `python -m rag_prototype.cli ingest ...` (배치 수집) 또는 ② 질의 중 벡터DB에 없는 약이면 `rag_chain._live_fetch_and_ingest()`가 **그 자리에서** API를 호출해 즉시 채워 넣음 (OCR이 실시간으로 인식한, 사전 배치에 없던 약 대응) | |

> **주의**: 이 API(`DrbEasyDrugInfoService/getDrbEasyDrugList`)는 공공데이터포털의
> **"식품의약품안전처_의약품개요정보(e약은요)"** 서비스다. OCR 파트(`drug_reference.py`)가
> drug_class 분류에 쓰는 "e약은요 DB"(정적 xlsx)와 **원천 데이터가 동일**하다 — 접근 방식만
> 실시간 API 호출 vs 정적 파일로 다를 뿐이다.

### 출처 1-부가 — 건강보험심사평가원 약가마스터·의약품표준코드 (로컬 CSV)

e약은요와 원천이 다른 **로컬 정적 데이터**. 효능효과 같은 설명문은 없지만, e약은요에는
없는 표준코드·ATC코드·허가일자·취소일자 같은 코드성 정보를 담고 있어 품목 식별/검증
보조용으로 병행 조회한다. OCR 파트(`drug_reference.py`)가 drug_class 분류에 쓰는 것과
같은 파일이다.

| 단계 | 코드 | 설명 |
|---|---|---|
| 원본 데이터 | `backend/data/hira_drug_master_20251031.csv` (약 30.5만 행, CP949 인코딩) | 건강보험심사평가원 약가마스터. 한글상품명·업체명·제형·품목기준코드·품목허가일자·표준코드·ATC코드·취소일자 등 |
| 데이터 모양 | `rag_prototype/schemas.py`의 `HiraDrugMasterEntry` | `is_active` 프로퍼티로 취소일자 없이 정상 등재 상태인지 바로 판단 가능 |
| 조회 | `rag_prototype/hira_master.py`의 `search_by_product_name()` / `is_registered_and_active()` | 최초 호출 시 CSV 전체를 한글상품명 기준 raw dict 인덱스로 1회 파싱해 프로세스 캐시(약 1.5초), 이후 조회는 즉시 반환. 정확히 일치하는 상품명 우선, 없으면 부분일치로 폴백 |
| 벡터DB 적재 | 안 함 | 설명문이 없어 임베딩 대상이 아님, 조회 전용 |
| 인용 연동 | `rag_chain._build_context`의 `_lookup_hira_entry` | 의약품 `SourceRef` 생성 시 같은 품목명으로 HIRA를 조회해 `hira_standard_code`/`hira_atc_code`/`hira_permit_date`/`hira_active`를 함께 채운다 (아래 "생성 & Hallucination 방어" 참고) |

> **[보류] 의약품 허가정보 API**(`DrugPrdtPrmsnInfoService07`)는 e약은요·약가마스터만으로
> 우선 조회하기로 하고 코드에 주석 처리해서 남겨뒀다 (`config.py`/`schemas.py`/`mfds_client.py`
> 및 관련 테스트에 `[보류]` 표시). 정보량이 방대하고 팀원 연동(HIRA 약가마스터) 조율이 더
> 필요해서 보류했고, 나중에 정말 경로를 바꿔야 하는 문제가 생기면 주석을 풀어 쓴다.

### 출처 2 — 만성질환 생활지침 (사람이 정리한 참고자료 파일)

| 단계 | 코드 | 설명 |
|---|---|---|
| 원본 데이터 | `data/lifestyle_guidelines.json` | 고혈압·당뇨병·이상지질혈증·만성콩팥병 생활수칙 11건. 각 항목에 근거 학회/기관(대한고혈압학회, 대한당뇨병학회, 한국지질·동맥경화학회, 대한신장학회, 질병관리청 심뇌혈관질환 예방관리수칙)을 `source` 필드로 명시. 직접 열어서 텍스트로 확인/수정 가능한 일반 JSON 파일 |
| 데이터 모양 | `rag_prototype/schemas.py`의 `LifestyleGuideline` | `id`(고유키) / `disease`(한글 질환명) / `disease_code`(영문 코드, 검색용) / `category`(식이요법·운동 등) / `rule`(생활수칙 본문) / `source`(근거 출처) |
| 로딩 | `rag_prototype/lifestyle_data.py`의 `load_lifestyle_guidelines()` | JSON 파일을 읽어 `LifestyleGuideline` 객체 리스트로 변환 (외부 API 호출 없음, 순수 파일 읽기) |
| 청킹 | `rag_prototype/chunking.py`의 `lifestyle_guideline_to_document()` | 항목 1개 = `Document` 1개 (이미 한 문장 단위라 추가로 쪼갤 필요 없음). metadata에 `doc_type="lifestyle_guideline"`, `disease_code`, `category`, `source` 등을 태그해둔다 |
| 적재 | `rag_prototype/vectorstore.py`의 `add_lifestyle_documents()` | id = guideline id(예: `htn-diet-1`)로 같은 컬렉션에 upsert |
| 실행 시점 | `python -m rag_prototype.cli ingest-lifestyle` (로컬 파일이라 배치 1회 실행이면 충분, 실시간 재조회 로직 없음) | |

> **주의**: `data/lifestyle_guidelines.json`은 각 학회 진료지침 원문이 아니라, AI 챗봇과의 요약 대화에서
> 정리한 2차 가공 데이터다. 실제 서비스에 반영하기 전에는 각 학회 진료지침 원문과 반드시 대조 검증해야 한다.

### 임베딩 & 벡터DB (두 데이터 공통)

- 임베딩 모델: `sentence-transformers`의 `jhgan/ko-sroberta-multitask` — 로컬에서 실행되며 OpenAI 키가 없어도 동작한다 (`vectorstore.get_embedding_function()`)
- 저장소: ChromaDB, 로컬 영속 디렉터리 `./chroma_db`, 컬렉션명 `mfds_drug_info` (`config.py`의 `CHROMA_PERSIST_DIR` / `CHROMA_COLLECTION_NAME`)
- 의약품 청크와 생활지침 청크가 **같은 컬렉션**에 함께 들어있고, 조회할 때 메타데이터 필터(`item_name` 또는 `disease_code`)로 구분해서 꺼낸다

### 질의 시점 검색 흐름 (`rag_prototype/rag_chain.py`의 `_build_context()`)

약품명 + 환자 상황 + 진단명이 들어오면, 아래 순서로 "참고자료"를 모은다:

```
질의(drug_name, situation, diagnosis)
  │
  ├─ 1) 의약품 정확매칭   search_by_item_name(drug_name)
  │      └─ Chroma where={"item_name": ...} 완전일치 (유사도 검색 아님)
  │
  ├─ 2) (1이 비면) 실시간 폴백   MFDS API 즉시 호출 -> 벡터DB에 적재 -> 1) 재시도
  │      └─ OCR이 방금 인식한, 사전 배치에 없던 약 대응
  │
  ├─ 3) (2도 비면) 유사도 검색 폴백   similarity_search(약품명+용량+상황)
  │
  └─ 4) 생활지침 질환 매칭   진단명 텍스트에서 DIAGNOSIS_DISEASE_ALIASES로 disease_code 추론
         └─ 예: "고혈압"→hypertension, "당뇨"/"당뇨병"→diabetes, "고지혈증"/"이상지질혈증"→dyslipidemia,
                "만성콩팥병"/"신장질환"→chronic_kidney_disease (진단에 여러 질환이 있으면 전부 매칭)
         └─ search_by_disease(disease_code)로 해당 질환의 생활지침 전체를 가져온다
```

1~4에서 모인 항목을 전부 하나의 번호(`[1] ... [2] ...`) 목록으로 합쳐 LLM에게 "참고자료"로 전달한다.
의약품이든 생활지침이든 "번호를 인용해야 답변에 쓸 수 있다"는 규칙은 동일하다.

### 생성 & Hallucination 방어 (`rag_chain.generate_guide()`)

- `OPENAI_API_KEY`가 없으면: **dry-run 모드** — 검색된 참고자료 원문을 그대로 반환(LLM 호출 없음), `review_required=True`
- 키가 있으면: `gpt-4o-mini`로 JSON 형식을 강제해 생성하며, hallucination을 줄이기 위해
  1. 답변의 모든 문장은 참고자료 번호를 근거로 작성하고 사용한 번호를 `source_refs`에 포함하도록 프롬프트에 강제
  2. 동일 질의를 `SELF_CONSISTENCY_SAMPLES`회(기본 3회) 생성해 서로 코사인 유사도가 가장 높은(가장 "합의된") 답을 채택 (`self_consistency.py`)
  3. 인용이 하나도 없거나 self-consistency 점수가 임계값 미만이면 `review_required=True`로 표시해 사람이 검토하도록 함
- LLM이 인용한 참고번호를 다시 원래 항목과 대조해, **의약품 인용은 `source_refs`, 생활지침 인용은
  `lifestyle_source_refs`**로 분리해 최종 응답(`GuideResponse`)에 담는다
- 의약품 `source_refs`(`SourceRef`)는 e약은요 필드(item_seq/item_name/field) 외에, 같은 품목명으로
  HIRA 약가마스터를 조회해 `hira_standard_code`/`hira_atc_code`/`hira_permit_date`/`hira_active`도
  함께 채운다 (`_build_context`의 `_lookup_hira_entry`). HIRA에 없는 품목명이면 이 필드들만 `None`으로
  남고 e약은요 인용 자체는 그대로 유효 — HIRA 조회 실패가 인용 생성을 막지 않는다

### OCR 연동 & 배치 처리 (`generate_guide_from_medication` / `generate_guides_from_ocr_result`)

- `generate_guide_from_medication(item)`: OCR `MedicationItem` 1건(dataclass/dict 무엇이든)을 받아 `GuideResponse` 1건을 반환. 내부적으로 `generate_guide()` 호출 후, `item.confidence`를 후처리로 병합한다(`_merge_ocr_confidence`) — `generate_guide()` 자체 시그니처는 건드리지 않는다.
- `generate_guides_from_ocr_result(ocr_result)` / `generate_guides_from_medications(list)`: `OCRResult.medications`(여러 약) 전체를 순회 처리. 항목 하나가 `NoContextFoundError` 등으로 실패해도 나머지는 정상 반환되고, 실패건은 `review_flags=["generation_error"]`로 표시된다. **비용 주의**: 약 1건당 `SELF_CONSISTENCY_SAMPLES`(기본 3)회 LLM 호출이 순차 발생하므로, 처방전 1건에 약 N개면 3×N회 직렬 호출이다.
- OCR 개별 `confidence`가 `OCR_CONFIDENCE_REVIEW_THRESHOLD`(0.80) 미만이면 인용/self-consistency가 멀쩡해도 `review_required`가 강제로 True가 되고, `confidence == 0.0`(Tesseract 등 미제공)이면 `ocr_confidence_unavailable`로 별도 구분된다. 자세한 배경과 근거는 `CONTRACT.md` 참고.

### 파일 지도

| 파일 | 역할 |
|---|---|
| `rag_prototype/schemas.py` | 데이터 모델 전체: `DrugInfo`, `HiraDrugMasterEntry`, `LifestyleGuideline`, `SourceRef`, `LifestyleSourceRef`, `GuideResponse`, OCR 입력 `MedicationInput` (`DrugPermitInfo`는 `[보류]` 주석 처리됨) |
| `rag_prototype/mfds_client.py` | 식약처 e약은요 API 호출 (검색 / 전체목록 페이지 조회, 재시도). 허가정보 관련 함수는 `[보류]` 주석 처리됨 |
| `rag_prototype/hira_master.py` | `backend/data/hira_drug_master_20251031.csv`(HIRA 약가마스터) 로컬 조회 — 표준코드/ATC코드/허가·취소 상태 |
| `rag_prototype/lifestyle_data.py` | `data/lifestyle_guidelines.json` 로더 |
| `rag_prototype/chunking.py` | 의약품/생활지침 데이터 → `Document` 청크 변환 |
| `rag_prototype/vectorstore.py` | ChromaDB 연결, 적재(`add_documents` / `add_lifestyle_documents`), 조회(`search_by_item_name` / `search_by_disease` / `similarity_search`) |
| `rag_prototype/rag_chain.py` | 참고자료 컨텍스트 구성, 질환 별칭 매칭, LLM 호출, self-consistency, 최종 `GuideResponse` 조립 |
| `rag_prototype/cli.py` | `ingest` / `ingest-lifestyle` / `query` 커맨드라인 진입점 |
| `data/lifestyle_guidelines.json` | 만성질환 생활지침 원본 데이터 (텍스트 에디터로 직접 수정 가능) |
| `backend/data/hira_drug_master_20251031.csv` | HIRA 약가마스터 원본 (약 30.5만 행, CP949, 54MB). `backend/`에만 실물 1개 두고 여기서 상위 디렉터리 경로로 참조 — 권순현님 `drug_reference.py`와 완전히 동일한 파일(중복 보관 안 함) |
| `scripts/demo_e2e.py` | 배치 수집 → 검색 → 가이드 생성 데모 |
| `CONTRACT.md` | OCR ↔ RAG 필드 매핑, confidence 임계값, `review_required` 명명 규칙, 생활지침 커버리지 문서 |
| `tests/contracts/` | OCR 실제 산출물 픽스처 기반 계약 테스트 (필드 누락/rename 감지) |
| `docs/deviation-log/` | 팀 간 인터페이스 편차 발견·해결 이력 (날짜별) |

## 설치

```bash
cd rag-prototype
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 환경변수

`.env` 파일에 이미 식약처 서비스키가 채워져 있습니다. OpenAI 키는 발급받는 대로
`OPENAI_API_KEY`에 채워 넣으면 됩니다 (`.env`는 상위 프로젝트 `.gitignore`에 의해 커밋되지 않습니다).

## 사용법

```bash
# 1. 의약품 데이터 수집 -> 벡터DB 저장
python -m rag_prototype.cli ingest --item-names "타이레놀,아스피린,노바스크" --per-name 2

# (선택) 전체 목록에서 대량 샘플 수집
python -m rag_prototype.cli ingest --pages 3 --num-of-rows 100

# 1-1. 만성질환 생활지침 데이터 적재 (data/lifestyle_guidelines.json -> 벡터DB, 최초 1회)
python -m rag_prototype.cli ingest-lifestyle

# 2. 가이드 생성 (약품명은 정확한 품목명 권장, 진단명을 주면 해당 질환의 생활지침이 함께 인용됨)
python -m rag_prototype.cli query --drug "타이레놀정500밀리그램" --situation "고령" --diagnosis "고혈압"

# 3. 2주차 목요일 완료 기준 데모 (10건 확보 -> top-3 검색 -> 가이드 1건)
python scripts/demo_e2e.py
```

## 테스트 / 린트

```bash
pytest        # 네트워크(식약처 API)와 OpenAI 호출은 mock 처리되어 있어 키 없이도 통과
ruff check .  # 저장소 루트 pyproject.toml의 [tool.ruff] 규칙(E/W/F/I/C90/B/UP/N) 적용
```

## 다음 단계

- OpenAI 키 발급 후 `query` 명령으로 실제 생성 품질 확인 및 프롬프트 튜닝
- `ai_worker/`(Redis Stream Consumer)로 `rag_chain.generate_guide`를 이식
- ①(OCR) 결과 포맷과 입력 인터페이스 합의 후 `situation`/`diagnosis` 파라미터를 실제 진료기록 구조로 대체
- `data/lifestyle_guidelines.json` 원문(학회 진료지침) 대조 검증 — 현재는 AI 요약 대화 기반 2차 가공 데이터
