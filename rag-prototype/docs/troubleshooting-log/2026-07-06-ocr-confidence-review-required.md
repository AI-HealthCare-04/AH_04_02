# 트러블슈팅 로그 — OCR 개별 신뢰도가 RAG 검토 플래그에 반영되지 않음

- **날짜**: 2026-07-06
- **작성자**: 김영혜 (RAG 담당)
- **심각도**: 높음 (환자 안전 관련 — 오인식 가능성이 있는 약이 "검토 불필요"로 나갈 수 있었음)
- **관련 문서**: `docs/deviation-log/2026-07-06-ocr-rag-integration.md` (D2 항목), `CONTRACT.md` 2·3번

## 무엇을 위해서 (목적)

순현님의 OCR 인터페이스(`ocr_interface.py`)가 만드는 `MedicationItem`/`OCRResult`를 내 RAG 파이프라인이
실제로 문제없이 소비할 수 있는지 확인하려고, 실제 OCR 산출물(Mock provider + 실측 CLOVA 캡처본)을
`rag_chain.generate_guide_from_medication()`에 직접 통과시켜보는 통합 테스트를 진행 중이었음.

## 무엇을 하다가 (작업)

OCR 브랜치를 fetch해서 `MockOCRProvider().extract()`를 그대로 호출해 얻은 실제 dataclass
`MedicationItem` 2건을 확인:

```
MedicationItem(drug_name='아스피린', confidence=0.92, diagnosis='고혈압', ...)
MedicationItem(drug_name='로자탄',   confidence=0.78, diagnosis='고혈압', ...)
```

로자탄의 confidence(0.78)는 OCR팀 자체 기준(`_apply_review_flag(threshold=0.80)`, results.md에 명시된
REQ-011)으로 "사람이 검토해야 하는" 낮은 신뢰도다. 이 항목을 실제 OpenAI 키로
`generate_guide_from_medication()`에 넣어 최종 응답을 확인했다.

## 어떠한 문제가 생겼고 (증상)

```python
guide = generate_guide_from_medication(
    MedicationItem(drug_name="로자탄", confidence=0.78, diagnosis="고혈압", ...)
)
print(guide.review_required)   # False   <- 기대: True
print(guide.review_reason)     # None
```

OCR 자체 기준으로는 검토가 필요한 약인데, RAG 최종 응답은 "검토 불필요"로 나왔다. 사람이 이 결과만
보면 오인식 가능성이 있었다는 사실 자체를 알 수 없는 상태였다.

## 그 원인이 무엇이며 (원인 분석)

1. `rag_prototype/schemas.py`의 `MedicationInput`에 `confidence: float` 필드는 있었지만, 이 값을 실제로
   *쓰는* 코드가 없었다. `rag_chain.generate_guide_from_medication()`은 `item.confidence`를
   `MedicationInput.model_validate()`로 파싱만 하고 그 이후 로직(`situation` 조합, `generate_guide()`
   호출) 어디에도 전달하지 않았다.
2. `GuideResponse.review_required`는 오직 `generate_guide()` 내부의 두 조건(① LLM이 참고자료를 인용했는가,
   ② self-consistency 점수가 임계값 이상인가)만으로 결정됐다. 이 두 조건은 "생성 품질"에 대한 것이지
   "OCR이 애초에 약 이름을 얼마나 확신하고 읽었는가"와는 무관한 지표라 로자탄 사례에서는 둘 다 통과했다.
3. 근본적으로는 OCR 쪽 `review_required`도 `overall_confidence`(처방전 전체 평균)만 보기 때문에,
   평균이 임계값을 넘기면(아스피린 0.92 + 로자탄 0.78 → 평균 0.85) 그 안에 개별 저신뢰 약이 있어도
   OCR 단계에서도 걸러지지 않는다. 즉 "OCR도 놓치고 RAG도 놓치는" 이중 사각지대였다.

## 그것을 해결하기 위해서 무엇을 했고 (해결)

이 설계를 어떻게 고칠지 architect/critic 두 서브에이전트로 3라운드 토의를 거쳐 아래로 확정했다
(토의 경과는 `docs/deviation-log/2026-07-06-ocr-rag-integration.md` 참고):

