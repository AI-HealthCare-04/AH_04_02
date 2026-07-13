from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from rag.config import settings


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


def similarity_search(query: str, k: int | None = None) -> list[Document]:
    store = get_vectorstore()
    return store.similarity_search(query, k=k or settings.TOP_K)
