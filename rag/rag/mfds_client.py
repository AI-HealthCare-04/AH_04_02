import time

import requests

from rag.config import settings
from rag.schemas import DrugInfo, DrugPermitInfo


class MfdsApiError(RuntimeError):
    pass


def _request(params: dict, base_url: str | None = None, retries: int = 2, timeout: float = 10.0) -> dict:
    query = {"serviceKey": settings.DATA_GO_KR_SERVICE_KEY, "type": "json", **params}
    url = base_url or settings.MFDS_BASE_URL

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=query, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
            continue

        result_code = data.get("header", {}).get("resultCode")
        if result_code != "00":
            raise MfdsApiError(f"MFDS API error {result_code}: {data.get('header', {}).get('resultMsg')}")
        return data

    raise MfdsApiError(f"MFDS API request failed after {retries + 1} attempts: {last_error}")


def search_by_name(item_name: str, num_of_rows: int = 10, page_no: int = 1) -> list[DrugInfo]:
    """품목명(부분 일치)으로 의약품 정보를 검색합니다."""
    data = _request({"itemName": item_name, "numOfRows": num_of_rows, "pageNo": page_no})
    items = data.get("body", {}).get("items") or []
    return [DrugInfo.model_validate(item) for item in items]


def fetch_page(num_of_rows: int = 100, page_no: int = 1) -> tuple[list[DrugInfo], int]:
    """전체 의약품 목록을 페이지 단위로 가져옵니다. (total_count, items) 반환."""
    data = _request({"numOfRows": num_of_rows, "pageNo": page_no})
    body = data.get("body", {})
    items = body.get("items") or []
    total_count = body.get("totalCount", 0)
    return [DrugInfo.model_validate(item) for item in items], total_count


def fetch_first_match(item_name: str) -> DrugInfo | None:
    results = search_by_name(item_name, num_of_rows=1)
    return results[0] if results else None



# [2026-07-10 → 7/13] DUR 병용금기는 API(getUsjntTabooInfoList03)로 시도했으나 활용신청
# 승인 대기(403 Forbidden)라 로컬 CSV 조회로 대체했다 — rag/dur_master.py의
# search_usjnt_taboo() 참고. 이 API가 나중에 승인되면 그때 다시 여기에 추가할 수 있다.


# [2026-07-14] 활용신청 승인되어 재활성화. item_name 쿼리 파라미터, 응답 필드 전부
# 실제 API 호출로 재확인 완료(schemas.DrugPermitInfo 참고).
def search_permit_info(item_name: str, num_of_rows: int = 10, page_no: int = 1) -> list[DrugPermitInfo]:
    """식약처_의약품제품허가정보(DrugPrdtPrmsnInfoService07)로 품목명(부분 일치) 허가 상태를 조회합니다.

    e약은요(search_by_name)와 별개 API — 효능효과 등 설명문은 없고, 허가번호·허가일자·
    허가/신고 구분·취소여부(정상 허가 의약품인지) 같은 규제 메타데이터만 돌려준다.
    """
    data = _request(
        {"item_name": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.PERMIT_INFO_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    return [DrugPermitInfo.model_validate(item) for item in items]


def is_officially_approved(item_name: str) -> bool | None:
    """품목명으로 허가정보를 조회해 정상 허가 상태(취소·취하 아님)인 품목이 하나라도 있으면 True.

    조회 결과가 아예 없으면(등록되지 않은 품목명 등) 판단 불가로 None을 반환한다.
    """
    results = search_permit_info(item_name)
    if not results:
        return None
    return any(item.is_active for item in results)
