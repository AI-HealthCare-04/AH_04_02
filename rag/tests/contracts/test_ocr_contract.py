"""OCR(origin/feature/ocr-day1-setup_soonhyun) <-> RAG 필드 계약 테스트.

OCR의 ocr_interface.py는 다른 브랜치에 있어 이 저장소에서 직접 import할 수 없으므로,
실제 산출물을 ocr_sample_output.json으로 복사해 픽스처로 고정한다. 두 브랜치가 dev로
머지되면 이 파일을 producer(OCR) 정본을 직접 읽는 방식으로 전환할 것 (contract.md 참고).

pydantic의 MedicationInput은 기본 extra="ignore"라 값만 비교해서는 OCR 쪽 필드
rename/삭제를 못 잡는다. 그래서 값 검증과 별개로 "RAG가 필요로 하는 필드 키 집합이
OCR dict의 키 집합의 부분집합인가"를 명시적으로 확인한다.
"""

import json
from pathlib import Path
from unittest.mock import patch

from rag.rag_chain import generate_guide_from_medication
from rag.schemas import GuideResponse, MedicationInput

FIXTURE_PATH = Path(__file__).parent / "ocr_sample_output.json"


def _load_sample() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_medication_input_fields_are_subset_of_ocr_output_keys():
    """RAG가 요구하는 필드명이 OCR이 실제로 내려주는 키 집합에 전부 포함되는지 확인한다.

    이 검증이 없으면, OCR이 필드명을 바꾸거나 빼도(extra="ignore" 때문에) 조용히
    무시되고 기본값으로 대체되어 알아채기 어렵다.
    """
    sample = _load_sample()
    ocr_keys = set(sample["medications"][0].keys())
    required_fields = set(MedicationInput.model_fields.keys())

    assert required_fields <= ocr_keys, f"OCR 산출물에 없는 필드: {required_fields - ocr_keys}"


def test_ocr_medications_pass_through_adapter_without_error():
    """실제 OCR mock 산출물 각 항목이 어댑터를 예외 없이 통과하고, confidence가 반영되는지 확인한다."""
    sample = _load_sample()

    fake_guide = GuideResponse(
        drug_name="placeholder",
        medication_guide="",
        disclaimer="disclaimer",
    )

    with patch("rag.rag_chain.generate_guide", return_value=fake_guide):
        guides = [generate_guide_from_medication(item) for item in sample["medications"]]

    assert len(guides) == len(sample["medications"])
    # 고정 픽스처 기준: 아스피린(0.92, 임계값 이상)은 그대로, 로자탄(0.78, 임계값 미만)은 검토 강제
    aspirin_guide, losartan_guide = guides
    assert aspirin_guide.ocr_confidence == 0.92
    assert aspirin_guide.review_required is False
    assert losartan_guide.ocr_confidence == 0.78
    assert losartan_guide.review_required is True
    assert "ocr_low_confidence" in losartan_guide.review_flags
