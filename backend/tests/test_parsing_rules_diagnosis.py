"""
test_parsing_rules_diagnosis.py — extract_diagnosis()가 진단명 뒤 텍스트를 통째로
삼키지 않는지 검증 (2026-07-20 실사용 재현 버그)

CLOVA가 연락처/발행일/처방 내역 등을 개행 없이 한 줄로 합쳐 내보내면, 기존 정지
조건(숫자+".)"+공백, "[\n■", 문자열 끝)이 전혀 안 걸려서 "진단: 제2형 당뇨병" 뒤의
연락처·처방 목록·주의문구까지 전부 diagnosis로 잡혔다 — 300자 넘는 문자열이
ocr_results.diagnosis(VARCHAR(255))를 초과해 처방전 확정 자체가 실패했다.
"""
from services.parsing_rules import _MAX_DIAGNOSIS_LEN, extract_diagnosis


def test_diagnosis_stops_before_contact_info_and_prescription_list():
    """[실사용 재현] 개행 없이 이어진 실제 OCR 텍스트에서 진단명만 추출돼야 한다."""
    text = (
        "진단: 제2형 당뇨병 연락처: 02-0000-0000 발행일: 2026-07-20 처방 의약품 "
        "No 의약품명 용법 일수 1 글루코파지정500밀리그램 1일 2회 아침, 저녁 식후 "
        "1정28일 2 자누비아정100밀리그램 1일 1회 아침 1정 28일 참고 "
        "주의사항(허가사항 기반 OCR 테스트 문구) - 저혈당 증상 및 음주 여부 확인 "
        "ONLY - 조영제 검사 예정 시 의료진에게 복용 사실 알림 본 이미지는 "
        "OCR/약명 매핑/RAG 테스트를 위한 합성 이미지입니다. 실제 처방전으로 사용할 "
        "수 없으며, 진료/투약 판단에 사용하지 마세요."
    )
    assert extract_diagnosis(text) == "제2형 당뇨병"


def test_diagnosis_result_never_exceeds_db_column_safe_length():
    """정지 조건을 전부 못 거른 극단적인 입력이 와도(예: 예상 못 한 포맷) 결과 길이가
    ocr_results.diagnosis(VARCHAR(255))를 절대 넘지 않아야 한다."""
    text = "진단: " + ("아" * 500)
    result = extract_diagnosis(text)
    assert len(result) <= _MAX_DIAGNOSIS_LEN


def test_diagnosis_still_works_for_simple_bracketed_format():
    """기존 지원 포맷(개행/괄호로 명확히 끊기는 경우)은 그대로 동작해야 한다."""
    text = "진단: 고혈압\n[급여][A1234] 노바스크정5mg 1정 1일 1회 30일"
    assert extract_diagnosis(text) == "고혈압"
