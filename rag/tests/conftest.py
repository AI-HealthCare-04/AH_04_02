from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clear_mfds_lru_caches():
    """[2026-07-21 추가] search_by_name/search_permit_info/search_permit_detail/DUR 4종에
    lru_cache를 추가했다(챗봇 DUR 조회 속도 개선) — 캐시가 프로세스 생명주기 동안 유지되면
    같은 item_name을 서로 다른 mock 응답으로 검증하는 테스트끼리 캐시를 공유해 먼저 실행된
    테스트의 결과가 나중 테스트에 새어나간다(실제로 test_search_by_name_raises_on_error_code가
    이렇게 깨졌다). 매 테스트 전후로 캐시를 비워 테스트 간 격리를 보장한다."""
    from rag.dur_master import (
        search_age_taboo,
        search_elderly_caution,
        search_pregnancy_taboo,
        search_usjnt_taboo,
    )
    from rag.mfds_client import search_by_name, search_permit_detail, search_permit_info

    caches = [
        search_by_name,
        search_permit_info,
        search_permit_detail,
        search_usjnt_taboo,
        search_elderly_caution,
        search_age_taboo,
        search_pregnancy_taboo,
    ]
    for cached_fn in caches:
        cached_fn.cache_clear()
    yield
    for cached_fn in caches:
        cached_fn.cache_clear()


@pytest.fixture(autouse=True)
def _no_real_dur_lookups():
    """DUR 조회 함수들이 실수로 로컬의 실제(수십만~87만 행) CSV를 읽지 않도록 기본값을 빈 리스트로 고정한다.

    이 CSV들은 backend/data/에 실제로 존재할 수도(개발자 로컬), 없을 수도(CI, 다른 팀원 로컬) 있다 —
    있으면 테스트가 우연히 실제 데이터에 의존하게 되고, 없으면 FileNotFoundError를 조용히 삼켜
    빈 리스트가 되므로 두 환경에서 결과가 갈릴 수 있다. DUR 관련 동작 자체를 검증하는 테스트는
    이 fixture 안에서 `with patch(...)`로 필요한 값을 다시 지정해서 덮어쓰면 된다(중첩 patch가 우선).
    """
    with (
        patch("rag.rag_chain.search_usjnt_taboo", return_value=[]),
        patch("rag.rag_chain.search_elderly_caution", return_value=[]),
        patch("rag.rag_chain.search_age_taboo", return_value=[]),
        patch("rag.rag_chain.search_pregnancy_taboo", return_value=[]),
        patch("rag.rag_chain.search_kdca_health_info", return_value=[]),
        # [2026-07-28 추가] _lifestyle_context_items가 title 정확매칭을 먼저 시도하도록
        # 바뀌면서 이 함수도 실수로 실제 벡터DB를 조회하지 않도록 기본값을 고정해야 한다.
        patch("rag.rag_chain.search_kdca_health_info_by_title", return_value=[]),
        # [2026-07-14 추가] search_permit_info도 같은 이유로 기본값을 빈 리스트로 고정 —
        # 실제 API를 실수로 호출하지 않도록(HIRA 조회와 동일하게 기존 다수 테스트가
        # search_hira_by_product_name만 mock하고 있어 이것까지 막아둬야 안전함).
        patch("rag.rag_chain.search_permit_info", return_value=[]),
        # [2026-07-14 추가] search_permit_detail(사용상의주의사항 상세 API)도 동일한 이유로 고정.
        patch("rag.rag_chain.search_permit_detail", return_value=[]),
    ):
        yield
