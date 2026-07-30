"""건강보험심사평가원 DUR(의약품안전사용서비스) 조회 — 식약처 Open API 연동.

[2026-07-10] DUR API(getUsjntTabooInfoList03)를 처음 시도했을 때는 활용신청 승인 대기
상태라 403 Forbidden이 나서, 공공데이터포털에서 받은 CSV로 임시 대체했었다(git 이력 참고).
[2026-07-14] 활용신청이 승인되어(개발계정, 자동승인) 다시 API 연동으로 전환한다 — CSV
파일(backend/data/dur_*.csv)은 더 이상 쓰지 않는다.

승인된 API 4개와 카테고리 대응:

| 카테고리 | 엔드포인트 | 관계 종류 |
|---|---|---|
| 병용금기 | getUsjntTabooInfoList03 | **약 두 개 사이의 관계** — 처방전에 상대 약이 실제로 있어야 경고 (search_usjnt_taboo) |
| 노인주의 | getOdsnAtentInfoList03 | 약 하나의 속성 (search_elderly_caution) |
| 연령금기 | getSpcifyAgrdeTabooInfoList03 | 약 하나의 속성 (search_age_taboo) |
| 임부금기 | getPwnmTabooInfoList03 | 약 하나의 속성 (search_pregnancy_taboo) |

[주의] CSV 시절엔 "노인주의(해열진통소염제)"가 별도 파일로 분리돼 있었으나, 승인된 API
목록에는 그 세부 카테고리에 대응하는 별도 엔드포인트가 없다 — getOdsnAtentInfoList03
하나가 전체 노인주의 항목을 돌려주므로, 이번 전환부터는 전부 "노인주의" 하나로 통합해
분류한다(NSAID 하위분류 정보 손실, README_rag.md에 기록).

[주의] CSV의 "연령금기" extra(특정연령/특정연령단위/연령처리조건)와 "임부금기" extra
(금기등급)에 대응하는 별도 필드가 API 응답에는 없다 — 해당 조건은 PROHBT_CONTENT(상세
설명) 텍스트 안에 자연어로 포함돼 있다. 이번 전환부터 두 카테고리의 extra는 항상 None이다.

노인주의/연령금기/임부금기는 "이 환자에게 실제로 해당하는지"(나이·임신 여부)를 이 시스템이
모르므로 조건 판단 없이 정보성으로만 노출한다 (schemas.DurCaution 참고).
"""

from rag.config import settings
from rag.mfds_client import _disk_cache, _request
from rag.schemas import DurCaution, DurTabooInfo


def _dedupe_cautions(cautions: list[DurCaution]) -> list[DurCaution]:
    """부분일치 조회 시 같은 성분의 제조사별 제품이 각각 행으로 등재돼 있어,
    (카테고리, 사유, 부가정보)가 완전히 같은 경고가 수십 건씩 중복될 수 있다
    (_check_dur_taboo의 브랜드 중복 제거와 같은 문제). item_name은 어차피 검색어로
    고정돼 있으므로 (category, detail, extra) 조합 기준으로 한 번만 남긴다.
    """
    seen: set[tuple[str, str | None, str | None]] = set()
    deduped: list[DurCaution] = []
    for c in cautions:
        key = (c.category, c.detail, c.extra)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _dedupe_taboo(taboos: list[DurTabooInfo]) -> list[DurTabooInfo]:
    """병용금기도 제조사별 제품이 각각 행으로 등재돼 브랜드 중복이 생긴다 —
    (mixture_item_name, prohbt_content) 조합 기준으로 한 번만 남긴다."""
    seen: set[tuple[str, str | None]] = set()
    deduped: list[DurTabooInfo] = []
    for t in taboos:
        key = (t.mixture_item_name, t.prohbt_content)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


