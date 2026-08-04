"""Compact, versioned master data for public drug APIs.

The application reads this JSONL before making a network request. Each line
stores one query/result pair, so only medicines supported by this service are
kept instead of copying very large upstream datasets. The same records can be
embedded in Chroma for RAG retrieval.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from rag.config import settings

MASTER_VERSION = 1
_NORMALIZE_RE = re.compile(r"[^0-9a-zA-Z가-힣]")


def normalize_lookup_name(value: str) -> str:
    return _NORMALIZE_RE.sub("", (value or "").casefold())


def _master_path(path: str | Path | None = None) -> Path:
    return Path(path or settings.PUBLIC_API_MASTER_PATH)


@lru_cache(maxsize=4)
def _load_index(path_text: str, modified_ns: int) -> dict[tuple[str, str], list[dict[str, Any]]]:
    del modified_ns
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    path = Path(path_text)
    if not path.exists():
        return dict(index)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            key = (record["record_type"], normalize_lookup_name(record["lookup_name"]))
            index[key].extend(record.get("items") or [])
    return dict(index)


def lookup(record_type: str, lookup_name: str, path: str | Path | None = None) -> list[dict[str, Any]] | None:
    master_path = _master_path(path)
    if not master_path.exists():
        return None
    index = _load_index(str(master_path.resolve()), master_path.stat().st_mtime_ns)
    key = (record_type, normalize_lookup_name(lookup_name))
    if key not in index:
        return None
    return list(index[key])


def write_records(records: Iterable[dict[str, Any]], path: str | Path | None = None) -> int:
    """Merge records by type/name and atomically rewrite the compact JSONL."""
    master_path = _master_path(path)
    master_path.parent.mkdir(parents=True, exist_ok=True)
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    if master_path.exists():
        with master_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    old = json.loads(line)
                    merged[(old["record_type"], normalize_lookup_name(old["lookup_name"]))] = old
    now = datetime.now(UTC).isoformat()
    for raw in records:
        record = {
            "version": MASTER_VERSION,
            "record_type": raw["record_type"],
            "lookup_name": raw["lookup_name"],
            "fetched_at": raw.get("fetched_at") or now,
            "status": raw.get("status") or ("ok" if raw.get("items") else "empty"),
            "items": raw.get("items") or [],
        }
        merged[(record["record_type"], normalize_lookup_name(record["lookup_name"]))] = record
    temporary = master_path.with_suffix(master_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for key in sorted(merged):
            handle.write(json.dumps(merged[key], ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(master_path)
    _load_index.cache_clear()
    return len(merged)


def prune_unverified_empty_records(path: str | Path | None = None) -> int:
    """Remove legacy empty rows whose API-success state was not recorded.

    Older builders represented both an API error and a confirmed empty result
    as ``items=[]``. Keeping those rows would suppress the safe live fallback.
    """
    master_path = _master_path(path)
    if not master_path.exists():
        return 0
    kept = []
    with master_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if not record.get("items"):
                continue
            record["status"] = "ok"
            kept.append(record)
    temporary = master_path.with_suffix(master_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in kept:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(master_path)
    _load_index.cache_clear()
    return len(kept)


def records_to_documents(path: str | Path | None = None) -> list[Document]:
    """Convert master records into compact Chroma documents for RAG."""
    master_path = _master_path(path)
    if not master_path.exists():
        return []
    documents: list[Document] = []
    with master_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            name = record["lookup_name"]
            record_type = record["record_type"]
            for index, item in enumerate(record.get("items") or []):
                # Permit detail fields can contain very large XML documents.
                # Keep the complete value in JSONL but cap the embedded text.
                text_fields = [str(value).strip() for value in item.values() if value]
                searchable_text = " | ".join(text_fields)[:6000]
                documents.append(
                    Document(
                        page_content=f"[{name}] {record_type}: {searchable_text}",
                        metadata={
                            "doc_type": "public_api_master",
                            "record_type": record_type,
                            "item_name": name,
                            "lookup_name_normalized": normalize_lookup_name(name),
                            "fetched_at": record.get("fetched_at", ""),
                            "master_line": line_number,
                            "master_item_index": index,
                            "source": "공공데이터포털 마스터",
                        },
                    )
                )
    return documents
