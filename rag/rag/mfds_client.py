import logging
import re
import time
import xml.etree.ElementTree as ET

import diskcache
import requests
from rag.config import settings
from rag.schemas import DrugInfo, DrugPermitDetail, DrugPermitInfo

_logger = logging.getLogger(__name__)

# 식약처 API 응답 디스크 캐시 — lru_cache(메모리 전용, 재시작 시 초기화)를 대체한다.
# diskcache.Cache는 내부적으로 SQLite를 사용하며 멀티프로세스(--workers 2)에서도 안전하다.
# timeout=1: 락 획득 대기 시간(초). 기본값 0.010은 멀티프로세스 환경에서 Timeout이 날 수
# 있어 1초로 늘린다. 초기화 실패(경로 접근 불가 등)가 있어도 API 호출 자체는 계속 작동한다.
# size_limit=100MB: 약물 데이터 건당 수 KB 수준이므로 실용적으로 넉넉하되 상한을 명시한다.
#
# 캐시 키 네임스페이스 규칙: "모듈접두사.함수명|인자1|인자2|..."
#   mfds.*  — mfds_client.py (e약은요, 허가정보 목록, 허가정보 상세)
#   dur.*   — dur_master.py  (병용금기, 노인주의, 연령금기, 임부금기)
# dur_master.py는 _disk_cache를 이 모듈에서 import해 같은 SQLite 파일을 공유한다.
# 새 함수를 추가할 때는 위 접두사 규칙에 따라 키 충돌을 방지할 것.
try:
    _disk_cache: diskcache.Cache | None = diskcache.Cache(
        settings.MFDS_CACHE_DIR,
        timeout=1,
        size_limit=100 * 1024 * 1024,  # 100 MB
    )
except Exception as _e:
    _logger.warning("diskcache 초기화 실패 — 캐시 없이 동작합니다: %s", _e)
    _disk_cache = None

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


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


