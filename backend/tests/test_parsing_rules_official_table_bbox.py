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
