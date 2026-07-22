import inspect
from unittest.mock import patch

from langchain_core.documents import Document
from rag.rag_chain import (
    _build_context,
    _check_dur_cautions,
    _check_dur_taboo,
    generate_guide,
    generate_guide_from_medication,
    generate_guides_from_medications,
    generate_lifestyle_guide_for_diagnosis,
)
from rag.schemas import (
    DrugInfo,
    DrugPermitDetail,
    DrugPermitInfo,
    DurCaution,
    DurTabooInfo,
    GuideResponse,
    HiraDrugMasterEntry,
    LifestyleGuideResult,
    SourceRef,
)

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


FAKE_PERMIT_ENTRY = DrugPermitInfo.model_validate(
    {
        "ITEM_SEQ": "202106092",
        "ITEM_NAME": "암로디핀정5밀리그램",
        "ENTP_NAME": "한미약품",
        "PERMIT_KIND_CODE": "신고",
        "CANCEL_DATE": None,
        "CANCEL_NAME": "정상",
    }
)


def test_build_context_enriches_source_ref_with_permit_data_when_matched():
    """[2026-07-14 추가] e약은요 SourceRef에 허가정보(허가/신고 구분, 정상여부)가 함께 채워진다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.search_permit_info", return_value=[FAKE_PERMIT_ENTRY]) as mock_permit,
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    mock_permit.assert_called_once_with("암로디핀정5밀리그램", num_of_rows=1)
    source_ref = context_items[0]["source_ref"]
    assert source_ref.permit_kind_code == "신고"
    assert source_ref.permit_active is True


def test_build_context_leaves_permit_fields_none_when_not_matched():
    """허가정보에서 못 찾으면 e약은요 인용 자체는 그대로 두고 허가정보 필드만 None으로 남는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.search_permit_info", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    source_ref = context_items[0]["source_ref"]
    assert source_ref.item_name == "암로디핀정5밀리그램"
    assert source_ref.permit_kind_code is None
    assert source_ref.permit_active is None


def test_build_context_permit_lookup_failure_does_not_break_citation():
    """허가정보 조회 자체가 예외를 던져도 e약은요 인용 생성은 막히지 않는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.search_permit_info", side_effect=RuntimeError("API 오류")),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    assert len(context_items) == 1
    assert context_items[0]["source_ref"].permit_active is None


FAKE_PERMIT_DETAIL = DrugPermitDetail.model_validate(
    {
        "ITEM_SEQ": "1",
        "ITEM_NAME": "암로디핀정5밀리그램",
        "NB_DOC_DATA": (
            '<DOC title="사용상의주의사항" type="NB"><SECTION title="">'
            '<ARTICLE title="1. 경고"><PARAGRAPH tagName="p">과량 복용 시 저혈압이 나타날 수 있습니다.'
            "</PARAGRAPH></ARTICLE></SECTION></DOC>"
        ),
    }
)


def test_build_context_adds_permit_precaution_sections_when_matched():
    """[2026-07-14 추가] 허가정보 상세(NB_DOC_DATA)의 사용상의주의사항 섹션이 추가 인용으로 붙는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.search_permit_info", return_value=[]),
        patch("rag.rag_chain.search_permit_detail", return_value=[FAKE_PERMIT_DETAIL]) as mock_detail,
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    mock_detail.assert_called_once_with("암로디핀정5밀리그램", num_of_rows=1)
    assert len(context_items) == 2
    precaution_item = context_items[1]
    assert precaution_item["kind"] == "drug"
    assert precaution_item["source_ref"].field == "사용상의주의사항 - 1. 경고"
    assert precaution_item["source_ref"].item_name == "암로디핀정5밀리그램"
    assert precaution_item["text"] == "과량 복용 시 저혈압이 나타날 수 있습니다."


