# 편차(Deviation) 로그 — OCR ↔ RAG 통합 검증

- **날짜**: 2026-07-06
- **작성자**: 김영혜 (RAG 담당)
- **관련 브랜치**: RAG는 `feature/frontend-setup_yunghye`, OCR은 `origin/feature/ocr-day1-setup_soonhyun` (`AH_04_02_soonhyun/ocr_interface.py`, 담당: 순현)
- **관련 문서**: `rag/contract.md` (필드 계약 정본), `docs/troubleshooting_log/troubleshooting-log.md`(2026.07.06 항목, D2 상세 재현 기록)

## 목적 — 무엇을 위해서

순현님이 만든 OCR 인터페이스(`ocr_interface.py`)가 뽑아내는 실제 처방전 인식 결과(`MedicationItem`/`OCRResult`)를,
내가 만든 RAG 파이프라인(`rag-prototype/`)이 실제로 "유기적으로, 기능적으로" 문제없이 받아 처리할 수 있는지
코드 리뷰가 아니라 **실제 데이터로** 검증하기 위함.

## 무엇을 하다가

1. OCR 브랜치(`origin/feature/ocr-day1-setup_soonhyun`)를 fetch해 `ocr_interface.py`, `parsing_rules.py`,
   `drug_reference.py`, `results.md`, `sample_ocr_output.json`을 직접 확인.
2. `MockOCRProvider().extract()`로 얻은 실제 `MedicationItem` dataclass 인스턴스 2건(아스피린 0.92,
   로자탄 0.78)과, 실측 CLOVA 캡처본(`sample_ocr_output.json`, 암로디핀/로자탄칼륨/메트포르민, 진단
   "고혈압, 제2형 당뇨병")을 합쳐 총 5건을 `rag_prototype.rag_chain.generate_guide_from_medication()`에
   실제로 통과시켜봄 (dry-run 4건 + 실제 OpenAI 호출 2건).

## 발견된 편차 4건

### D1. 배치 처리 진입점 부재

- **무엇**: `OCRResult.medications`는 리스트인데, RAG 쪽엔 약 1건만 받는 `generate_guide_from_medication()`만
  있고 여러 건을 순회/집계하는 검증된 함수나 테스트가 없었음.
- **원인**: RAG를 "약 1건 조회" 단위로만 설계하고, OCR이 처방전 1건당 여러 약을 한 번에 내려준다는 점을
  진입점 설계에 반영하지 않음.
- **해결**: `rag_chain.generate_guides_from_medications(list)` / `generate_guides_from_ocr_result(ocr_result)`
  추가. 항목 하나가 `NoContextFoundError` 등으로 실패해도 `try/except`로 격리해 나머지는 정상 반환, 실패건은
  `review_flags=["generation_error"]`로 표시. (`BatchGuideResponse` 같은 집계 스키마는 2주차 프로토타입
  단계에는 과설계로 판단해 보류 — `ai_worker` 실제 이식 시점에 재검토)
- **재발 방지**: README에 "여러 약은 반드시 `generate_guides_from_ocr_result()`로 진입" 명시. 배치 비용
  (약 1건당 self-consistency 샘플 수만큼 LLM 호출, N건이면 3×N 직렬 호출)도 함께 문서화해 규모가 커질 때
  병렬화/샘플 수 조정을 검토하도록 함.

### D2. OCR 개별 인식 신뢰도가 RAG 최종 응답에 반영되지 않음 (가장 심각, 실측 확인)

- **무엇**: `MedicationItem.confidence=0.78`(OCR 자체 기준 0.80 미만 → 검토 필요)인 약을 실제 OpenAI 키로
  생성했더니 `GuideResponse.review_required=False`가 나옴. 상세 재현 과정은
  `docs/troubleshooting_log/troubleshooting-log.md`(2026.07.06 항목) 참고.
- **원인**: `MedicationInput.confidence` 필드는 존재했지만 `generate_guide_from_medication()`/`generate_guide()`
  어디에서도 읽지 않았음. 게다가 OCR 자체의 `review_required`도 `overall_confidence`(전체 평균)만 보기 때문에
  평균이 임계값을 넘으면 그 안의 개별 저신뢰 약을 놓친다 (예: 아스피린 0.92 + 로자탄 0.78 → 평균 0.85 →
  OCR도 통과 판정).
- **해결**: `config.py`에 `OCR_CONFIDENCE_REVIEW_THRESHOLD=0.80` 신설. `rag_chain._merge_ocr_confidence()`를
  어댑터(`generate_guide_from_medication`)에서 **후처리**로 호출해, `confidence < 0.80`이면
  `review_required=True` + `review_flags`에 `ocr_low_confidence` 추가, `confidence == 0.0`(Tesseract 등
  미제공)이면 `ocr_confidence_unavailable`로 별도 구분. **핵심 설계 결정**: 이 로직을 `generate_guide()`
  코어 시그니처에 넣지 않고 어댑터에서 결과를 병합하는 방식으로 함 — 코어는 드럭 중심 로직만 유지해 회귀
  위험을 최소화 (3라운드 서브에이전트 토의에서 확정, 아래 참고).
