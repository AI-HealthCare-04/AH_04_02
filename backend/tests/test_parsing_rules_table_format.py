"""
test_parsing_rules_table_format.py — _parse_table_format() 회귀 방지 테스트 (2026-07-31 추가)

PR #133(처방전 표 폴백 파서의 오탐/PRN/총 투약일수 버그 수정)은 실제 CLOVA OCR로
mock_prescription_*.png 15장을 end-to-end 업로드해서 검증했지만, `_parse_table_format`을
직접 겨냥한 자동화된 단위 테스트는 없었다(pecs0310 PR #133 리뷰 반영) — 표 폴백 파서를
나중에 다시 건드릴 때 이번에 고친 3가지가 조용히 재발하는 걸 막기 위해, 그때 재현했던
실제 처방전(mock_prescription_03.png/mock_prescription_05.png) 텍스트 구조를 그대로
합성 텍스트로 재현해 회귀 테스트로 남긴다.
"""
from services.parsing_rules import DRUG_NAME_RE, parse_prescription

# ── 버그 1: DRUG_NAME_RE가 "질환"의 "환"을 알약 제형으로 오매칭 ──────────────


def test_drug_name_re_does_not_match_jilhwan_diagnosis_word():
    """[mock_prescription_03.png 재현] 진단명 "심혈관질환"의 "환"이 알약(환) 제형
    접미사로 오매칭되어 "심혈관질"이 가짜 약품명으로 잡히면 안 된다."""
    assert DRUG_NAME_RE.search("고혈압, 심혈관질환 예방") is None


def test_drug_name_re_still_matches_real_hwan_dosage_form():
    """"질" 뒤의 "환"만 제외해야 한다 — 실제 "환"(알약) 제형 약품명은 그대로 인식돼야 함."""
    m = DRUG_NAME_RE.search("우황청심환 1환 복용")
    assert m is not None
    assert m.group(1) == "우황청심환"


def test_table_format_does_not_misalign_rows_after_diagnosis_false_positive():
    """진단명 줄의 "심혈관질환"이 가짜 약품명으로 잡히면, 위치(인덱스) 기반 용법/일수
    배열이 한 칸씩 밀려 마지막 실제 약(크레스토정)의 필드가 통째로 빈 값이 됐었다."""
    raw = (
        "진단명: 고혈압, 심혈관질환 예방 처방 의약품 No 의약품명 용법 일수 "
        "1 디오반필름코팅정80밀리그램 1일 1회 아침 1정 60일 "
        "2 플라빅스정75밀리그램 1일 1회 아침 식후 1정 60일 "
        "3 크레스토정10밀리그램 1일 1회 저녁 1정 60일"
    )
    meds, _ = parse_prescription(raw)

    assert len(meds) == 3  # 진단명의 "심혈관질환"이 4번째 가짜 약으로 섞이면 안 됨
    assert meds[2]["drug_name"] == "크레스토정"
    assert meds[2]["frequency"] == "1회"
    assert meds[2]["total_days"] == "60일"


# ── 버그 2/3: "1회 분무" 같은 PRN 표기 + 행마다 반복되는 "N일" ────────────────


def test_table_format_multi_row_reads_prn_and_total_days_per_row():
    """[mock_prescription_05.png 재현] "약품명 1일 N회 ... N일"이 약마다 한 행씩
    반복되는 구조에서: (1) 앞쪽 약들의 "30일"이 마지막 횟수 매치 이후로만 찾는
    옛 로직 때문에 놓치지 않아야 하고, (2) "1회 분무"처럼 숫자 뒤에 한글이 바로
    오는 PRN 표기는 이 파서만 가진 PRN 폴백 부재로 비어있지 않아야 한다."""
    raw = (
        "처방 의약품 No 의약품명 용법 일수 "
        "1 심바스타틴정20밀리그램 1일 1회 저녁 1정 30일 "
        "2 노바스크정5밀리그램 1일 1회 아침 1정 30일 "
        "3 니트로링구알스프레이 흉통 시 혀 밑에 1회 분무 필요시"
    )
    meds, _ = parse_prescription(raw)

    assert len(meds) == 3
    assert meds[0]["drug_name"] == "심바스타틴정"
    assert meds[0]["frequency"] == "1회"
    assert meds[0]["total_days"] == "30일"  # 수정 전엔 엉뚱한 각주/헤더 숫자가 배정됨
    assert meds[1]["drug_name"] == "노바스크정"
    assert meds[1]["frequency"] == "1회"
    assert meds[1]["total_days"] == "30일"
    assert meds[2]["drug_name"] == "니트로링구알스프레이"
    assert meds[2]["frequency"] == "필요시"  # 수정 전엔 빈 문자열
    assert meds[2]["total_days"] == "필요시"  # 수정 전엔 빈 문자열


def test_table_format_bare_freq_number_is_not_misread_as_total_days():
    """총 투약일수 폴백(bare-number 정규식)이 "회"(횟수)를 제외 목록에 안 넣으면,
    BARE_FREQ_RE가 이미 포기한("1회 분무") "1회"의 "1"이 다시 걸려 "1일"로
    잘못 채워졌다 — PRN 행의 total_days가 숫자로 잘못 채워지면 안 된다."""
    raw = (
        "처방 의약품 No 의약품명 용법 일수 "
        "1 니트로링구알스프레이 흉통 시 혀 밑에 1회 분무 필요시"
    )
    meds, _ = parse_prescription(raw)

    assert len(meds) == 1
    assert meds[0]["total_days"] == "필요시"