def test_build_context_adds_no_precaution_items_when_detail_not_matched():
    """상세정보에서 못 찾거나(빈 리스트) NB_DOC_DATA가 없으면 추가 인용 없이 e약은요 인용만 남는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.search_permit_info", return_value=[]),
        patch("rag.rag_chain.search_permit_detail", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    assert len(context_items) == 1


def test_generate_guide_falls_back_to_permit_precaution_when_llm_omits_precautions():
    """LLM이 precautions를 비워도 사용상의주의사항 근거가 있으면 화면에 표시할 주의문구를 보강한다."""
    context_items = [
        {
            "kind": "drug",
            "idx": 1,
            "text": "과량 복용 시 저혈압이 나타날 수 있습니다.",
            "source_ref": SourceRef(
                item_seq="1",
                item_name="암로디핀정5밀리그램",
                field="사용상의주의사항 - 1. 경고",
            ),
        }
    ]

    with (
        patch("rag.rag_chain._build_context", return_value=context_items),
        patch("rag.rag_chain.settings.OPENAI_API_KEY", "test-key"),
        patch("rag.rag_chain.settings.SELF_CONSISTENCY_SAMPLES", 1),
        patch("langchain_openai.ChatOpenAI", return_value=object()),
        patch(
            "rag.rag_chain._llm_generate_once",
            return_value={
                "medication_guide": "암로디핀은 고혈압 치료에 사용합니다.",
                "precautions": [],
                "source_refs": [1],
            },
        ),
    ):
        guide = generate_guide("암로디핀정5밀리그램")

    assert guide.precautions == ["과량 복용 시 저혈압이 나타날 수 있습니다."]
    assert guide.source_refs[0].field == "사용상의주의사항 - 1. 경고"


def test_build_context_permit_detail_lookup_failure_does_not_break_citation():
    """상세정보 조회 자체가 예외를 던져도 e약은요 인용 생성은 막히지 않는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.search_permit_info", return_value=[]),
        patch("rag.rag_chain.search_permit_detail", side_effect=RuntimeError("API 오류")),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None)

    assert len(context_items) == 1


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


def test_build_context_uses_kdca_as_primary_lifestyle_source():
    """[2026-07-21] 질병관리청 건강정보(실제 수집분)를 생활습관 안내의 최우선 소스로 조회한다."""
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


FAKE_OSTEOPOROSIS_KDCA_DOC = Document(
    page_content="[골다공증 - 운동요법] 체중 부하 운동을 주 3회 이상 꾸준히 합니다.",
    metadata={
        "doc_type": "kdca_health_info",
        "cntnts_sn": "5678",
        "title": "골다공증",
        "section_name": "운동요법",
        "section_sn": "20",
        "index": 0,
        "source": "질병관리청 국가건강정보포털",
        "source_url": "https://health.kdca.go.kr/example-osteoporosis",
    },
)


def test_build_context_falls_back_to_kdca_for_osteoporosis_not_in_curated_alias_list():
    """[2026-07-20 사용자 재현 케이스] '골다공증'은 DIAGNOSIS_DISEASE_ALIASES 4개 질환에
    없어 search_by_disease로는 못 찾지만, search_kdca_health_info(전체 수집분 의미기반
    검색)로 생활습관 안내가 보강되는지 확인한다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease", return_value=[]) as mock_curated,
        patch("rag.rag_chain.search_kdca_health_info", return_value=[FAKE_OSTEOPOROSIS_KDCA_DOC]) as mock_kdca_search,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None, diagnosis="골다공증")

    mock_curated.assert_not_called()  # "골다공증"은 별칭에 없으므로 disease_code 자체가 안 나옴
    mock_kdca_search.assert_called_once_with("골다공증", k=3)
    lifestyle_item = next(item for item in context_items if item["kind"] == "lifestyle")
    assert lifestyle_item["source_ref"].disease == "골다공증"
    assert lifestyle_item["source_ref"].category == "운동요법"
    assert "체중 부하 운동" in lifestyle_item["text"]


def test_build_context_prefers_kdca_over_curated_lifestyle_when_both_match():
    """[2026-07-21] curated(학회 요약, 미검증 2차 가공 데이터)에도 매칭이 있어도, 질병관리청
    검색에서 이미 찾았으면 그걸 쓰고 curated 조회는 아예 하지 않는다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_kdca_health_info", return_value=[FAKE_KDCA_DOC]) as mock_kdca_search,
        patch("rag.rag_chain.search_by_disease") as mock_search_disease,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None, diagnosis="고혈압 있음")

    mock_kdca_search.assert_called_once_with("고혈압 있음", k=3)
    mock_search_disease.assert_not_called()
    lifestyle_item = next(item for item in context_items if item["kind"] == "lifestyle")
    assert lifestyle_item["source_ref"].source == "질병관리청 국가건강정보포털"


