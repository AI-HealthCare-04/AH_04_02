from services.parsing_rules import (
    DRUG_NAME_RE,
    is_official_prescription_table,
    parse_official_table_by_bbox,
)


def test_drug_name_re_negative_lookahead_prevents_false_positives():
    """'자몽주스'의 '주', '샘플은OCR'의 'CR'처럼 단어 중간의 제형어/접미사가 약품명으로 오인식되는 문제를 방지한다."""
    assert DRUG_NAME_RE.search("자몽주스 섭취 금지") is None
    assert DRUG_NAME_RE.search("본 샘플은OCR 검증을 위해 기재했습니다") is None
    assert DRUG_NAME_RE.search("기반OCR 테스트") is None

    # 실제 약품명은 정상 매칭되어야 함
    assert DRUG_NAME_RE.search("글루코파지XR정500mg").group(1) == "글루코파지XR정"
    assert DRUG_NAME_RE.search("노바스크정5mg").group(1) == "노바스크정"
    assert DRUG_NAME_RE.search("프라그민주10000IU").group(1) == "프라그민주"


def test_is_official_prescription_table_detection():
    fields = [
        {"inferText": "No", "boundingPoly": {"vertices": [{"x": 100, "y": 800}]}},
        {"inferText": "처방", "boundingPoly": {"vertices": [{"x": 300, "y": 800}]}},
        {"inferText": "의약품", "boundingPoly": {"vertices": [{"x": 350, "y": 800}]}},
        {"inferText": "명칭", "boundingPoly": {"vertices": [{"x": 400, "y": 800}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 600, "y": 800}]}},
        {"inferText": "투약량", "boundingPoly": {"vertices": [{"x": 650, "y": 800}]}},
        {"inferText": "1일", "boundingPoly": {"vertices": [{"x": 800, "y": 800}]}},
        {"inferText": "횟수", "boundingPoly": {"vertices": [{"x": 850, "y": 800}]}},
        {"inferText": "총일수", "boundingPoly": {"vertices": [{"x": 1000, "y": 800}]}},
        {"inferText": "용법·용량", "boundingPoly": {"vertices": [{"x": 1200, "y": 800}]}},
        {"inferText": "조제시", "boundingPoly": {"vertices": [{"x": 1400, "y": 800}]}},
    ]
    assert is_official_prescription_table(fields) is True

    # 하나라도 누락되면 False
    fields_incomplete = [f for f in fields if f["inferText"] != "총일수"]
    assert is_official_prescription_table(fields_incomplete) is False


def test_parse_official_table_by_bbox_end_to_end():
    fields = [
        # 헤더 7개 컬럼
        {"inferText": "No", "boundingPoly": {"vertices": [{"x": 120, "y": 800}]}},
        {"inferText": "처방", "boundingPoly": {"vertices": [{"x": 300, "y": 800}]}},
        {"inferText": "의약품", "boundingPoly": {"vertices": [{"x": 350, "y": 800}]}},
        {"inferText": "명칭", "boundingPoly": {"vertices": [{"x": 400, "y": 800}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 668, "y": 800}]}},
        {"inferText": "투약량", "boundingPoly": {"vertices": [{"x": 696, "y": 800}]}},
        {"inferText": "1일", "boundingPoly": {"vertices": [{"x": 837, "y": 800}]}},
        {"inferText": "횟수", "boundingPoly": {"vertices": [{"x": 886, "y": 800}]}},
        {"inferText": "총일수", "boundingPoly": {"vertices": [{"x": 993, "y": 800}]}},
        {"inferText": "용법·용량", "boundingPoly": {"vertices": [{"x": 1221, "y": 800}]}},
        {"inferText": "조제시", "boundingPoly": {"vertices": [{"x": 1400, "y": 800}]}},
        # 행 1: 노바스크정5mg
        {"inferText": "1", "boundingPoly": {"vertices": [{"x": 121, "y": 900}]}},
        {"inferText": "노바스크정5mg", "boundingPoly": {"vertices": [{"x": 171, "y": 900}]}},
        {"inferText": "1정", "boundingPoly": {"vertices": [{"x": 687, "y": 900}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 853, "y": 900}]}},
        {"inferText": "30일", "boundingPoly": {"vertices": [{"x": 1003, "y": 900}]}},
        {"inferText": "아침", "boundingPoly": {"vertices": [{"x": 1230, "y": 900}]}},
        # 표 밖 면허번호/전화번호 (총일수 오인식 차단 테스트)
        {"inferText": "면허번호", "boundingPoly": {"vertices": [{"x": 120, "y": 1400}]}},
        {"inferText": "123456", "boundingPoly": {"vertices": [{"x": 200, "y": 1400}]}},
        {"inferText": "031-000-0000", "boundingPoly": {"vertices": [{"x": 300, "y": 1400}]}},
    ]

    meds = parse_official_table_by_bbox(fields)
    assert len(meds) == 1
    assert meds[0]["drug_name"] == "노바스크정 5mg"
    assert meds[0]["dosage"] == "1정"
    assert meds[0]["frequency"] == "1회"
    assert meds[0]["total_days"] == "30일"


