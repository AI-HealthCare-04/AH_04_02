"""
test_parsing_rules_dose_amount.py — "1회 투여량"(dose_amount, mg/ml 등) 필드와
reconcile_dose_fields()의 3가지 규칙 검증 (2026-07-25 추가)

  사용량 O                    → 그대로 둔다.
  사용량 X, 투여량 O          → 약품명에 포함된 단위당 함량으로 나눠서 개수를 역산한다.
  사용량 X, 투여량 X          → 빈 문자열(지어내지 않음).
"""
from services.parsing_rules import parse_prescription, reconcile_dose_fields


def test_reconcile_keeps_dosage_when_already_present():
    # 사용량이 이미 있으면 투여량 값과 무관하게 그대로 둔다.
    assert reconcile_dose_fields("1캡슐", "200mg", "세레브렉스캡슐 200mg") == "1캡슐"


def test_reconcile_computes_quantity_from_amount_and_name_strength():
    # 1회 투여량(10mg) ÷ 약품명 단위당 함량(5mg) = 2정.
    assert reconcile_dose_fields("", "10mg", "암로핀정 5mg") == "2정"


def test_reconcile_defaults_to_one_unit_when_amount_equals_name_strength():
    # 투여량이 약품명 함량과 같으면(둘 다 같은 값에서 왔을 때) 1개로 계산된다 —
    # 실제 처방전 대부분(정제, 별도 mg 언급 없음)이 이 경우다.
    assert reconcile_dose_fields("", "500mg", "타이레놀정 500mg") == "1정"


def test_reconcile_returns_empty_when_unit_mismatch():
    # mg 대 ml처럼 단위가 다르면 나눌 수 없다 — 지어내지 않는다.
    assert reconcile_dose_fields("", "10ml", "암로핀정 5mg") == ""


def test_reconcile_returns_empty_when_no_strength_in_name():
    # 약품명에 함량이 아예 없으면(예: 주사제 이름만) 역산할 근거가 없다.
    assert reconcile_dose_fields("", "10mg", "인슐린주") == ""


def test_reconcile_returns_empty_when_combo_drug():
    # 복합제(성분 2개, "50/1000mg")는 단순 나눗셈으로 개수를 정할 수 없다.
    assert reconcile_dose_fields("", "50/1000mg", "글리메피리드정 50/1000mg") == ""


def test_reconcile_returns_empty_when_both_missing():
    assert reconcile_dose_fields("", "", "암로핀정 5mg") == ""


def test_parse_prescription_falls_back_to_computed_quantity_when_only_mg_stated():
    # "1정"/"1T" 같은 명시적 개수 표기가 전혀 없고, 처방 문구에 별도 투여량(10mg)만
    # 있으면 약품명 함량(5mg)으로 나눠 "2정"을 역산해서 채운다.
    raw = "[급여][601209872] 암로핀정5mg 1회 10mg 1일 1회 30일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == "2정"
    assert meds[0]["dose_amount"] == "10mg"


def test_parse_prescription_table_dose_amount_column_computes_usage():
    # 테이블 헤더가 "1회 투여량"이면 해당 mg 값은 dose_amount로 먼저 저장하고,
    # 약품명 함량과 나눠 환자가 볼 1회 사용량(dosage)을 도출한다.
    raw = "약품명 1회투여량 1일횟수 투약일수 암로핀정5mg 10mg 1일 1회 30"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == "2정"
    assert meds[0]["dose_amount"] == "10mg"
    assert meds[0]["total_days"] == "30일"


def test_parse_prescription_dose_amount_label_does_not_become_total_days():
    raw = "[급여][123] 오구멘틴듀오시럽228mg/5ml 1회 투여량 5mL 1일 3회 5일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == "5mL"
    assert meds[0]["dose_amount"] == "5mL"
    assert meds[0]["total_days"] == "5일"


def test_parse_prescription_reads_dose_amount_from_name_when_no_explicit_mg_in_text():
    # 텍스트 어디에도 mg가 따로 안 적혀 있으면 약품명에 붙어 나온 함량을
    # 1회 투여량으로 폴백한다(대부분의 정제 처방전 케이스).
    raw = "[급여][649500569] 암로디핀정5mg(한미) 1.00 1일 1회 30"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == "1정"  # 이미 "1.00"+제형으로 인식됐으므로 재계산 안 함
    assert meds[0]["dose_amount"] == "5mg"
