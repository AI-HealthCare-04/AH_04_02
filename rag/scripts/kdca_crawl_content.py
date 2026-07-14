"""data/kdca_healthinfo_cntntsSn.csv(kdca_crawl_list.py로 생성)의 cntntsSn 전체에
대해 healthInfoNew API를 호출해 본문을 수집하고 JSONL로 정규화 저장한다.

토큰은 환경변수 KDCA_TOKEN으로 전달한다(포털 Open API 신청 승인 후 발급되는 값,
코드에 하드코딩하지 않음). 사용법은 rag/README_rag.md의 "질병관리청 건강정보 수집" 절 참고.
"""
import csv
import json
import os
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "..", "data")
IN_CSV = os.path.join(DATA_DIR, "kdca_healthinfo_cntntsSn.csv")
OUT_JSONL = os.path.join(DATA_DIR, "kdca_healthinfo_content.jsonl")
FAILED_LOG = os.path.join(DATA_DIR, "kdca_healthinfo_failed.txt")

API_URL = "https://api.kdca.go.kr/api/provide/healthInfoNew"
SOURCE_NAME = "질병관리청 국가건강정보포털"
SOURCE_URL = "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoMain.do"
DELAY_SEC = 0.25
MAX_RETRIES = 2


class LegacySSLAdapter(HTTPAdapter):
    """api.kdca.go.kr가 legacy renegotiation을 요구하는 구형 SSL 설정이라
    OpenSSL 3.x 기본값(안전하지 않은 재협상 차단)으로는 접속이 거부된다."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def fetch_content(session: requests.Session, token: str, cntnts_sn: str) -> dict | None:
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params={"TOKEN": token, "cntntsSn": cntnts_sn}, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            code = root.findtext("HEAD/CODE", default="")
            if code != "S001":
                message = root.findtext("HEAD/MESSAGE", default="")
                raise ValueError(f"API 오류 code={code} message={message}")

            svc = root.find("svc")
            if svc is None:
                raise ValueError("svc 노드 없음")

            sections = [
                {
                    "name": (cl.findtext("CNTNTS_CL_NM") or "").strip(),
                    "cl_sn": (cl.findtext("CNTNTSCLSN") or "").strip(),
                    "html": (cl.findtext("CNTNTS_CL_CN") or "").strip(),
                }
                for cl in svc.findall("cntntsClList/cntntsCl")
            ]

            return {
                "cntntsSn": cntnts_sn,
                "title": (svc.findtext("CNTNTSSJ") or "").strip(),
                "lclassn": (svc.findtext("LCLASSN") or "").strip(),
                "updated_at": (svc.findtext("SYSUPDTDT") or "").strip(),
                "sections": sections,
                "source": SOURCE_NAME,
                "source_url": SOURCE_URL,
            }
        except Exception as e:  # noqa: BLE001 — 재시도 소진 후에만 실패 처리
            if attempt < MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
                continue
            print(f"[실패] cntntsSn={cntnts_sn}: {e}", file=sys.stderr)
            return None


def main():
    token = os.environ.get("KDCA_TOKEN")
    if not token:
        print("KDCA_TOKEN 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    with open(IN_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    failed = []

    with open(OUT_JSONL, "w", encoding="utf-8") as out_f:
        for i, row in enumerate(rows, start=1):
            cntnts_sn = row["cntntsSn"]
            content = fetch_content(session, token, cntnts_sn)
            if content is None:
                failed.append(cntnts_sn)
            else:
                content["fetched_at"] = datetime.now(timezone.utc).isoformat()
                out_f.write(json.dumps(content, ensure_ascii=False) + "\n")
                out_f.flush()

            if i % 20 == 0 or i == total:
                print(f"{i}/{total} 완료 (실패 {len(failed)}건)")

            time.sleep(DELAY_SEC)

    if failed:
        with open(FAILED_LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(failed))
        print(f"\n실패 {len(failed)}건 → {FAILED_LOG}")

    print(f"완료: {total - len(failed)}/{total}건 → {OUT_JSONL}")


if __name__ == "__main__":
    main()