1. `config.py`에 `OCR_CONFIDENCE_REVIEW_THRESHOLD = 0.80` 신설 (OCR의 REQ-011 임계값과 동일 값이지만,
   RAG의 `SELF_CONSISTENCY_SIMILARITY_THRESHOLD=0.75`와는 완전히 다른 의미의 별개 상수임을 주석으로 명시).
2. `rag_chain.py`에 `_merge_ocr_confidence(guide, confidence)` 함수를 신설해 **어댑터
   (`generate_guide_from_medication`) 안에서 후처리로 병합**하는 방식을 택했다. `generate_guide()` 코어
   시그니처는 건드리지 않아 기존 회귀 위험을 없앴다(1라운드에서는 코어에 파라미터를 추가하는 안이었으나,
   2라운드 비판에서 "코어까지 건드릴 필요 없다"는 지적을 받아 3라운드에서 최종적으로 어댑터 병합 방식으로
   변경함).
3. `confidence == 0.0`(Tesseract 폴백처럼 신뢰도 자체가 제공되지 않는 경우)과 `0.0 < confidence < 0.80`
   (신뢰도는 있지만 낮은 경우)을 값으로 구분해 각각 `ocr_confidence_unavailable` / `ocr_low_confidence`
   플래그를 부여했다. (1라운드는 이 구분을 `None` 기본값으로 하려 했으나, OCR `MedicationItem.confidence`가
   항상 float이고 키가 생략되지 않는다는 사실을 재확인해 값 기준으로 바꿨다.)
4. `GuideResponse`에 `review_flags: list[str]`와 `ocr_confidence: float | None`을 추가(둘 다 default
   보유로 기존 스키마·테스트 비파괴).
5. 회귀 테스트 3건 추가: 신뢰도 낮음(0.78) → 검토 강제, 신뢰도 0.0 → unavailable 플래그, 신뢰도 높음(0.92)
   → 기존 상태 보존.

수정 후 재현:
```python
guide = generate_guide_from_medication(
    {"drug_name": "로자탄", "dosage": "50mg", "confidence": 0.78, "diagnosis": "고혈압", ...}
)
assert guide.review_required is True
assert "ocr_low_confidence" in guide.review_flags
assert guide.ocr_confidence == 0.78
```

## 재발 방지를 위해 어떤 것을 했는지 (예방)

1. **계약 문서화**: `CONTRACT.md`를 신설해 OCR↔RAG 필드 매핑, confidence 임계값 두 개(0.80 vs 0.75)의
   각각 다른 의미, `review_required` 이름 충돌과 병합 규약(`ocr_review_required`/`rag_review_required`
   접두어 사용)을 명문화. 두 파트가 다른 브랜치에서 독립 개발되는 한 이런 문서가 유일한 합의 지점이다.
2. **계약 테스트 신설**: `tests/contracts/test_ocr_contract.py` + `ocr_sample_output.json` — OCR 실제
   산출물을 픽스처로 고정해, "RAG가 요구하는 필드가 OCR 산출물 키 집합의 부분집합인가"와 "낮은/높은
   confidence가 실제로 다르게 처리되는가"를 회귀 테스트로 고정. `CONTRACT.md` 5번 항목에 이 픽스처를
   "누가 언제 갱신하는지"(머지 전: OCR 필드 변경 PR에서 알림 / 머지 후: producer 정본을 직접 읽도록 전환)
   프로세스까지 명시 — 프로세스 없는 픽스처는 곧 stale해진다는 2라운드 비판을 반영한 것.
3. **회귀 테스트**: 저신뢰/미제공/고신뢰 3가지 confidence 케이스가 각각 다르게 처리되는지 코드로 고정해,
   향후 리팩터링 시 이 병합 로직이 조용히 빠지는 것을 방지.
4. **문서 내 명시적 프레이밍**: "이건 새 기능이 아니라 OCR의 overall-only 판정 한계에 대한 보완 통제다"라고
   명시해, 나중에 누군가 "OCR이 이미 review_required를 주는데 RAG가 왜 또 체크하지?"라고 오해해 이 로직을
   제거하지 않도록 함.
