#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
생약 약재정보 전체 수집 → herb_reference.csv 생성

HerbMdntfService API (공공데이터포털 IROS_335)
실행: python scripts/build_herb_reference.py  (backend/ 에서 실행)
출력: backend/herb_reference.csv
"""
import csv
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).parent.parent
load_dotenv(_BACKEND_DIR / ".env")

API_URL = "http://apis.data.go.kr/1471057/HerbMdntfService/getMdntf"
NUM_OF_ROWS = 100
DELAY = 0.2
OUTPUT = _BACKEND_DIR / "herb_reference.csv"

# 한자가 포함된 괄호 전체 제거: (當歸), (葛根), (野菊花) 등
_HANJA_PAREN_RE = re.compile(r"\([^\)]*[一-鿿][^\)]*\)")


def clean_name(raw: str) -> str:
    return _HANJA_PAREN_RE.sub("", raw).strip()


def fetch_page(service_key: str, page_no: int) -> dict:
    resp = requests.get(
        API_URL,
        params={
            "serviceKey": service_key,
            "numOfRows": NUM_OF_ROWS,
            "pageNo": page_no,
            "type": "json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def extract_rows(body: dict) -> list[dict]:
    items = body.get("items") or []
    if isinstance(items, dict):
        items = [items]

    result = []
    for item in items:
        mdntf_no = item.get("MDNTF_NO", "")
        drgnm_no = item.get("DRGNM_NO", "")
        drgnm_raw = (item.get("DRGNM") or "").strip()

        aliases = [clean_name(a) for a in drgnm_raw.split(",")]
        aliases = [a for a in aliases if a]
        if not aliases:
            continue
        representative = aliases[0]

        for alias in aliases:
            result.append({
                "mdntf_no": mdntf_no,
                "drgnm_no": drgnm_no,
                "herb_name": alias,
                "representative_name": representative,
                "drgnm_raw": drgnm_raw,
            })
    return result


def main():
    service_key = os.environ.get("HERB_API_KEY", "")
    if not service_key:
        raise EnvironmentError("HERB_API_KEY가 .env에 없습니다.")

    print("1페이지 요청 중...")
    data = fetch_page(service_key, 1)

    header = data.get("header", {})
    if header.get("resultCode") != "00":
        raise RuntimeError(f"API 오류: {header.get('resultMsg')}")

    body = data["body"]
    total_count = body["totalCount"]
    total_pages = (total_count + NUM_OF_ROWS - 1) // NUM_OF_ROWS
    print(f"전체 {total_count}건 / {total_pages}페이지 예상")

    all_rows: list[dict] = []
    all_rows.extend(extract_rows(body))
    print(f"  page  1/{total_pages}  누적 이명 {len(all_rows)}개")

    for page_no in range(2, total_pages + 1):
        time.sleep(DELAY)
        data = fetch_page(service_key, page_no)
        all_rows.extend(extract_rows(data["body"]))
        print(f"  page {page_no:2d}/{total_pages}  누적 이명 {len(all_rows)}개")

    fieldnames = ["mdntf_no", "drgnm_no", "herb_name", "representative_name", "drgnm_raw"]
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n완료: 이명 {len(all_rows)}개 → {OUTPUT}")


if __name__ == "__main__":
    main()