def test_parse_official_table_by_bbox_inhaler_row_not_dropped():
    """실사용 재현(prescription_sample_03, 천식·알레르기 비염): "심비코트터부헬러"처럼
    정/캡슐/액 같은 통상 제형어가 아니라 흡입기 디바이스명("헬러")으로 끝나는 약품명이
    row_anchors 판정에서 통째로 빠져 그 행이 사라지고, 값이 다음 행(알레그라정)에
    섞여 들어가던 버그의 회귀 테스트."""
    fields = [
        # 헤더 7개 컬럼
        {"inferText": "No", "boundingPoly": {"vertices": [{"x": 120, "y": 800}]}},
        {"inferText": "처방", "boundingPoly": {"vertices": [{"x": 300, "y": 800}]}},
        {"inferText": "의약품", "boundingPoly": {"vertices": [{"x": 350, "y": 800}]}},
        {"inferText": "명칭", "boundingPoly": {"vertices": [{"x": 400, "y": 800}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 668, "y": 800}]}},
        {"inferText": "투약량", "boundingPoly": {"vertices": [{"x": 696, "y": 800}]}},
        {"inferText": "1일", "boundingPoly": {"vertices": [{"x": 837, "y": 800}]}},
        {"inferText": "횟수", "boundingPoly": {"vertices": [{"x": 886, "y": 800}]}},
        {"inferText": "총일수", "boundingPoly": {"vertices": [{"x": 993, "y": 800}]}},
        {"inferText": "용법·용량", "boundingPoly": {"vertices": [{"x": 1221, "y": 800}]}},
        {"inferText": "조제시", "boundingPoly": {"vertices": [{"x": 1400, "y": 800}]}},
        # 행 1: 심비코트터부헬러160/4.5마이크로그램 — 1흡입/2회/30일
        {"inferText": "1", "boundingPoly": {"vertices": [{"x": 121, "y": 900}]}},
        {"inferText": "심비코트터부헬러160/4.5마이크로그램", "boundingPoly": {"vertices": [{"x": 171, "y": 900}]}},
        {"inferText": "1흡입", "boundingPoly": {"vertices": [{"x": 687, "y": 900}]}},
        {"inferText": "2회", "boundingPoly": {"vertices": [{"x": 853, "y": 900}]}},
        {"inferText": "30일", "boundingPoly": {"vertices": [{"x": 1003, "y": 900}]}},
        {"inferText": "아침·저녁", "boundingPoly": {"vertices": [{"x": 1230, "y": 900}]}},
        # 행 2: 알레그라정120밀리그램 — 1정/1회/14일
        {"inferText": "2", "boundingPoly": {"vertices": [{"x": 121, "y": 1000}]}},
        {"inferText": "알레그라정120밀리그램", "boundingPoly": {"vertices": [{"x": 171, "y": 1000}]}},
        {"inferText": "1정", "boundingPoly": {"vertices": [{"x": 687, "y": 1000}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 853, "y": 1000}]}},
        {"inferText": "14일", "boundingPoly": {"vertices": [{"x": 1003, "y": 1000}]}},
        {"inferText": "아침 식후", "boundingPoly": {"vertices": [{"x": 1230, "y": 1000}]}},
        # 행 3: 벤토린흡입액2.5밀리그램/2.5밀리리터 — 1앰플/필요시/5일
        {"inferText": "3", "boundingPoly": {"vertices": [{"x": 121, "y": 1100}]}},
        {"inferText": "벤토린흡입액2.5밀리그램/2.5밀리리터", "boundingPoly": {"vertices": [{"x": 171, "y": 1100}]}},
        {"inferText": "1앰플", "boundingPoly": {"vertices": [{"x": 687, "y": 1100}]}},
        {"inferText": "필요시", "boundingPoly": {"vertices": [{"x": 853, "y": 1100}]}},
        {"inferText": "5일", "boundingPoly": {"vertices": [{"x": 1003, "y": 1100}]}},
        {"inferText": "네불라이저 흡입", "boundingPoly": {"vertices": [{"x": 1230, "y": 1100}]}},
    ]

    meds = parse_official_table_by_bbox(fields)
    assert len(meds) == 3

    assert meds[0]["drug_name"] == "심비코트터부헬러"
    assert meds[0]["dosage"] == "1흡입"
    assert meds[0]["frequency"] == "2회"
    assert meds[0]["total_days"] == "30일"

    assert meds[1]["drug_name"] == "알레그라정"
    assert meds[1]["dosage"] == "1정"
    assert meds[1]["frequency"] == "1회"
    assert meds[1]["total_days"] == "14일"

    assert meds[2]["drug_name"] == "벤토린흡입액"
    assert meds[2]["dosage"] == "1앰플"
    assert meds[2]["frequency"] == "필요시"
    assert meds[2]["total_days"] == "5일"


