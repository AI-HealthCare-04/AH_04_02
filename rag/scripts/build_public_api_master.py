"""Build the compact public API master once, outside request handling.

Examples:
  python rag/scripts/build_public_api_master.py --from-cache
  python rag/scripts/build_public_api_master.py --item-names "노바스크정5밀리그람,타이레놀8시간이알서방정"
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from rag.public_api_master import (
    normalize_lookup_name,
    prune_unverified_empty_records,
    write_records,
)

from rag import dur_master, mfds_client


def _record(record_type: str, name: str, items: list) -> dict:
    return {
        "record_type": record_type,
        "lookup_name": name,
        "items": [item.model_dump(by_alias=True) for item in items],
    }


def fetch_name(name: str, include_drug_info: bool = True) -> list[dict]:
    jobs = {
        "drug_info": lambda: mfds_client.search_by_name(name, num_of_rows=10, use_master=False),
        "permit_info": lambda: mfds_client.search_permit_info(name, num_of_rows=10, use_master=False),
        "permit_detail": lambda: mfds_client.search_permit_detail(name, num_of_rows=10, use_master=False),
        "dur_taboo": lambda: dur_master.search_usjnt_taboo(name, use_master=False),
        "dur_elderly": lambda: dur_master.search_elderly_caution(name, use_master=False),
        "dur_age": lambda: dur_master.search_age_taboo(name, use_master=False),
        "dur_pregnancy": lambda: dur_master.search_pregnancy_taboo(name, use_master=False),
    }
    if not include_drug_info:
        jobs.pop("drug_info")
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {kind: pool.submit(job) for kind, job in jobs.items()}
        results = {}
        for kind, future in futures.items():
            try:
                results[kind] = future.result()
            except Exception as exc:  # one unavailable endpoint must not discard the other sources
                print(f"[{name}] {kind} failed: {exc}")
                # Do not write an empty row for an API failure. Absence from
                # the master deliberately triggers the safe live fallback.
                continue
    return [_record(kind, name, items) for kind, items in results.items()]


def records_from_disk_cache() -> list[dict]:
    cache = mfds_client._disk_cache
    if cache is None:
        return []
    type_map = {
        "mfds.search_by_name": "drug_info",
        "mfds.search_permit_info": "permit_info",
        "mfds.search_permit_detail": "permit_detail",
        "dur.search_usjnt_taboo": "dur_taboo",
        "dur.search_elderly_caution": "dur_elderly",
        "dur.search_age_taboo": "dur_age",
        "dur.search_pregnancy_taboo": "dur_pregnancy",
    }
    records = []
    for key in cache.iterkeys():
        parts = str(key).split("|")
        if len(parts) < 2 or parts[0] not in type_map:
            continue
        cached = cache.get(key)
        if cached is None:  # expired/unreadable cache value is not a confirmed empty result
            continue
        records.append({"record_type": type_map[parts[0]], "lookup_name": parts[1], "items": cached})
    return records


def drug_records_from_emed_xlsx(names: list[str]) -> list[dict]:
    """Use the checked-out e약은요 export when the live HTTP endpoint is slow."""
    candidates = list((Path(__file__).resolve().parents[2] / "backend" / "data").glob("*.xlsx"))
    if not candidates:
        return []
    frame = pd.read_excel(candidates[0]).where(pd.notna, None)
    rows = frame.to_dict("records")
    records = []
    for name in names:
        normalized = normalize_lookup_name(name)
        matches = [
            row
            for row in rows
            if normalized in normalize_lookup_name(str(row.get("itemName") or ""))
            or normalize_lookup_name(str(row.get("itemName") or "")) in normalized
        ][:10]
        if matches:
            records.append({"record_type": "drug_info", "lookup_name": name, "items": matches})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact public API master JSONL")
    parser.add_argument("--item-names", default="", help="comma-separated medicine names to fetch once")
    parser.add_argument("--from-cache", action="store_true", help="seed from the existing persistent API cache")
    parser.add_argument(
        "--from-emed-xlsx",
        action="store_true",
        help="fill e약은요 records from the compact local export instead of its slow HTTP endpoint",
    )
    parser.add_argument("--output", default=None, help="JSONL output path")
    parser.add_argument(
        "--prune-unverified-empty",
        action="store_true",
        help="remove legacy empty rows that may have originated from an API failure",
    )
    args = parser.parse_args()

    if args.prune_unverified_empty:
        print(f"public API master pruned: {prune_unverified_empty_records(args.output)} verified records")
        return

    records = records_from_disk_cache() if args.from_cache else []
    names = [part.strip() for part in args.item_names.split(",") if part.strip()]
    if names:
        with ThreadPoolExecutor(max_workers=min(4, len(names))) as pool:
            for name_records in pool.map(lambda name: fetch_name(name, not args.from_emed_xlsx), names):
                records.extend(name_records)
    if args.from_emed_xlsx:
        records.extend(drug_records_from_emed_xlsx(names))
    if not records:
        parser.error("provide --from-cache and/or --item-names")
    count = write_records(records, args.output)
    print(f"public API master ready: {count} query records")


if __name__ == "__main__":
    main()