# [2026-07-21 추가 → 2026-07-30 디스크 캐시로 전환]
# mfds_client의 lru_cache와 동일한 이유로 diskcache로 전환한다.
# _disk_cache는 mfds_client._disk_cache와 동일한 인스턴스를 공유해 캐시 디렉토리를 통일한다.
def search_usjnt_taboo(item_name: str, num_of_rows: int = 100, page_no: int = 1) -> list[DurTabooInfo]:
    """품목명(부분일치)으로 병용금기 상대 목록을 조회합니다.

    못 찾으면 빈 리스트 — "이 약은 병용금기가 없다"는 의미가 아니라 "DUR 데이터에 해당
    품목명이 등재돼 있지 않다"는 뜻이므로 호출부에서 그렇게 해석하지 않도록 주의할 것.
    """
    key = f"dur.search_usjnt_taboo|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DurTabooInfo.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request(
        {"itemName": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.DUR_USJNT_TABOO_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    taboos = [
        DurTabooInfo(
            item_name=item.get("ITEM_NAME") or item_name,
            mixture_item_name=item["MIXTURE_ITEM_NAME"],
            prohbt_content=(item.get("PROHBT_CONTENT") or "").strip() or None,
        )
        for item in items
        if item.get("MIXTURE_ITEM_NAME")
    ]
    result = _dedupe_taboo(taboos)
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result


def search_elderly_caution(item_name: str, num_of_rows: int = 100, page_no: int = 1) -> list[DurCaution]:
    """품목명(부분일치)으로 노인주의 정보를 조회합니다.

    [2026-07-14] API 전환 이후 "노인주의(해열진통소염제)" 세부 분류는 더 이상 구분하지
    않는다 — 승인된 API(getOdsnAtentInfoList03)가 전체 노인주의 항목을 하나로 반환한다.
    """
    key = f"dur.search_elderly_caution|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DurCaution.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request(
        {"itemName": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.DUR_ODSN_ATENT_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    cautions = [
        DurCaution(
            item_name=item.get("ITEM_NAME") or item_name,
            category="노인주의",
            detail=(item.get("PROHBT_CONTENT") or "").strip() or None,
        )
        for item in items
    ]
    result = _dedupe_cautions(cautions)
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result


def search_age_taboo(item_name: str, num_of_rows: int = 100, page_no: int = 1) -> list[DurCaution]:
    """품목명(부분일치)으로 연령금기(특정 연령대 사용 금지) 정보를 조회합니다."""
    key = f"dur.search_age_taboo|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DurCaution.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request(
        {"itemName": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.DUR_AGE_TABOO_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    cautions = [
        DurCaution(
            item_name=item.get("ITEM_NAME") or item_name,
            category="연령금기",
            detail=(item.get("PROHBT_CONTENT") or "").strip() or None,
        )
        for item in items
    ]
    result = _dedupe_cautions(cautions)
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result


def search_pregnancy_taboo(item_name: str, num_of_rows: int = 100, page_no: int = 1) -> list[DurCaution]:
    """품목명(부분일치)으로 임부금기 정보를 조회합니다."""
    key = f"dur.search_pregnancy_taboo|{item_name}|{num_of_rows}|{page_no}"
    if _disk_cache is not None:
        try:
            cached = _disk_cache.get(key)
            if cached is not None:
                return [DurCaution.model_validate(d) for d in cached]
        except Exception:
            pass
    data = _request(
        {"itemName": item_name, "numOfRows": num_of_rows, "pageNo": page_no},
        base_url=settings.DUR_PREGNANCY_TABOO_BASE_URL,
    )
    items = data.get("body", {}).get("items") or []
    cautions = [
        DurCaution(
            item_name=item.get("ITEM_NAME") or item_name,
            category="임부금기",
            detail=(item.get("PROHBT_CONTENT") or "").strip() or None,
        )
        for item in items
    ]
    result = _dedupe_cautions(cautions)
    if _disk_cache is not None:
        try:
            _disk_cache.set(key, [r.model_dump() for r in result], expire=settings.MFDS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return result
