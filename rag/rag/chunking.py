import html
import re

from langchain_core.documents import Document
from rag.schemas import DRUG_FIELD_LABELS, DrugInfo, KdcaHealthInfoSection, LifestyleGuideline

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_MIN_KDCA_SECTION_TEXT_LEN = 10  # 순수 이미지 태그 등 검색에 의미 없는 섹션 제외 기준


def _strip_html(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html)
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


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


def kdca_health_info_section_to_document(section: KdcaHealthInfoSection) -> Document | None:
    """질병관리청 건강정보 섹션 1건을 Document로 변환합니다. 텍스트가 거의 없는 순수
    이미지 섹션은 검색에 의미가 없어 None을 반환합니다(호출부에서 건너뜀)."""
    text = _strip_html(section.html)
    if len(text) < _MIN_KDCA_SECTION_TEXT_LEN:
        return None
    content = f"[{section.title} - {section.section_name}] {text}"
    return Document(
        page_content=content,
        metadata={
            "doc_type": "kdca_health_info",
            "cntnts_sn": section.cntnts_sn,
            "title": section.title,
            "section_name": section.section_name,
            "section_sn": section.section_sn,
            "index": section.index,
            "source": section.source,
            "source_url": section.source_url,
            "updated_at": section.updated_at,
        },
    )


def kdca_health_info_sections_to_documents(sections: list[KdcaHealthInfoSection]) -> list[Document]:
    documents = []
    for section in sections:
        doc = kdca_health_info_section_to_document(section)
        if doc is not None:
            documents.append(doc)
    return documents
