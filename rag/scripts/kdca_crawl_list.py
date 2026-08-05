"""질병관리청 국가건강정보포털 Open API 신청내역(83페이지)을 순회해서 cntntsSn
목록을 수집한다. 사용법은 rag/README.md의 "질병관리청 건강정보 수집" 절 참고.

이 목록 페이지는 로그인 세션이 있어야만 접근되므로, 브라우저에서 로그인한 뒤
DevTools Console에 `document.cookie`를 입력해 얻은 값을 KDCA_COOKIE 환경변수로
전달한다(코드에 하드코딩하지 않음).
"""
import csv
import os
import re
import sys
import time

import requests

BASE_URL = "https://health.kdca.go.kr/healthinfo/biz/health/portalUseGuidance/openApiReqst/openApiReqstMain.do"
TOTAL_PAGES = 83
OUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "kdca_healthinfo_cntntsSn.csv")

ROW_RE = re.compile(
    r'<tr>\s*<td class="txtC">(\d+)</td>\s*<td>(.*?)</td>\s*<td>.*?</td>\s*'
    r'<td class="txtC">([\d-]+)</td>\s*<td class="txtC">([^<]*)</td>',
    re.S,
)


def extract_rows(html: str, page_index: int, results: dict) -> int:
    added = 0
    for row_id, title, applied_date, status in ROW_RE.findall(html):
        if row_id in results:
            continue
        results[row_id] = {
            "cntntsSn": row_id,
            "pageIndex": page_index,
            "title": re.sub(r"<[^>]+>", "", title).strip(),
            "appliedDate": applied_date,
            "status": status,
        }
        added += 1
    return added


def main():
    cookie = os.environ.get("KDCA_COOKIE")
    if not cookie:
        print("KDCA_COOKIE 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    session = requests.Session()
    session.headers.update(
        {"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie, "User-Agent": "Mozilla/5.0"}
    )

    results: dict[str, dict] = {}
    for page_index in range(1, TOTAL_PAGES + 1):
        resp = session.post(
            BASE_URL, data={"pageIndex": str(page_index), "searchTy": "", "searchWrd": ""}, timeout=15
        )
        if resp.status_code != 200:
            print(f"[경고] page {page_index}: HTTP {resp.status_code}", file=sys.stderr)
            time.sleep(1)
            continue

        added = extract_rows(resp.text, page_index, results)
        print(f"{page_index}/{TOTAL_PAGES} 완료, 이번 페이지 {added}건, 누적 {len(results)}건")
        time.sleep(0.3)

    rows = list(results.values())
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["cntntsSn", "pageIndex", "title", "appliedDate", "status"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n완료: 총 {len(rows)}건 → {OUT_CSV}")


if __name__ == "__main__":
    main()
