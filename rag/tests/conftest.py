from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_mfds_disk_cache(tmp_path, monkeypatch):
    """[2026-07-21 추가 → 2026-07-30 diskcache 전환에 맞게 수정]
    lru_cache 시절의 cache_clear() 역할을 diskcache 방식으로 대체한다.

    각 테스트마다 tmp_path 아래 격리된 임시 캐시 디렉토리를 사용해 테스트 간 캐시 오염을
    방지한다 — lru_cache.cache_clear()와 달리 디스크 캐시는 프로세스 재시작 후에도 남으므로,
    단순 clear() 대신 테스트마다 새 디렉토리를 쓰는 방식이 더 안전하다.

    monkeypatch가 테스트 종료 시 _disk_cache를 자동으로 원래 값으로 복원한다.
    """
    import diskcache
    import rag.dur_master as _dur_master_mod
    import rag.mfds_client as _mfds_client_mod

    test_cache = diskcache.Cache(str(tmp_path / "mfds_cache"), timeout=1)
    monkeypatch.setattr(_mfds_client_mod, "_disk_cache", test_cache)
    monkeypatch.setattr(_dur_master_mod, "_disk_cache", test_cache)
    yield
    test_cache.close()


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