- **재발 방지**: `rag/contract.md` 2번 항목에 "왜 RAG가 OCR confidence를 다시 체크하는가(=OCR의 overall-only
  판정에 대한 보완 통제)"를 명시. 회귀 테스트 3건(`test_low_ocr_confidence_forces_review`,
  `test_zero_confidence_marks_unavailable`, `test_high_confidence_preserves_review_state`) 추가.

### D3. `review_required` 필드명 충돌

- **무엇**: `OCRResult.review_required`(추출 신뢰도 기준)와 `GuideResponse.review_required`(인용/
  self-consistency 기준)가 이름은 같은데 의미가 다름.
- **원인**: 두 파트가 독립적으로 각자 도메인에 맞는 이름을 붙였고, 사전에 네이밍을 조율하지 않음.
- **해결**: rename하지 않기로 결정 (OCR 계약은 동결이라 못 바꾸고, RAG 쪽 rename은 `cli.py`의
  `model_dump()` JSON 출력·기존 소비자·테스트를 깨뜨림). 대신 `GuideResponse.review_flags: list[str]`를
  추가해 사유를 기계 판독 가능한 코드(`no_citation`/`low_self_consistency`/`ocr_low_confidence`/
  `ocr_confidence_unavailable`/`dry_run`/`generation_error`)로 구분.
- **재발 방지**: `rag/contract.md` 3번 항목에 "다운스트림(`ai_worker` 등)에서 두 `review_required`를 함께
  로깅/병합할 때는 `ocr_review_required`/`rag_review_required`처럼 접두어를 붙여 구분할 것"을 명문화.

### D4. 생활지침 커버리지 한계 (버그 아님, 정보성)

- **무엇**: 실제 OCR 목업 결과에 "관상동맥질환", "위염", "골관절염", "불면증", "무릎관절증" 등 진단명이
  나오는데, `data/lifestyle_guidelines.json`은 4개 질환(고혈압/당뇨병/이상지질혈증/만성콩팥병)만 커버해서
  이 경우 생활지침 인용이 0건으로 나옴.
- **원인**: 애초에 4개 질환만 데이터를 구축했고, 커버 범위를 코드 주석/문서에 명시하지 않음.
- **해결**: 코드 수정 없음 (커버 안 되는 질환에 근거 없이 지어내지 않는 것이 올바른 동작).
- **재발 방지**: `rag_chain.py`의 `DIAGNOSIS_DISEASE_ALIASES` 위 주석과 `rag/contract.md` 4번 항목에 "커버
  안 되는 질환은 생활지침 0건이 정상"임을 명시해, 나중에 "왜 생활지침이 안 나오지?"를 버그로 오인하지
  않도록 함.

## 3라운드 서브에이전트 토의 (CAPA 수립 과정)

D1~D4를 어떻게 해결할지 architect/critic 두 개의 독립 서브에이전트로 3라운드 토의를 진행함:

1. **1라운드 (제안, architect)**: D1~D4에 대한 초기 해결안 제시. D2는 `generate_guide()` 코어 시그니처에
   `ocr_confidence: float | None = None` 파라미터를 추가하는 안, D1은 `BatchGuideResponse`라는 새 집계
   스키마를 만드는 안을 제안.
2. **2라운드 (비판, critic)**: 판정 **REVISE**. 핵심 지적 2가지 — (a) `None` 가드는 어댑터 경로에서
   죽은 코드다(OCR의 `confidence`는 항상 float, 절대 None이 아니므로). (b) `BatchGuideResponse`는 2주차
   프로토타입에는 과설계이고, 오히려 약 1건당 self-consistency 3회 호출 → N건이면 3×N 직렬 호출이라는
   실질적 비용 문제를 1라운드가 언급조차 안 했다는 점을 지적.
3. **3라운드 (최종 수렴, architect가 비판에 응답)**: OCR 브랜치 코드로 critic의 사실 주장을 전부 재검증한
   뒤, D2는 "코어 시그니처는 그대로 두고 어댑터에서 후처리 병합"으로, unknown(신뢰도 미제공)/low(신뢰도
   낮음) 구분은 `None` 대신 **값 기준**(`confidence == 0.0` → unavailable)으로 최종 확정. D1은
   `BatchGuideResponse`를 보류하고 `list[GuideResponse]`만 반환하는 얇은 헬퍼로 축소.

최종 CAPA는 위 D1~D4의 "해결" 항목에 반영된 대로 그대로 구현함 (config.py/schemas.py/rag_chain.py 변경,
회귀 테스트 4건 + 계약 테스트 2건 추가, `rag/contract.md` 신설).

## 검증 결과

- `pytest` 20/20 통과, `ruff check .` 클린.
- 계약 테스트(`tests/contracts/test_ocr_contract.py`)가 OCR mock 실제 산출물(아스피린 0.92 / 로자탄 0.78)을
  픽스처로 고정해, confidence 병합이 실제 필드값 기준으로 정확히 동작하는지 검증.
