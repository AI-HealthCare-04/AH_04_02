from pathlib import Path

from rag_prototype.dur_master import (
    search_age_taboo,
    search_elderly_caution,
    search_pregnancy_taboo,
    search_usjnt_taboo,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dur_taboo_sample.csv"
ELDERLY_FIXTURE = Path(__file__).parent / "fixtures" / "dur_elderly_caution_sample.csv"
ELDERLY_NSAID_FIXTURE = Path(__file__).parent / "fixtures" / "dur_elderly_caution_nsaid_sample.csv"
AGE_TABOO_FIXTURE = Path(__file__).parent / "fixtures" / "dur_age_taboo_sample.csv"
PREGNANCY_TABOO_FIXTURE = Path(__file__).parent / "fixtures" / "dur_pregnancy_taboo_sample.csv"


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


def test_search_elderly_caution_combines_both_lists():
    """일반 노인주의 + 해열진통소염제 전용 노인주의 목록을 둘 다 조회해서 합친다."""
    results = search_elderly_caution(
        "요시케어정5밀리그램(솔리페나신숙신산염)", elderly_path=ELDERLY_FIXTURE, nsaid_path=ELDERLY_NSAID_FIXTURE
    )

    assert len(results) == 1
    assert results[0].category == "노인주의"
    assert "항콜린" in results[0].detail


def test_search_elderly_caution_nsaid_list():
    results = search_elderly_caution("에이서캡슐(아세클로페낙)", elderly_path=ELDERLY_FIXTURE, nsaid_path=ELDERLY_NSAID_FIXTURE)

    assert len(results) == 1
    assert results[0].category == "노인주의(해열진통소염제)"
    assert "위장관계" in results[0].detail


def test_search_elderly_caution_no_match_returns_empty():
    assert search_elderly_caution("존재하지않는약", elderly_path=ELDERLY_FIXTURE, nsaid_path=ELDERLY_NSAID_FIXTURE) == []


def test_search_age_taboo_includes_age_condition_in_extra():
    results = search_age_taboo("마도파에취비에스캅셀125", path=AGE_TABOO_FIXTURE)

    assert len(results) == 1
    assert results[0].category == "연령금기"
    assert results[0].extra == "25세 미만"
    assert "안전성" in results[0].detail


def test_search_pregnancy_taboo_includes_grade_in_extra():
    results = search_pregnancy_taboo("씨앤유캡슐", path=PREGNANCY_TABOO_FIXTURE)

    assert len(results) == 1
    assert results[0].category == "임부금기"
    assert results[0].extra == "금기등급 1"
    assert "임부 투여금기" in results[0].detail
