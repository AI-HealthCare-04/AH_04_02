from unittest.mock import patch

import pytest


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
    ):
        yield
