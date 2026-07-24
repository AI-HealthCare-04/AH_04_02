"""
test_parsing_rules_dose_quantity.py — extract_dose_quantity()/parse_prescription() 검증
(2026-07-23 추가)

"1회 투약량"(mg 등 주성분 함량, 약품명에 붙어 나옴)과 "1회 복용량"(환자가 한 번에
정/캡슐/병 몇 개를 먹는지)은 서로 다른 정보다. 이 테스트는 dosage 필드가 이제
후자(복용량)를 담는지, 세 가지 표기 방식(텍스트 단위, 약식 T/C, 단위 없는 숫자
컬럼 + 약품명 제형 조합)을 모두 인식하는지 확인한다.
"""
from services.parsing_rules import extract_dose_quantity, parse_prescription


def test_extract_dose_quantity_with_explicit_unit():
    assert extract_dose_quantity("1회 1정, 1일 1회, 30일분 복용") == "1정"


def test_extract_dose_quantity_with_capsule_unit():
    assert extract_dose_quantity("1회 1캡슐, 1일 1회 (식전), 30일분") == "1캡슐"


def test_extract_dose_quantity_with_abbrev_tablet():
    assert extract_dose_quantity("1T qd(취침전) #7") == "1정"


def test_extract_dose_quantity_with_abbrev_capsule():
    assert extract_dose_quantity("1C bid #14") == "1캡슐"


def test_extract_dose_quantity_bare_number_uses_form_fallback():
    # 공식 표 포맷처럼 단위 없이 숫자만 있는 컬럼 — 약품명의 제형을 붙여 완성한다.
    assert extract_dose_quantity(" 1.00 1일 1회 30", form="정") == "1정"


def test_extract_dose_quantity_bare_number_without_form_returns_empty():
    # 제형을 모르면(form 없음) 숫자만으로는 복용량을 지어내지 않는다.
    assert extract_dose_quantity(" 1.00 1일 1회 30") == ""


def test_extract_dose_quantity_does_not_pick_up_frequency_or_days_numbers():
    # "1일"/"1회"/"30"(일수)에 붙은 숫자는 복용량이 아니므로 잡히면 안 된다.
    assert extract_dose_quantity("1일 3회 30일분", form="정") == ""


def test_parse_prescription_official_format_reads_dose_quantity_not_mg():
    raw = (
        "[급여][649500569] 암로디핀정5mg(한미) 1.00 1일 1회 30\n"
        "[급여][642201549] 로자탄칼륨정50mg(종근당) 1.00 1일 1회 30\n"
        "[급여][643501076] 메트포르민정500mg(대웅) 2.00 1일 2회 30\n"
        "진단명: 고혈압, 제2형 당뇨병"
    )
    meds, _ = parse_prescription(raw)
    assert len(meds) == 3
    assert meds[0]["dosage"] == "1정"
    assert meds[1]["dosage"] == "1정"
    assert meds[2]["dosage"] == "2정"
    # 성분 함량(mg)은 dosage가 아니라 drug_name에 그대로 남아있어야 한다.
    assert "5mg" in meds[0]["drug_name"]


def test_parse_prescription_bag_format_reads_explicit_unit_text():
    raw = (
        "1. [급여][658101482] 아스피린프로텍트정100mg\n"
        "   1회 1정, 1일 1회, 30일분 복용\n"
        "2. [급여][622309872] 오메프라졸캡슐20mg\n"
        "   1회 1캡슐, 1일 1회 (식전), 30일분"
    )
    meds, _ = parse_prescription(raw)
    assert len(meds) == 2
    assert meds[0]["dosage"] == "1정"
    assert meds[1]["dosage"] == "1캡슐"


def test_parse_prescription_abbrev_format_reads_tablet_capsule_shorthand():
    raw = (
        "Pt: 이영희(모)\n"
        "Dx: 골관절염, 불면증\n\n"
        "Rx)\n"
        "1) [급여][601209872] 세레브렉스캡슐200mg 1C bid #14\n"
        "2) [급여][633409872][향정] 졸피뎀정10mg 1T qd(취침전) #7\n"
        "3) [급여][611209874] 파모티딘정20mg 1T bid #14"
    )
    meds, _ = parse_prescription(raw)
    assert len(meds) == 3
    assert meds[0]["dosage"] == "1캡슐"
    assert meds[1]["dosage"] == "1정"
    assert meds[2]["dosage"] == "1정"
