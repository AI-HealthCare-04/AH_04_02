from pathlib import Path

from rag_prototype.dur_master import search_usjnt_taboo

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dur_taboo_sample.csv"


def test_search_usjnt_taboo_exact_match_returns_mixture_partner():
    results = search_usjnt_taboo("와파린정", path=FIXTURE_PATH)

    assert len(results) == 1
    assert results[0].item_name == "와파린정"
    assert results[0].mixture_item_name == "아스피린정"
    assert results[0].prohbt_content == "출혈 위험 증가로 병용을 피하십시오."


def test_search_usjnt_taboo_is_bidirectional():
    """제품명B로 조회해도 제품명A가 상대로 나온다 (관계에 방향이 없음)."""
    results = search_usjnt_taboo("아스피린정", path=FIXTURE_PATH)

    assert len(results) == 1
    assert results[0].mixture_item_name == "와파린정"


def test_search_usjnt_taboo_falls_back_to_partial_match():
    results = search_usjnt_taboo("로자탄", path=FIXTURE_PATH)

    assert len(results) == 1
    assert results[0].mixture_item_name == "스피로노락톤정"


def test_search_usjnt_taboo_no_match_returns_empty():
    assert search_usjnt_taboo("존재하지않는약", path=FIXTURE_PATH) == []


def test_search_usjnt_taboo_missing_file_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        search_usjnt_taboo("와파린정", path=Path("/no/such/file.csv"))
