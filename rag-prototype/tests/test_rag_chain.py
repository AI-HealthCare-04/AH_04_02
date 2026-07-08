from unittest.mock import patch

from langchain_core.documents import Document
from rag_prototype.rag_chain import (
    _build_context,
    generate_guide,
    generate_guide_from_medication,
    generate_guides_from_medications,
)
from rag_prototype.schemas import DrugInfo, GuideResponse, HiraDrugMasterEntry

FAKE_DOC = Document(
    page_content="[암로디핀정5밀리그램] 효능·효과: 고혈압에 사용합니다.",
    metadata={
        "item_seq": "1",
        "item_name": "암로디핀정5밀리그램",
        "field": "efcy_qesitm",
        "field_label": "효능·효과",
        "update_de": "2024-01-01",
    },
)

FAKE_LIFESTYLE_DOC = Document(
    page_content="[고혈압 - 식이요법] 하루 소금 섭취량을 6g 이하로 줄입니다.",
    metadata={
        "doc_type": "lifestyle_guideline",
        "guideline_id": "htn-diet-1",
        "disease": "고혈압",
        "disease_code": "hypertension",
        "category": "식이요법",
        "source": "대한고혈압학회 고혈압 진료지침",
    },
)

FAKE_DRUG = DrugInfo.model_validate(
    {
        "itemSeq": "1",
        "itemName": "암로디핀정5밀리그램",
        "entpName": "한미약품",
        "efcyQesitm": "고혈압에 사용합니다.",
    }
)


