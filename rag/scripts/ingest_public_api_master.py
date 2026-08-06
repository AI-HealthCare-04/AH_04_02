"""Embed the compact public API master into the existing Chroma collection."""

from rag.public_api_master import records_to_documents
from rag.vectorstore import add_public_api_master_documents


def main() -> None:
    documents = records_to_documents()
    count = add_public_api_master_documents(documents)
    print(f"public API master embedded: {count} documents")


if __name__ == "__main__":
    main()
