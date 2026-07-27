"""
test_parsing_rules_prn.py — "필요시"(PRN) 인식 테스트 (2026-07-27 추가)

extract_frequency/extract_days는 원래 hs/ac/pc(타이밍)와 함께 prn도 "1일 투약횟수"/
"총 투약일수"에 어울리지 않는 값이라 빈 문자열로 걸러냈다. 그런데 실제로는 "필요시"
자체를 화면에 그대로 보여주는 게 더 유용하다는 요청이 있어, prn만 예외로 분리해서
값을 반환하도록 바꿨다 — 영문 약어("prn")와 한글 표기("필요시") 둘 다 인식해야 한다.
"""
from services.parsing_rules import extract_days, extract_frequency, parse_prescription


# ── extract_frequency ───────────────────────────────────────────────────────

def test_extract_frequency_recognizes_korean_prn_text():
    assert extract_frequency("타이레놀정500mg 1회 1정 필요시 복용") == "필요시"


def test_extract_frequency_recognizes_prn_abbreviation():
    assert extract_frequency("APAP 500mg 1T prn") == "필요시"


def test_extract_frequency_prefers_explicit_count_over_prn():
    """명시적인 횟수("1일 3회")가 있으면 그걸 우선하고, 굳이 "필요시"로 덮어쓰지 않는다."""
    assert extract_frequency("1일 3회 필요시 추가 복용 가능") == "3회"


def test_extract_frequency_still_filters_meal_timing_abbreviations():
    """hs/ac/pc(타이밍)는 여전히 빈 값이어야 한다 — prn만 예외다."""
    assert extract_frequency("1T hs") == ""
    assert extract_frequency("1T pc") == ""


# ── extract_days ────────────────────────────────────────────────────────────

def test_extract_days_recognizes_korean_prn_text():
    assert extract_days("타이레놀정500mg 1회 1정 필요시 복용") == "필요시"


def test_extract_days_recognizes_prn_abbreviation():
    assert extract_days("APAP 500mg 1T prn") == "필요시"


def test_extract_days_prefers_explicit_days_over_prn():
    assert extract_days("30일분, 필요시 추가 복용 가능") == "30일"


# ── parse_prescription end-to-end ───────────────────────────────────────────

def test_parse_prescription_abbrev_format_reads_prn_as_frequency_and_days():
    raw = "Rx)\n1) 타이레놀정500mg 1T prn"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["frequency"] == "필요시"
    assert meds[0]["total_days"] == "필요시"


def test_parse_prescription_list_format_reads_korean_prn():
    raw = "1. 타이레놀정500mg 1회 1정, 필요시 복용"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["frequency"] == "필요시"