def test_build_context_falls_back_to_live_mfds_fetch_when_not_ingested():
    """벡터DB에 없는 약이면 식약처 API에서 즉시 조회해 채워 넣고 다시 찾는다."""
    calls = {"n": 0}

    def fake_search_by_item_name(item_name):
        calls["n"] += 1
        return [] if calls["n"] == 1 else [FAKE_DOC]

    with (
        patch("rag_prototype.rag_chain.search_by_item_name", side_effect=fake_search_by_item_name),
        patch("rag_prototype.rag_chain.search_by_name", return_value=[FAKE_DRUG]) as mock_mfds_search,
        patch("rag_prototype.rag_chain.add_documents") as mock_add_documents,
        patch("rag_prototype.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    mock_mfds_search.assert_called_once()
    mock_add_documents.assert_called_once()
    assert len(context_items) == 1
    assert context_items[0]["source_ref"].item_name == "암로디핀정5밀리그램"


FAKE_HIRA_ENTRY = HiraDrugMasterEntry.model_validate(
    {
        "한글상품명": "암로디핀정5밀리그램",
        "업체명": "한미약품",
        "표준코드": "8800000000000",
        "국제표준코드(ATC코드)": "C08CA01",
        "품목허가일자": "2010-01-01",
        "취소일자": "",
    }
)


def test_build_context_enriches_source_ref_with_hira_data_when_matched():
    """e약은요 SourceRef에 HIRA 표준코드/ATC코드/허가상태가 함께 채워진다."""
    with (
        patch("rag_prototype.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag_prototype.rag_chain.search_hira_by_product_name", return_value=[FAKE_HIRA_ENTRY]) as mock_hira,
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    mock_hira.assert_called_once_with("암로디핀정5밀리그램", limit=1)
    source_ref = context_items[0]["source_ref"]
    assert source_ref.hira_standard_code == "8800000000000"
    assert source_ref.hira_atc_code == "C08CA01"
    assert source_ref.hira_active is True


def test_build_context_leaves_hira_fields_none_when_not_matched():
    """HIRA에서 못 찾으면 e약은요 인용 자체는 그대로 두고 HIRA 필드만 None으로 남는다."""
    with (
        patch("rag_prototype.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag_prototype.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    source_ref = context_items[0]["source_ref"]
    assert source_ref.item_name == "암로디핀정5밀리그램"
    assert source_ref.hira_standard_code is None
    assert source_ref.hira_active is None


def test_build_context_hira_lookup_failure_does_not_break_citation():
    """HIRA 조회 자체가 예외를 던져도 e약은요 인용 생성은 막히지 않는다."""
    with (
        patch("rag_prototype.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag_prototype.rag_chain.search_hira_by_product_name", side_effect=RuntimeError("CSV 없음")),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    assert len(context_items) == 1
    assert context_items[0]["source_ref"].hira_standard_code is None


def test_build_context_includes_lifestyle_guidelines_when_diagnosis_matches():
    """진단명이 별칭(예: '고혈압 있음')을 포함하면 해당 disease_code의 생활지침을 컨텍스트에 추가한다."""
    with (
        patch("rag_prototype.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag_prototype.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]) as mock_search_disease,
        patch("rag_prototype.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None, diagnosis="고혈압 있음")

    mock_search_disease.assert_called_once_with("hypertension")
    kinds = {item["kind"] for item in context_items}
    assert kinds == {"drug", "lifestyle"}
    lifestyle_item = next(item for item in context_items if item["kind"] == "lifestyle")
    assert lifestyle_item["source_ref"].guideline_id == "htn-diet-1"
    assert lifestyle_item["source_ref"].disease == "고혈압"


def test_build_context_skips_lifestyle_search_without_diagnosis():
    with (
        patch("rag_prototype.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag_prototype.rag_chain.search_by_disease") as mock_search_disease,
        patch("rag_prototype.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    mock_search_disease.assert_not_called()
    assert all(item["kind"] == "drug" for item in context_items)


def test_generate_guide_dry_run_includes_lifestyle_source_refs():
    """OPENAI_API_KEY가 없는 dry-run 모드에서도 생활지침 인용은 lifestyle_source_refs로 채워진다."""
    with (
        patch("rag_prototype.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag_prototype.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]),
        patch("rag_prototype.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag_prototype.rag_chain.settings.OPENAI_API_KEY", None),
    ):
        guide = generate_guide("암로디핀정5밀리그램", diagnosis="고혈압")

    assert len(guide.source_refs) == 1
    assert guide.source_refs[0].item_name == "암로디핀정5밀리그램"
    assert len(guide.lifestyle_source_refs) == 1
    assert guide.lifestyle_source_refs[0].guideline_id == "htn-diet-1"
    assert "소금" in guide.lifestyle_guide


def test_generate_guide_from_medication_maps_ocr_fields():
    """OCR의 MedicationItem 필드(진단/복용법/약효분류)를 situation으로 조합해 넘긴다."""
    medication = {
        "drug_name": "암로디핀",
        "dosage": "5mg",
        "frequency": "1일 1회",
        "diagnosis": "고혈압",
        "drug_class": "칼슘채널차단제",
        "confidence": 0.92,
    }

    with patch("rag_prototype.rag_chain.generate_guide") as mock_generate:
        generate_guide_from_medication(medication)

    mock_generate.assert_called_once()
    args, kwargs = mock_generate.call_args
    assert args[0] == "암로디핀"
    assert kwargs["dosage"] == "5mg"
    assert "고혈압" in kwargs["situation"]
    assert "1일 1회" in kwargs["situation"]
    assert "칼슘채널차단제" in kwargs["situation"]
    assert kwargs["diagnosis"] == "고혈압"


def test_generate_guide_from_medication_accepts_dataclass_style_object():
    class FakeMedicationItem:
        def __init__(self):
            self.__dict__ = {
                "drug_name": "케이캡",
                "dosage": "50mg",
                "frequency": "",
                "diagnosis": "",
                "drug_class": "",
                "confidence": 0.9,
            }

    with patch("rag_prototype.rag_chain.generate_guide") as mock_generate:
        generate_guide_from_medication(FakeMedicationItem())

    args, kwargs = mock_generate.call_args
    assert args[0] == "케이캡"
    assert kwargs["dosage"] == "50mg"
    assert kwargs["situation"] is None
    assert kwargs["diagnosis"] is None


def _base_guide(**overrides) -> GuideResponse:
    defaults = dict(
        drug_name="로자탄",
        medication_guide="복약 안내",
        lifestyle_guide="생활습관 안내",
        disclaimer="disclaimer",
        review_required=False,
        review_reason=None,
        review_flags=[],
    )
    defaults.update(overrides)
    return GuideResponse(**defaults)


def test_low_ocr_confidence_forces_review():
    """OCR 개별 신뢰도(<0.80)가 낮으면, 인용 근거가 멀쩡해도 review_required가 강제로 True가 된다."""
    with patch("rag_prototype.rag_chain.generate_guide", return_value=_base_guide()):
        guide = generate_guide_from_medication(
            {"drug_name": "로자탄", "confidence": 0.78, "diagnosis": "고혈압"}
        )

    assert guide.review_required is True
    assert "ocr_low_confidence" in guide.review_flags
    assert guide.ocr_confidence == 0.78
    assert "OCR" in guide.review_reason


def test_zero_confidence_marks_unavailable():
    """confidence=0.0(Tesseract 폴백처럼 신뢰도 미제공)은 'low'가 아니라 'unavailable'로 구분된다."""
    with patch("rag_prototype.rag_chain.generate_guide", return_value=_base_guide()):
        guide = generate_guide_from_medication({"drug_name": "암로디핀", "confidence": 0.0})

    assert guide.review_required is True
    assert "ocr_confidence_unavailable" in guide.review_flags
    assert guide.ocr_confidence == 0.0


def test_high_confidence_preserves_review_state():
    """OCR 신뢰도가 임계값 이상이면 기존 review_required/review_flags를 건드리지 않는다."""
    with patch("rag_prototype.rag_chain.generate_guide", return_value=_base_guide()):
        guide = generate_guide_from_medication({"drug_name": "암로디핀", "confidence": 0.92})

    assert guide.review_required is False
    assert guide.review_flags == []
    assert guide.ocr_confidence == 0.92


def test_batch_isolates_failure():
    """여러 약 중 하나가 실패해도 나머지 결과는 정상 반환되고, 실패건만 generation_error로 표시된다."""

    def fake_generate_guide_from_medication(medication):
        if medication["drug_name"] == "실패약":
            raise RuntimeError("MFDS 데이터 없음")
        return _base_guide(drug_name=medication["drug_name"])

    with patch(
        "rag_prototype.rag_chain.generate_guide_from_medication",
        side_effect=fake_generate_guide_from_medication,
    ):
        guides = generate_guides_from_medications(
            [{"drug_name": "정상약"}, {"drug_name": "실패약"}]
        )

    assert len(guides) == 2
    assert guides[0].drug_name == "정상약"
    assert guides[0].review_flags == []
    assert guides[1].drug_name == "실패약"
    assert guides[1].review_required is True
    assert guides[1].review_flags == ["generation_error"]