def test_build_context_falls_back_to_curated_lifestyle_when_kdca_has_no_match():
    """등록된 4개 질환이어도, 질병관리청 검색에서 못 찾을 때만 curated 학회 요약으로 보강한다."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_kdca_health_info", return_value=[]) as mock_kdca_search,
        patch("rag.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]) as mock_search_disease,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
    ):
        context_items = _build_context("암로디핀정5밀리그램", situation=None, diagnosis="고혈압 있음")

    mock_kdca_search.assert_called_once_with("고혈압 있음", k=3)
    mock_search_disease.assert_called_once_with("hypertension")
    lifestyle_item = next(item for item in context_items if item["kind"] == "lifestyle")
    assert lifestyle_item["source_ref"].guideline_id == "htn-diet-1"
    assert lifestyle_item["source_ref"].disease == "고혈압"


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


def test_generate_guide_does_not_search_lifestyle_context():
    """[2026-07-21 회의 반영] generate_guide()(의약품 전용)는 이제 생활습관 컨텍스트를
    전혀 조회하지 않는다 — 그 진단명이 매칭돼도 search_by_disease/search_kdca_health_info를
    호출하지 않아야 하고, 결과 GuideResponse에는 lifestyle_guide/lifestyle_source_refs
    필드 자체가 없다(스키마에서 제거됨)."""
    with (
        patch("rag.rag_chain.search_by_item_name", return_value=[FAKE_DOC]),
        patch("rag.rag_chain.search_by_disease") as mock_curated,
        patch("rag.rag_chain.search_kdca_health_info") as mock_kdca,
        patch("rag.rag_chain.search_hira_by_product_name", return_value=[]),
        patch("rag.rag_chain.settings.OPENAI_API_KEY", None),
    ):
        guide = generate_guide("암로디핀정5밀리그램", diagnosis="고혈압")

    mock_curated.assert_not_called()
    mock_kdca.assert_not_called()
    assert len(guide.source_refs) == 1
    assert guide.source_refs[0].item_name == "암로디핀정5밀리그램"
    assert "lifestyle_guide" not in GuideResponse.model_fields
    assert "lifestyle_source_refs" not in GuideResponse.model_fields


def test_generate_lifestyle_guide_for_diagnosis_dry_run_uses_context_text():
    """OPENAI_API_KEY가 없는 dry-run 모드에서도 생활지침 인용·본문이 그대로 채워진다."""
    with (
        patch("rag.rag_chain.search_kdca_health_info", return_value=[]),
        patch("rag.rag_chain.search_by_disease", return_value=[FAKE_LIFESTYLE_DOC]),
        patch("rag.rag_chain.settings.OPENAI_API_KEY", None),
    ):
        result = generate_lifestyle_guide_for_diagnosis("고혈압")

    assert result.diagnosis == "고혈압"
    assert len(result.source_refs) == 1
    assert result.source_refs[0].guideline_id == "htn-diet-1"
    assert "소금" in result.guide
    assert "dry_run" in result.review_flags


def test_generate_lifestyle_guide_for_diagnosis_has_no_drug_name_param():
    """[2026-07-21 회의 반영] 생활습관 안내는 의약품과 무관하게 진단명만으로 생성돼야
    한다 — 함수 시그니처 자체가 drug_name을 받지 않도록 구조적으로 고정한다."""
    params = list(inspect.signature(generate_lifestyle_guide_for_diagnosis).parameters)
    assert params == ["diagnosis"]


def test_generate_lifestyle_guide_for_diagnosis_falls_back_safely_without_diagnosis():
    """진단명이 없으면 검색을 시도하지 않고(지어내지 않고) 안전한 일반 안내로 즉시 대체한다."""
    with (
        patch("rag.rag_chain.search_kdca_health_info") as mock_kdca,
        patch("rag.rag_chain.search_by_disease") as mock_curated,
    ):
        result = generate_lifestyle_guide_for_diagnosis(None)

    mock_kdca.assert_not_called()
    mock_curated.assert_not_called()
    assert result.diagnosis == ""
    assert result.review_required is True
    assert "no_diagnosis" in result.review_flags
    assert "진단명" in result.guide


def test_generate_lifestyle_guide_for_diagnosis_falls_back_safely_when_no_context_found():
    """진단명은 있지만 매칭되는 생활지침이 하나도 없으면, 지어내지 않고 안전한 안내로 대체한다."""
    with (
        patch("rag.rag_chain.search_kdca_health_info", return_value=[]),
        patch("rag.rag_chain.search_by_disease", return_value=[]),
    ):
        result = generate_lifestyle_guide_for_diagnosis("희귀질환예시")

    assert result.diagnosis == "희귀질환예시"
    assert result.review_required is True
    assert "no_lifestyle_context" in result.review_flags
    assert result.source_refs == []


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
        guides, lifestyle_guides = generate_guides_from_medications(
            [{"drug_name": "정상약"}, {"drug_name": "실패약"}]
        )

    assert len(guides) == 2
    assert guides[0].drug_name == "정상약"
    assert guides[0].review_flags == []
    assert guides[1].drug_name == "실패약"
    assert guides[1].review_required is True
    assert guides[1].review_flags == ["generation_error"]
    # 진단명이 하나도 없으므로(둘 다 diagnosis 미지정) 안전한 폴백 안내 1건만 반환된다.
    assert len(lifestyle_guides) == 1
    assert lifestyle_guides[0].diagnosis == ""
    assert "no_diagnosis" in lifestyle_guides[0].review_flags


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


def test_generate_guides_from_medications_generates_lifestyle_once_per_unique_diagnosis():
    """[2026-07-21 회의 반영, 핵심 회귀 테스트] 여러 약이 같은 진단명을 공유해도 생활습관
    안내는 진단명당 한 번만 생성돼야 한다 — "의약품별"이 아니라 "진단명별"이라는 요구사항의
    직접적인 검증. 서로 다른 진단명(고혈압/당뇨병)은 각각 한 번씩, 총 2번만 호출된다."""
    medications = [
        {"drug_name": "암로디핀", "diagnosis": "고혈압"},
        {"drug_name": "로자탄", "diagnosis": "고혈압"},  # 고혈압 중복 — 재생성되면 안 됨
        {"drug_name": "메트포르민", "diagnosis": "당뇨병"},
    ]
    with (
        patch("rag.rag_chain.generate_guide_from_medication") as mock_generate_guide,
        patch("rag.rag_chain.generate_lifestyle_guide_for_diagnosis") as mock_generate_lifestyle,
    ):
        mock_generate_guide.side_effect = lambda medication, other_drug_names=None: _base_guide(
            drug_name=medication["drug_name"]
        )
        mock_generate_lifestyle.side_effect = lambda diagnosis: LifestyleGuideResult(
            diagnosis=diagnosis or "", guide=f"{diagnosis} 생활습관 안내"
        )
        guides, lifestyle_guides = generate_guides_from_medications(medications)

    assert len(guides) == 3  # 의약품별 가이드는 여전히 3개(약 개수만큼)
    assert mock_generate_lifestyle.call_count == 2  # 생활습관은 고유 진단명(2개)만큼만 호출
    called_diagnoses = [c.args[0] for c in mock_generate_lifestyle.call_args_list]
    assert called_diagnoses == ["고혈압", "당뇨병"]  # 첫 등장 순서, 중복 없음
    assert [lg.diagnosis for lg in lifestyle_guides] == ["고혈압", "당뇨병"]


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
