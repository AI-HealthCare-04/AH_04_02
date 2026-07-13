from langchain_core.documents import Document

from rag.schemas import DRUG_FIELD_LABELS, DrugInfo, LifestyleGuideline


def drug_to_documents(drug: DrugInfo) -> list[Document]:
    """의약품 1건을 필드별 Document로 분할합니다 (필드별로 출처 추적이 가능하도록)."""
    documents: list[Document] = []
    for field_name, label in DRUG_FIELD_LABELS.items():
        text = getattr(drug, field_name)
        if not text or not text.strip():
            continue
        content = f"[{drug.item_name}] {label}: {text.strip()}"
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "item_seq": drug.item_seq,
                    "item_name": drug.item_name,
                    "entp_name": drug.entp_name,
                    "field": field_name,
                    "field_label": label,
                    "update_de": drug.update_de or "",
                },
            )
        )
    return documents


def drugs_to_documents(drugs: list[DrugInfo]) -> list[Document]:
    documents: list[Document] = []
    for drug in drugs:
        documents.extend(drug_to_documents(drug))
    return documents


def lifestyle_guideline_to_document(guideline: LifestyleGuideline) -> Document:
    """만성질환 생활지침 1건을 Document로 변환합니다 (질환·항목별로 출처 추적이 가능하도록)."""
    content = f"[{guideline.disease} - {guideline.category}] {guideline.rule}"
    return Document(
        page_content=content,
        metadata={
            "doc_type": "lifestyle_guideline",
            "guideline_id": guideline.id,
            "disease": guideline.disease,
            "disease_code": guideline.disease_code,
            "category": guideline.category,
            "source": guideline.source,
        },
    )


def lifestyle_guidelines_to_documents(guidelines: list[LifestyleGuideline]) -> list[Document]:
    return [lifestyle_guideline_to_document(guideline) for guideline in guidelines]
