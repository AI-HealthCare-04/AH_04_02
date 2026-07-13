from unittest.mock import patch

from langchain_core.documents import Document
from rag.rag_chain import (
    _build_context,
    _check_dur_cautions,
    _check_dur_taboo,
    generate_guide,
    generate_guide_from_medication,
    generate_guides_from_medications,
)
from rag.schemas import DrugInfo, DurCaution, DurTabooInfo, GuideResponse, HiraDrugMasterEntry

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
        patch("rag.rag_chain.search_by_item_name", side_effect=fake_search_by_item_name),
        patch("rag.rag_chain.search_by_name", return_value=[FAKE_DRUG]) as mock_mfds_search,
        patch("rag.rag_chain.add_documents") as mock_add_documents,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
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
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[FAKE_HIRA_ENTRY]) as mock_hira,
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
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    source_ref = context_items[0]["source_ref"]
    assert source_ref.item_name == "암로디핀정5밀리그램"
    assert source_ref.hira_standard_code is None
    assert source_ref.hira_active is None


def test_build_context_hira_lookup_failure_does_not_break_citation():
    """HIRA 조회 자체가 예외를 던져도 e약은요 인용 생성은 막히지 않는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", side_effect=RuntimeError("CSV 없음")),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    assert len(context_items) == 1
    assert context_items[0]["source_ref"].hira_standard_code is None


def test_build_context_includes_lifestyle_guidelines_when_diagnosis_matches():
    """진단명이 별칭(예: '고혈압 있음')을 포함하면 해당 disease_code의 생활지침을 컨텍스트에 추가한다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]) as mock_search_disease,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None, diagnosis="고혈압 있음")

    mock_search_disease.assert_called_once_with("hypertension")
    kinds = {item["kind"] for item in context_items}
    assert kinds == {"drug", "lifestyle"}
    lifestyle_item = next(item for item in context_items if item["kind"] == "lifestyle")
    assert lifestyle_item["source_ref"].guideline_id == "htn-diet-1"
    assert lifestyle_item["source_ref"].disease == "고혈압"


FAKE_KDCA_DOC = Document(
    page_content="[관절염 - 개요정의] 관절염은 관절에 염증이 생기는 질환입니다.",
    metadata={
        "doc_type": "kdca_health_info",
        "cntnts_sn": "1234",
        "title": "관절염",
        "section_name": "개요정의",
        "section_sn": "10",
        "index": 0,
        "source": "질병관리청 국가건강정보포털",
        "source_url": "https://health.kdca.go.kr/example",
    },
)


def test_build_context_falls_back_to_kdca_when_curated_lifestyle_has_no_match():
    """등록된 4개 질환에 없는 진단명이면 질병관리청 건강정보 전체 수집분에서 유사도 검색으로 보강한다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease", return_value=[]),
        patch("rag.rag_chain.search_kdca_health_info", return_value=[FAKE_KDCA_DOC]) as mock_kdca_search,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None, diagnosis="관절염")

    mock_kdca_search.assert_called_once_with("관절염", k=3)
    lifestyle_item = next(item for item in context_items if item["kind"] == "lifestyle")
    assert lifestyle_item["source_ref"].disease == "관절염"
    assert lifestyle_item["source_ref"].category == "개요정의"
    assert "kdca-1234-10-0" == lifestyle_item["source_ref"].guideline_id


def test_build_context_skips_kdca_fallback_when_curated_lifestyle_found():
    """등록된 4개 질환으로 이미 생활지침을 찾았으면 질병관리청 전체 검색은 호출하지 않는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]),
        patch("rag.rag_chain.search_kdca_health_info") as mock_kdca_search,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        _build_context("암로디핀정5밀리그램", situation=None, diagnosis="고혈압 있음")

    mock_kdca_search.assert_not_called()


def test_build_context_skips_kdca_fallback_without_diagnosis():
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease", return_value=[]),
        patch("rag.rag_chain.search_kdca_health_info") as mock_kdca_search,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        _build_context("암로디핀정5밀리그램", situation=None, diagnosis=None)

    mock_kdca_search.assert_not_called()


def test_build_context_skips_lifestyle_search_without_diagnosis():
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease") as mock_search_disease,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    mock_search_disease.assert_not_called()
    assert all(item["kind"] == "drug" for item in context_items)


