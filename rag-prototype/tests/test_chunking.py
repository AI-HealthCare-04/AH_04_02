from rag_prototype.chunking import drug_to_documents
from rag_prototype.schemas import DrugInfo

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