# [2026-07-21 추가 → 2026-07-30 디스크 캐시로 전환]
# 식약처 데이터는 정부가 보통 하루~한 달 단위로 갱신하는 정적에 가까운 데이터다. 기존
# lru_cache는 프로세스 메모리에만 유지돼 서버 재시작 시 초기화됐다 — diskcache로 전환해서
# 한 번 조회된 결과를 서버 재시작 후에도 재사용한다(TTL=48시간, settings.MFDS_CACHE_TTL_SECONDS).
# Pydantic 모델은 model_dump()/model_validate()로 명시적 JSON 직렬화해서 pickle 의존 없이
# Pydantic 버전 변경에도 안전하게 처리한다. 캐시 장애 시에도 API 직접 호출로 폴백된다.
def search_by_name(
    item_name: str, num_of_rows: int = 10, page_no: int = 1, *, use_master: bool = True
) -> list[DrugInfo]:
    """품목명(부분 일치)으로 의약품 정보를 검색합니다."""
    if use_master and settings.PUBLIC_API_MASTER_ENABLED:
        from rag.public_api_master import lookup

        mastered = lookup("drug_info", item_name)
        if mastered is not None:
            return [DrugInfo.model_validate(item) for item in mastered][:num_of_rows]
        if not settings.PUBLIC_API_LIVE_FALLBACK:
            return []
    key = f"mfds.search_by_name|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DrugInfo.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request({"itemName": item_name, "numOfRows": num_of_rows, "pageNo": page_no})
    items = data.get("body", {}).get("items") or []
    result = [DrugInfo.model_validate(item) for item in items]
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result


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
def search_permit_info(
    item_name: str, num_of_rows: int = 10, page_no: int = 1, *, use_master: bool = True
) -> list[DrugPermitInfo]:
    """식약처_의약품제품허가정보(DrugPrdtPrmsnInfoService07)로 품목명(부분 일치) 허가 상태를 조회합니다.

    e약은요(search_by_name)와 별개 API — 효능효과 등 설명문은 없고, 허가번호·허가일자·
    허가/신고 구분·취소여부(정상 허가 의약품인지) 같은 규제 메타데이터만 돌려준다.
    """
    if use_master and settings.PUBLIC_API_MASTER_ENABLED:
        from rag.public_api_master import lookup

        mastered = lookup("permit_info", item_name)
        if mastered is not None:
            return [DrugPermitInfo.model_validate(item) for item in mastered][:num_of_rows]
        if not settings.PUBLIC_API_LIVE_FALLBACK:
            return []
    key = f"mfds.search_permit_info|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DrugPermitInfo.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request(
        {"item_name": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.PERMIT_INFO_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    result = [DrugPermitInfo.model_validate(item) for item in items]
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result


def is_officially_approved(item_name: str) -> bool | None:
    """품목명으로 허가정보를 조회해 정상 허가 상태(취소·취하 아님)인 품목이 하나라도 있으면 True.

    조회 결과가 아예 없으면(등록되지 않은 품목명 등) 판단 불가로 None을 반환한다.
    """
    results = search_permit_info(item_name)
    if not results:
        return None
    return any(item.is_active for item in results)


# [2026-07-14 추가] 사용자가 "제품허가정보로 사용상의 주의사항 조회 가능한지" 확인 요청 —
# 목록 조회(getDrugPrdtPrmsnInq07)에는 없고, 상세정보(getDrugPrdtPrmsnDtlInq06)에만 있다.
def search_permit_detail(
    item_name: str, num_of_rows: int = 10, page_no: int = 1, *, use_master: bool = True
) -> list[DrugPermitDetail]:
    """식약처_의약품제품허가정보 상세정보(getDrugPrdtPrmsnDtlInq06)를 품목명(부분 일치)으로 조회합니다.

    효능효과/용법용량/사용상의주의사항/임부수유부주의사항 원문(XX_DOC_DATA, 구조화 XML)을
    담고 있다 — parse_doc_sections()로 사람이 읽을 텍스트로 변환해야 한다.
    """
    if use_master and settings.PUBLIC_API_MASTER_ENABLED:
        from rag.public_api_master import lookup

        mastered = lookup("permit_detail", item_name)
        if mastered is not None:
            return [DrugPermitDetail.model_validate(item) for item in mastered][:num_of_rows]
        if not settings.PUBLIC_API_LIVE_FALLBACK:
            return []
    key = f"mfds.search_permit_detail|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DrugPermitDetail.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request(
        {"item_name": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.PERMIT_DETAIL_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    result = [DrugPermitDetail.model_validate(item) for item in items]
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result


def parse_doc_sections(doc_xml: str | None) -> list[tuple[str, str]]:
    """`<DOC><SECTION><ARTICLE title="...">문단들</ARTICLE></SECTION></DOC>` 구조의
    XX_DOC_DATA 문자열을 (섹션 제목, 본문 텍스트) 리스트로 변환합니다.

    문단(PARAGRAPH) 안에 표 등 HTML 마크업이 CDATA로 섞여 있을 수 있어 태그를 제거한다.
    파싱 실패(빈 값·잘못된 XML)는 예외를 던지지 않고 빈 리스트로 처리한다 — 이 텍스트가
    없어도 나머지 인용(e약은요/HIRA/DUR)은 그대로 유효해야 하기 때문이다.
    """
    if not doc_xml or not doc_xml.strip():
        return []
    try:
        root = ET.fromstring(doc_xml)
    except ET.ParseError:
        return []

    sections = []
    for article in root.iter("ARTICLE"):
        title = (article.get("title") or "").strip()
        paragraphs = []
        for p in article.iter("PARAGRAPH"):
            if not p.text:
                continue
            cleaned = _WHITESPACE_RE.sub(" ", _TAG_RE.sub(" ", p.text)).strip()
            if cleaned:
                paragraphs.append(cleaned)
        text = " ".join(paragraphs)
        if title and text:
            sections.append((title, text))
    return sections
