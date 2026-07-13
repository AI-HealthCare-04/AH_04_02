from pathlib import Path

from rag.hira_master import is_registered_and_active, search_by_product_name

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hira_master_sample.csv"


def test_search_by_product_name_exact_match():
    results = search_by_product_name("타이레놀정500밀리그람(아세트아미노펜)", path=FIXTURE_PATH)

    assert len(results) == 1
    assert results[0].entp_name == "한국얀센"
    assert results[0].standard_code == "8806469025705"
    assert results[0].atc_code == "N02BE01"
    assert results[0].is_active is True


def test_search_by_product_name_falls_back_to_partial_match():
    results = search_by_product_name("아스피린", path=FIXTURE_PATH)

    assert len(results) == 1
    assert results[0].item_name == "아스피린정"


def test_search_by_product_name_no_match_returns_empty():
    assert search_by_product_name("존재하지않는약", path=FIXTURE_PATH) == []


def test_is_registered_and_active_true_when_active():
    assert is_registered_and_active("타이레놀정500밀리그람(아세트아미노펜)", path=FIXTURE_PATH) is True


def test_is_registered_and_active_false_when_cancelled():
    assert is_registered_and_active("테스트취소약정", path=FIXTURE_PATH) is False


def test_is_registered_and_active_none_when_not_found():
    assert is_registered_and_active("존재하지않는약", path=FIXTURE_PATH) is None
