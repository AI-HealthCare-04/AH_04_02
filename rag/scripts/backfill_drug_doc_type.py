"""기존에 인제스트된 의약품 문서에 doc_type="drug" 메타데이터를 백필한다.

[2026-07-20, REQ-037 관련 이슈3] chunking.py의 drug_to_documents()가 이제 doc_type="drug"를
새로 태깅하지만, 이미 인제스트된 기존 문서(doc_type 필드 자체가 없어 None으로 조회됨)는
그대로 남아있다. rag_chain.py의 _build_context()가 컨텍스트를 못 찾을 때 마지막 폴백으로
쓰는 similarity_search(filter={"doc_type": "drug"})가 이 기존 문서들을 걸러내지 못하면
(사실상 안 걸린다는 뜻) 폴백 자체가 무력화되므로, 팀 각자 환경에서 1회 실행이 필요하다.

item_name이 있는 문서(=드러그 문서)만 골라 같은 id(item_seq::field)로 upsert한다 —
kdca_health_info/lifestyle_guideline 문서는 건드리지 않는다(이미 각자 doc_type이 있음).

사용법:
    cd rag && uv run python scripts/backfill_drug_doc_type.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.documents import Document  # noqa: E402
from rag.vectorstore import get_vectorstore  # noqa: E402


def main() -> None:
    store = get_vectorstore()
    all_data = store.get()

    to_update: list[Document] = []
    ids: list[str] = []
    for doc_id, content, metadata in zip(
        all_data["ids"], all_data["documents"], all_data["metadatas"], strict=True
    ):
        if metadata.get("doc_type") is not None:
            continue
        if not metadata.get("item_name") or not metadata.get("item_seq"):
            continue
        updated_metadata = {**metadata, "doc_type": "drug"}
        to_update.append(Document(page_content=content, metadata=updated_metadata))
        ids.append(doc_id)

    if not to_update:
        print("백필 대상 없음 — 이미 전부 doc_type이 있거나 컬렉션이 비어있습니다.")
        return

    print(f"{len(to_update)}건에 doc_type=\"drug\" 백필 중...")
    store.add_documents(to_update, ids=ids)
    print("완료.")


if __name__ == "__main__":
    main()
