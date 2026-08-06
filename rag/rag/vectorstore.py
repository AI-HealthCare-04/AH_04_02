from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from rag.config import settings

try:
    from services.langfuse_tracing import (
        flush_langfuse,
        optional_observation,
        update_observation,
    )
except Exception:  # noqa: BLE001 — rag 단독 실행 시 backend/services가 없어도 RAG는 동작해야 함
    def optional_observation(**_kwargs):
        from contextlib import nullcontext

        return nullcontext(None)

    def update_observation(_observation, **_kwargs) -> None:
        return None

    def flush_langfuse() -> None:
        return None


@lru_cache(maxsize=1)
def get_embedding_function() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)


def get_vectorstore() -> Chroma:
    return Chroma(
        collection_name=settings.CHROMA_COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        persist_directory=settings.CHROMA_PERSIST_DIR,
    )


def add_documents(documents: list[Document]) -> int:
    if not documents:
        return 0
    store = get_vectorstore()
    ids = [f"{doc.metadata['item_seq']}::{doc.metadata['field']}" for doc in documents]
    store.add_documents(documents, ids=ids)
    return len(documents)


def add_lifestyle_documents(documents: list[Document]) -> int:
    if not documents:
        return 0
    store = get_vectorstore()
    ids = [doc.metadata["guideline_id"] for doc in documents]
    store.add_documents(documents, ids=ids)
    return len(documents)


_CHROMA_MAX_BATCH_SIZE = 5000  # Chroma의 실제 한도(약 5461)보다 여유를 둔 배치 크기


def add_kdca_health_info_documents(documents: list[Document]) -> int:
    """663건 전체를 섹션 단위로 펼치면 한 번에 넣기엔 너무 많아(8000건 이상) Chroma의
    단일 upsert 배치 한도를 넘는다 — 배치로 나눠 넣는다."""
    if not documents:
        return 0
    store = get_vectorstore()
    ids = [f"kdca::{doc.metadata['cntnts_sn']}::{doc.metadata['section_sn']}::{doc.metadata['index']}" for doc in documents]
    for start in range(0, len(documents), _CHROMA_MAX_BATCH_SIZE):
        batch_docs = documents[start : start + _CHROMA_MAX_BATCH_SIZE]
        batch_ids = ids[start : start + _CHROMA_MAX_BATCH_SIZE]
        store.add_documents(batch_docs, ids=batch_ids)
    return len(documents)


def add_public_api_master_documents(documents: list[Document]) -> int:
    if not documents:
        return 0
    store = get_vectorstore()
    ids = [
        f"public-api::{doc.metadata['record_type']}::{doc.metadata['lookup_name_normalized']}::{doc.metadata['master_item_index']}"
        for doc in documents
    ]
    for start in range(0, len(documents), _CHROMA_MAX_BATCH_SIZE):
        store.add_documents(
            documents[start : start + _CHROMA_MAX_BATCH_SIZE],
            ids=ids[start : start + _CHROMA_MAX_BATCH_SIZE],
        )
    return len(documents)


def search_public_api_master(query: str, k: int | None = None) -> list[Document]:
    return similarity_search(query, k=k, filter={"doc_type": "public_api_master"})


def search_kdca_health_info_by_title(title: str) -> list[Document]:
    """제목(질환/주제명)이 정확히 일치하는 건강정보 섹션을 전부 가져옵니다."""
    store = get_vectorstore()
    result = store.get(where={"title": title})
    docs = []
    for content, metadata in zip(result.get("documents", []), result.get("metadatas", []), strict=True):
        docs.append(Document(page_content=content, metadata=metadata))
    return docs


def search_by_disease(disease_code: str) -> list[Document]:
    """특정 만성질환(disease_code)에 해당하는 생활지침 청크를 모두 가져옵니다."""
    store = get_vectorstore()
    result = store.get(where={"disease_code": disease_code})
    docs = []
    for content, metadata in zip(result.get("documents", []), result.get("metadatas", []), strict=True):
        docs.append(Document(page_content=content, metadata=metadata))
    return docs


def search_by_item_name(item_name: str) -> list[Document]:
    """특정 약품명과 정확히 일치하는 메타데이터로 모든 청크를 가져옵니다."""
    store = get_vectorstore()
    result = store.get(where={"item_name": item_name})
    docs = []
    for content, metadata in zip(result.get("documents", []), result.get("metadatas", []), strict=True):
        docs.append(Document(page_content=content, metadata=metadata))
    return docs


def similarity_search(query: str, k: int | None = None, filter: dict | None = None) -> list[Document]:
    store = get_vectorstore()
    top_k = k or settings.TOP_K
    with optional_observation(
        as_type="retriever",
        name="retrieve-from-chromadb",
        input={
            "query_omitted": True,
            "query_length": len(query or ""),
            "top_k": top_k,
            "filter": filter,
            "collection": settings.CHROMA_COLLECTION_NAME,
        },
    ) as observation:
        docs = store.similarity_search(query, k=top_k, filter=filter)
        update_observation(
            observation,
            output={
                "retrieved_count": len(docs),
                "top_k": top_k,
                "documents": [
                    {
                        "doc_type": doc.metadata.get("doc_type"),
                        "title": doc.metadata.get("title"),
                        "source": doc.metadata.get("source"),
                        "item_name": doc.metadata.get("item_name"),
                        "field": doc.metadata.get("field") or doc.metadata.get("field_label"),
                        "disease": doc.metadata.get("disease") or doc.metadata.get("disease_code"),
                        "category": doc.metadata.get("category"),
                    }
                    for doc in docs[:top_k]
                ],
            },
        )
        flush_langfuse()
        return docs


def search_kdca_health_info(query: str, k: int | None = None) -> list[Document]:
    """진단명 등 자유 텍스트로 건강정보 섹션을 의미 기반 검색합니다(doc_type으로 다른
    문서 종류와 섞이지 않게 필터링). 663건 전체를 사람이 하나하나 별칭 등록할 수 없어
    (data/lifestyle_guidelines.json의 4개 질환처럼) 임베딩 유사도 검색으로 대체한다."""
    return similarity_search(query, k=k, filter={"doc_type": "kdca_health_info"})
