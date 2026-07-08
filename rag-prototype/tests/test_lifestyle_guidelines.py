from rag_prototype.chunking import lifestyle_guidelines_to_documents
from rag_prototype.lifestyle_data import load_lifestyle_guidelines
from rag_prototype.schemas import LifestyleGuideline

GUIDELINE = LifestyleGuideline.model_validate(
    {
        "id": "htn-diet-1",
        "disease": "고혈압",
        "disease_code": "hypertension",
        "category": "식이요법",
        "rule": "하루 소금 섭취량을 6g 이하로 줄입니다.",
        "source": "대한고혈압학회 고혈압 진료지침",
    }
)


def test_lifestyle_guidelines_to_documents_metadata_and_content():
    docs = lifestyle_guidelines_to_documents([GUIDELINE])
    doc = docs[0]

    assert doc.metadata["doc_type"] == "lifestyle_guideline"
    assert doc.metadata["guideline_id"] == "htn-diet-1"
    assert doc.metadata["disease_code"] == "hypertension"
    assert "고혈압" in doc.page_content
    assert "소금" in doc.page_content


def test_load_lifestyle_guidelines_from_default_data_file():
    guidelines = load_lifestyle_guidelines()

    assert len(guidelines) > 0
    disease_codes = {g.disease_code for g in guidelines}
    assert {"hypertension", "diabetes", "dyslipidemia", "chronic_kidney_disease"} <= disease_codes