def test_generate_guide_dry_run_includes_lifestyle_source_refs():
    """OPENAI_API_KEY가 없는 dry-run 모드에서도 생활지침 인용은 lifestyle_source_refs로 채워진다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.settings.OPENAI_API_KEY", None),
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

    with patch("rag.rag_chain.generate_guide") as mock_generate:
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

    with patch("rag.rag_chain.generate_guide") as mock_generate:
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
    with patch("rag.rag_chain.generate_guide", return_value=_base_guide()):
        guide = generate_guide_from_medication(
            {"drug_name": "로자탄", "confidence": 0.78, "diagnosis": "고혈압"}
        )

    assert guide.review_required is True
    assert "ocr_low_confidence" in guide.review_flags
    assert guide.ocr_confidence == 0.78
    assert "OCR" in guide.review_reason


def test_zero_confidence_marks_unavailable():
    """confidence=0.0(Tesseract 폴백처럼 신뢰도 미제공)은 'low'가 아니라 'unavailable'로 구분된다."""
    with patch("rag.rag_chain.generate_guide", return_value=_base_guide()):
        guide = generate_guide_from_medication({"drug_name": "암로디핀", "confidence": 0.0})

    assert guide.review_required is True
    assert "ocr_confidence_unavailable" in guide.review_flags
    assert guide.ocr_confidence == 0.0


def test_high_confidence_preserves_review_state():
    """OCR 신뢰도가 임계값 이상이면 기존 review_required/review_flags를 건드리지 않는다."""
    with patch("rag.rag_chain.generate_guide", return_value=_base_guide()):
        guide = generate_guide_from_medication({"drug_name": "암로디핀", "confidence": 0.92})

    assert guide.review_required is False
    assert guide.review_flags == []
    assert guide.ocr_confidence == 0.92


def test_batch_isolates_failure():
    """여러 약 중 하나가 실패해도 나머지 결과는 정상 반환되고, 실패건만 generation_error로 표시된다."""

    def fake_generate_guide_from_medication(medication, other_drug_names=None):
        if medication["drug_name"] == "실패약":
            raise RuntimeError("MFDS 데이터 없음")
        return _base_guide(drug_name=medication["drug_name"])

    with patch(
        "rag.rag_chain.generate_guide_from_medication",
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


def _dur_entry(**overrides) -> DurTabooInfo:
    defaults = dict(item_name="와파린정", mixture_item_name="아스피린정", prohbt_content="출혈 위험 증가")
    defaults.update(overrides)
    return DurTabooInfo(**defaults)


def test_check_dur_taboo_warns_when_mixture_partner_is_in_prescription():
    """DUR이 알려주는 금기 상대가 이 처방전에 실제로 있을 때만 경고를 만든다."""
    with patch("rag.rag_chain.search_usjnt_taboo", return_value=[_dur_entry()]):
        warnings = _check_dur_taboo("와파린", other_drug_names=["아스피린정"])

    assert len(warnings) == 1
    assert warnings[0].mixture_item_name == "아스피린정"
    assert warnings[0].prohbt_content == "출혈 위험 증가"


def test_check_dur_taboo_dedupes_brand_variants_by_reason():
    """CSV가 브랜드(제품) 단위라 같은 성분의 여러 제조사 제품이 각각 한 행씩 나올 수 있다 —
    처방전에 적힌 이름(other_drug_names) + 사유 기준으로 한 번만 경고해야 한다."""
    entries = [
        _dur_entry(mixture_item_name="유한메토트렉세이트주사액25밀리그람/밀리리터_(50mg/2mL)", prohbt_content="혈액학적 독성"),
        _dur_entry(mixture_item_name="화이자메토트렉세이트주25mg/mL_(0.5g/20mL)", prohbt_content="혈액학적 독성"),
        _dur_entry(mixture_item_name="엠티엑스주(메토트렉세이트)_(0.5g/20mL)", prohbt_content="혈액학적 독성"),
    ]
    with patch("rag.rag_chain.search_usjnt_taboo", return_value=entries):
        warnings = _check_dur_taboo("아스피린", other_drug_names=["메토트렉세이트"])

    assert len(warnings) == 1
    assert warnings[0].mixture_item_name == "메토트렉세이트"  # 브랜드명이 아니라 처방전에 적힌 이름
    assert warnings[0].prohbt_content == "혈액학적 독성"


def test_check_dur_taboo_silent_when_mixture_partner_not_in_prescription():
    """DUR에 금기 상대가 있어도, 이 환자가 그 약을 같이 안 먹으면 경고하지 않는다."""
    with patch("rag.rag_chain.search_usjnt_taboo", return_value=[_dur_entry()]):
        warnings = _check_dur_taboo("와파린", other_drug_names=["로자탄"])

    assert warnings == []


def test_check_dur_taboo_returns_empty_without_other_drugs():
    """비교 대상 약이 없으면(단일 약 조회 등) DUR API 자체를 호출하지 않는다."""
    with patch("rag.rag_chain.search_usjnt_taboo") as mock_search:
        warnings = _check_dur_taboo("와파린", other_drug_names=[])

    mock_search.assert_not_called()
    assert warnings == []


def test_check_dur_taboo_fails_silently_when_api_errors():
    """[활용신청 승인 전 상태와 동일한 시나리오] DUR 조회가 예외를 던져도 가이드 생성은 안 막힌다."""
    with patch("rag.rag_chain.search_usjnt_taboo", side_effect=RuntimeError("403 Forbidden")):
        warnings = _check_dur_taboo("와파린", other_drug_names=["아스피린정"])

    assert warnings == []


def test_generate_guide_from_medication_adds_dur_warning_and_forces_review():
    """배치 처리 중 병용금기가 확인되면 review_required가 강제로 True가 되고 사유가 남는다."""
    with (
        patch("rag.rag_chain.generate_guide", return_value=_base_guide(drug_name="와파린")),
        patch("rag.rag_chain.search_usjnt_taboo", return_value=[_dur_entry()]),
    ):
        guide = generate_guide_from_medication(
            {"drug_name": "와파린", "confidence": 0.95}, other_drug_names=["아스피린정"]
        )

    assert guide.review_required is True
    assert "dur_taboo_warning" in guide.review_flags
    assert len(guide.dur_warnings) == 1
    assert guide.dur_warnings[0].mixture_item_name == "아스피린정"


def test_generate_guides_from_medications_passes_sibling_drug_names():
    """배치의 각 약에게 '나머지 약들'의 이름이 정확히 전달되는지(자기 자신은 제외) 확인한다."""
    with patch("rag.rag_chain.generate_guide_from_medication") as mock_generate:
        mock_generate.side_effect = lambda medication, other_drug_names=None: _base_guide(
            drug_name=medication["drug_name"]
        )
        generate_guides_from_medications(
            [{"drug_name": "와파린"}, {"drug_name": "아스피린"}, {"drug_name": "로자탄"}]
        )

    calls = mock_generate.call_args_list
    assert calls[0].kwargs["other_drug_names"] == ["아스피린", "로자탄"]
    assert calls[1].kwargs["other_drug_names"] == ["와파린", "로자탄"]
    assert calls[2].kwargs["other_drug_names"] == ["와파린", "아스피린"]


def _caution(**overrides) -> DurCaution:
    defaults = dict(item_name="솔리페나신", category="노인주의", detail="항콜린 부작용 증가")
    defaults.update(overrides)
    return DurCaution(**defaults)


def test_check_dur_cautions_aggregates_all_three_sources():
    """노인주의·연령금기·임부금기 세 소스 결과를 전부 합쳐서 돌려준다."""
    with (
        patch("rag.rag_chain.search_elderly_caution", return_value=[_caution(category="노인주의")]),
        patch("rag.rag_chain.search_age_taboo", return_value=[_caution(category="연령금기", extra="18세 미만")]),
        patch("rag.rag_chain.search_pregnancy_taboo", return_value=[_caution(category="임부금기", extra="금기등급 1")]),
    ):
        cautions = _check_dur_cautions("솔리페나신")

    assert len(cautions) == 3
    assert {c.category for c in cautions} == {"노인주의", "연령금기", "임부금기"}


def test_check_dur_cautions_one_source_failing_does_not_block_others():
    """세 소스 중 하나가 실패(CSV 부재 등)해도 나머지 결과는 정상 반환된다."""
    with (
        patch("rag.rag_chain.search_elderly_caution", side_effect=FileNotFoundError("no csv")),
        patch("rag.rag_chain.search_age_taboo", return_value=[_caution(category="연령금기")]),
        patch("rag.rag_chain.search_pregnancy_taboo", return_value=[]),
    ):
        cautions = _check_dur_cautions("솔리페나신")

    assert len(cautions) == 1
    assert cautions[0].category == "연령금기"


def test_generate_guide_from_medication_adds_dur_caution_and_forces_review():
    """DUR 주의사항(노인주의 등)이 있으면 review_required가 강제로 True가 되고 사유가 남는다."""
    with (
        patch("rag.rag_chain.generate_guide", return_value=_base_guide(drug_name="솔리페나신")),
        patch("rag.rag_chain.search_usjnt_taboo", return_value=[]),
        patch("rag.rag_chain.search_elderly_caution", return_value=[_caution()]),
        patch("rag.rag_chain.search_age_taboo", return_value=[]),
        patch("rag.rag_chain.search_pregnancy_taboo", return_value=[]),
    ):
        guide = generate_guide_from_medication({"drug_name": "솔리페나신", "confidence": 0.95})

    assert guide.review_required is True
    assert "dur_caution" in guide.review_flags
    assert len(guide.dur_cautions) == 1
    assert guide.dur_cautions[0].category == "노인주의"