def test_parse_official_table_by_bbox_plaster_row_not_dropped():
    """실사용 재현(prescription_sample_02, 고지혈증·통증): "케토톱플라스타"처럼
    "패취/패치" 대신 "플라스타"(plaster)로 표기된 패취제 약품명이 row_anchors
    판정에서 통째로 빠져 그 행이 사라지던 버그의 회귀 테스트."""
    fields = [
        # 헤더 7개 컬럼
        {"inferText": "No", "boundingPoly": {"vertices": [{"x": 120, "y": 800}]}},
        {"inferText": "처방", "boundingPoly": {"vertices": [{"x": 300, "y": 800}]}},
        {"inferText": "의약품", "boundingPoly": {"vertices": [{"x": 350, "y": 800}]}},
        {"inferText": "명칭", "boundingPoly": {"vertices": [{"x": 400, "y": 800}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 668, "y": 800}]}},
        {"inferText": "투약량", "boundingPoly": {"vertices": [{"x": 696, "y": 800}]}},
        {"inferText": "1일", "boundingPoly": {"vertices": [{"x": 837, "y": 800}]}},
        {"inferText": "횟수", "boundingPoly": {"vertices": [{"x": 886, "y": 800}]}},
        {"inferText": "총일수", "boundingPoly": {"vertices": [{"x": 993, "y": 800}]}},
        {"inferText": "용법·용량", "boundingPoly": {"vertices": [{"x": 1221, "y": 800}]}},
        {"inferText": "조제시", "boundingPoly": {"vertices": [{"x": 1400, "y": 800}]}},
        # 행 1: 크레스토정10밀리그램 — 1정/1회/28일
        {"inferText": "1", "boundingPoly": {"vertices": [{"x": 121, "y": 900}]}},
        {"inferText": "크레스토정10밀리그램", "boundingPoly": {"vertices": [{"x": 171, "y": 900}]}},
        {"inferText": "1정", "boundingPoly": {"vertices": [{"x": 687, "y": 900}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 853, "y": 900}]}},
        {"inferText": "28일", "boundingPoly": {"vertices": [{"x": 1003, "y": 900}]}},
        {"inferText": "저녁 식후", "boundingPoly": {"vertices": [{"x": 1230, "y": 900}]}},
        # 행 2: 타이레놀8시간이알서방정650밀리그램 — 1정/2회/5일
        {"inferText": "2", "boundingPoly": {"vertices": [{"x": 121, "y": 1000}]}},
        {"inferText": "타이레놀8시간이알서방정650밀리그램", "boundingPoly": {"vertices": [{"x": 171, "y": 1000}]}},
        {"inferText": "1정", "boundingPoly": {"vertices": [{"x": 687, "y": 1000}]}},
        {"inferText": "2회", "boundingPoly": {"vertices": [{"x": 853, "y": 1000}]}},
        {"inferText": "5일", "boundingPoly": {"vertices": [{"x": 1003, "y": 1000}]}},
        {"inferText": "통증 시 경구투여", "boundingPoly": {"vertices": [{"x": 1230, "y": 1000}]}},
        # 행 3: 케토톱플라스타 — 1매/1회/7일
        {"inferText": "3", "boundingPoly": {"vertices": [{"x": 121, "y": 1100}]}},
        {"inferText": "케토톱플라스타", "boundingPoly": {"vertices": [{"x": 171, "y": 1100}]}},
        {"inferText": "1매", "boundingPoly": {"vertices": [{"x": 687, "y": 1100}]}},
        {"inferText": "1회", "boundingPoly": {"vertices": [{"x": 853, "y": 1100}]}},
        {"inferText": "7일", "boundingPoly": {"vertices": [{"x": 1003, "y": 1100}]}},
        {"inferText": "통증 부위에 부착", "boundingPoly": {"vertices": [{"x": 1230, "y": 1100}]}},
    ]

    meds = parse_official_table_by_bbox(fields)
    assert len(meds) == 3

    assert meds[0]["drug_name"] == "크레스토정"
    assert meds[1]["drug_name"] == "타이레놀8시간이알서방정"

    assert meds[2]["drug_name"] == "케토톱플라스타"
    assert meds[2]["dosage"] == "1매"
    assert meds[2]["frequency"] == "1회"
    assert meds[2]["total_days"] == "7일"
