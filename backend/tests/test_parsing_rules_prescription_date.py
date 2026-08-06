"""
test_parsing_rules_prescription_date.py — extract_prescription_date() 검증
(2026-07-23 추가)

"전에 쓴 것과 같은 처방전인지 날짜로 알아볼 수 없나"라는 질문에서 시작 — mock
처방전 생성 스크립트 6종을 확인해보니 "조제일자/처방일자/진료일자/조제일" 라벨은
6개 포맷 전부에 있었고(YYYY-MM-DD, YYYY.MM.DD 두 형식), "처방번호"는 1개 포맷에만
있어 중복판정 근거로 못 쓴다고 판단했다(처방번호 쪽은 팀원이 별도 조사 중).
"""
from services.parsing_rules import extract_prescription_date


def test_dash_format_with_label_josuljilja():
    assert extract_prescription_date("조제일자: 2026-07-01") == "2026-07-01"


def test_dash_format_with_label_cheobangilja_no_colon():
    assert extract_prescription_date("처방일자 2026-06-30 처방의약품") == "2026-06-30"


def test_dot_format_with_label_josulil():
    assert extract_prescription_date("조제일 2026.07.01") == "2026-07-01"


def test_jinryoilja_with_single_digit_month_day():
    assert extract_prescription_date("진료일자: 2026.7.9") == "2026-07-09"


def test_no_date_label_returns_empty():
    assert extract_prescription_date("암로디핀정5밀리그램 1일 1회 30일분") == ""
