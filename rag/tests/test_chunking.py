from rag.chunking import drug_to_documents, kdca_health_info_sections_to_documents
from rag.kdca_health_info_data import load_kdca_health_info_sections
from rag.schemas import DrugInfo
from pathlib import Path

KDCA_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kdca_healthinfo_sample.jsonl"

DRUG = DrugInfo.model_validate(
    {
        "itemSeq": "195700020",
        "itemName": "활명수",
        "entpName": "동화약품(주)",
        "efcyQesitm": "소화불량에 사용합니다.",
        "useMethodQesitm": "1회 1병 복용합니다.",
        "atpnWarnQesitm": None,
        "atpnQesitm": "임부는 상의하십시오.",
        "intrcQesitm": None,
        "seQesitm": None,
        "depositMethodQesitm": "실온 보관하십시오.",
        "updateDe": "2024-05-09",
    }
)


def test_drug_to_documents_skips_empty_fields():
    docs = drug_to_documents(DRUG)
    fields = {doc.metadata["field"] for doc in docs}

    assert "atpn_warn_qesitm" not in fields
    assert "intrc_qesitm" not in fields
    assert "se_qesitm" not in fields
    assert fields == {"efcy_qesitm", "use_method_qesitm", "atpn_qesitm", "deposit_method_qesitm"}


def test_drug_to_documents_metadata_and_content():
    docs = drug_to_documents(DRUG)
    efcy_doc = next(doc for doc in docs if doc.metadata["field"] == "efcy_qesitm")

    assert efcy_doc.metadata["item_seq"] == "195700020"
    assert efcy_doc.metadata["item_name"] == "활명수"
    assert "활명수" in efcy_doc.page_content
    assert "소화불량" in efcy_doc.page_content


def test_kdca_health_info_sections_to_documents_strips_html_and_skips_images():
    sections = load_kdca_health_info_sections(KDCA_FIXTURE_PATH)
    docs = kdca_health_info_sections_to_documents(sections)

    # 3개 섹션(개요정의/개요원인-이미지/개요원인-텍스트) 중 순수 이미지 섹션 1건은 제외되어야 함
    edema_docs = [d for d in docs if d.metadata["cntnts_sn"] == "6544"]
    assert len(edema_docs) == 2
    assert all("<" not in d.page_content.split("] ", 1)[1] for d in edema_docs)


def test_kdca_health_info_section_to_document_metadata_and_content():
    sections = load_kdca_health_info_sections(KDCA_FIXTURE_PATH)
    docs = kdca_health_info_sections_to_documents(sections)
    cold_doc = next(d for d in docs if d.metadata["cntnts_sn"] == "5423")

    assert cold_doc.metadata["doc_type"] == "kdca_health_info"
    assert cold_doc.metadata["title"] == "감기"
    assert cold_doc.metadata["section_name"] == "개요정의"
    assert cold_doc.metadata["source"] == "질병관리청 국가건강정보포털"
    assert "[감기 - 개요정의]" in cold_doc.page_content
    assert "바이러스" in cold_doc.page_content
