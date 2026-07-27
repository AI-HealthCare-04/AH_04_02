"""
test_parsing_rules_dosage_forms.py — 정제/캡슐 외 제형(시럽/주사/패치/연고/점안 등)
인식 회귀 방지 테스트 (2026-07-27 추가)

정제(정)/캡슐 위주로만 자라온 제형 키워드 목록 때문에, 처방전 OCR이 그 외 제형을
제대로 인식하지 못하는 문제가 실사용에서 보고됐다:
  - "패치"(더 흔한 표기, "패취"만 인식되던 문제)로 끝나는 약은 DRUG_NAME_RE 자체가
    매칭 실패해 약이 통째로 인식 결과에서 사라졌다.
  - 점안액/점이액(안약/귀약), 환(알약)도 같은 이유로 누락됐다.
  - 시럽/점안액처럼 부피·방울 단위로 복용량을 쓰는 제형은 "1회 복용량"(dosage)이
    단위 없는 숫자로 오인되어 약품명의 제형이 엉뚱하게 붙었다("1방울" → "1액").
"""
from services.parsing_rules import (
    DRUG_NAME_RE,
    _detect_format,
    extract_dose_quantity,
    parse_prescription,
)


# ── DRUG_NAME_RE — 정제/캡슐 외 제형 인식 ──────────────────────────────────

def test_drug_name_re_matches_patch_common_spelling():
    """"패치"(더 흔한 표기) — 예전엔 "패취"만 인식돼 이 표기의 약은 통째로 누락됐다."""
    m = DRUG_NAME_RE.search("리도카인패치 1매 1일 1회 #7")
    assert m is not None
    assert m.group(1) == "리도카인패치"


def test_drug_name_re_matches_patch_alternate_spelling():
    """기존에 이미 지원되던 "패취" 표기는 계속 인식돼야 한다."""
    m = DRUG_NAME_RE.search("리도카인패취 1매 1일 1회 #7")
    assert m is not None
    assert m.group(1) == "리도카인패취"


def test_drug_name_re_matches_eye_drop_form():
    m = DRUG_NAME_RE.search("히알루론산점안액 1방울 1일 3회 #7")
    assert m is not None
    assert m.group(1) == "히알루론산점안액"


def test_drug_name_re_matches_ear_drop_form():
    m = DRUG_NAME_RE.search("오플록사신점이액 2방울 1일 2회 #5")
    assert m is not None
    assert m.group(1) == "오플록사신점이액"


def test_drug_name_re_matches_pill_form():
    m = DRUG_NAME_RE.search("우황청심환 1환 1일 1회 #3")
    assert m is not None
    assert m.group(1) == "우황청심환"


def test_drug_name_re_matches_nasal_spray_form():
    """[2026-07-27 추가 재현] "나잘스프레이"가 처방전에 있으면 이 약 자체가 인식
    결과에서 사라진다고 신고됨 — "스프레이"가 제형 목록에 없었다."""
    m = DRUG_NAME_RE.search("나잘스프레이 1회 2분무 1일 3회 #7")
    assert m is not None
    assert m.group(1) == "나잘스프레이"


def test_drug_name_re_still_matches_tablet_and_capsule():
    """기존 정제/캡슐 인식은 회귀 없이 그대로 동작해야 한다."""
    assert DRUG_NAME_RE.search("타이레놀정500mg").group(1) == "타이레놀정"
    assert DRUG_NAME_RE.search("오메프라졸캡슐20mg").group(1) == "오메프라졸캡슐"


# ── DRUG_NAME_RE — [2026-07-27 추가] 제형 표준 참고표 기준 추가 제형 ──────────

def test_drug_name_re_matches_granule_forms():
    assert DRUG_NAME_RE.search("타이레놀과립500mg").group(1) == "타이레놀과립"
    assert DRUG_NAME_RE.search("아스피린세립100mg").group(1) == "아스피린세립"


def test_drug_name_re_matches_liquid_forms():
    assert DRUG_NAME_RE.search("종합감기엘릭서").group(1) == "종합감기엘릭서"
    assert DRUG_NAME_RE.search("자양강장드링크").group(1) == "자양강장드링크"


def test_drug_name_re_matches_injection_container_forms():
    assert DRUG_NAME_RE.search("에피네프린앰플 1mg/ml").group(1) == "에피네프린앰플"
    assert DRUG_NAME_RE.search("인슐린바이알").group(1) == "인슐린바이알"
    assert DRUG_NAME_RE.search("인슐린프리필드시린지").group(1) == "인슐린프리필드시린지"


def test_drug_name_re_matches_paste_form():
    assert DRUG_NAME_RE.search("트리암시놀론페이스트").group(1) == "트리암시놀론페이스트"


def test_drug_name_re_matches_suppository_forms():
    assert DRUG_NAME_RE.search("디클로페낙좌제").group(1) == "디클로페낙좌제"
    assert DRUG_NAME_RE.search("인도메타신좌약").group(1) == "인도메타신좌약"


def test_drug_name_re_matches_film_form():
    assert DRUG_NAME_RE.search("온단세트론필름").group(1) == "온단세트론필름"


def test_drug_name_re_matches_troche_and_lozenge_forms():
    assert DRUG_NAME_RE.search("벤지다민트로키").group(1) == "벤지다민트로키"
    assert DRUG_NAME_RE.search("포비돈로젠지").group(1) == "포비돈로젠지"


def test_drug_name_re_matches_gum_form():
    assert DRUG_NAME_RE.search("니코틴껌").group(1) == "니코틴껌"


# ── extract_dose_quantity — 부피·방울 단위 ──────────────────────────────────

def test_extract_dose_quantity_with_ml_unit():
    assert extract_dose_quantity("1회 10ml, 1일 3회 (식후) 복용", form="시럽") == "10ml"


def test_extract_dose_quantity_with_drop_unit():
    assert extract_dose_quantity("1회 1방울, 1일 3회 점안", form="액") == "1방울"


def test_extract_dose_quantity_drop_unit_does_not_fall_back_to_drug_form():
    """[재현] "방울"이 단위로 인식되지 않으면 (3) 폴백에서 약품명 제형("액")이
    엉뚱하게 붙어 "1액" 같은 말이 안 되는 값이 만들어졌다."""
    result = extract_dose_quantity("1방울 1일 3회", form="액")
    assert result == "1방울"
    assert result != "1액"


# ── extract_dose_quantity — [2026-07-27 추가] g/단위/분사/퍼프/앰플/바이알/시린지/개/매 ──

def test_extract_dose_quantity_with_gram_unit_for_powder():
    """산제/과립제는 흔히 "1회 2g"처럼 중량으로 복용량을 표기한다."""
    assert extract_dose_quantity("1회 2g, 1일 3회 (식후)", form="산") == "2g"


def test_extract_dose_quantity_with_insulin_unit():
    """[실사용 예시] "인슐린 프리필드펜 1회 10단위(Unit)"."""
    assert extract_dose_quantity("1회 10단위 피하주사, 1일 1회", form="시린지") == "10단위"


def test_extract_dose_quantity_with_puff_unit_for_inhaler():
    assert extract_dose_quantity("1회 2퍼프, 1일 2회 흡입", form="스프레이") == "2퍼프"


def test_extract_dose_quantity_with_spray_count_unit():
    assert extract_dose_quantity("양쪽 비공 1회 1분사, 1일 3회", form="스프레이") == "1분사"


def test_extract_dose_quantity_with_stick_unit():
    assert extract_dose_quantity("1회 1스틱, 1일 3회 (식후)", form="시럽") == "1스틱"


def test_extract_dose_quantity_with_ampoule_and_vial_units():
    assert extract_dose_quantity("1회 1앰플 정맥주사, 1일 1회", form="주") == "1앰플"
    assert extract_dose_quantity("1회 1바이알 근육주사, 1일 1회", form="주") == "1바이알"


def test_extract_dose_quantity_with_patch_sheet_unit():
    assert extract_dose_quantity("1회 1매 부착, 1일 1회 교체", form="패치") == "1매"


# ── extract_dose_quantity — [2026-07-27 추가] 숫자가 "회"에 붙는 스프레이 표기 ──

def test_extract_dose_quantity_spray_count_attached_to_hoe_with_ssik():
    """[실사용 예시] "양쪽 비공 1회씩 분사"처럼 숫자가 분사가 아니라 "회"에 붙어
    나오는 표기 — 분무/분사에 숫자가 직접 안 붙어 있으면 예전엔 빈 값이었다."""
    assert extract_dose_quantity("양쪽 비공 1회씩 분사, 1일 3회") == "1분사"


def test_extract_dose_quantity_spray_count_attached_to_hoe_without_ssik():
    assert extract_dose_quantity("매회 1회 분무, 1일 3회") == "1분무"


def test_extract_dose_quantity_direct_spray_count_still_takes_priority():
    """숫자가 분무/분사에 직접 붙어 있으면(더 명시적) 그걸 우선한다."""
    assert extract_dose_quantity("1회 2분무, 1일 3회") == "2분무"


# ── _detect_format — 크림/연고/패치 등도 list 포맷으로 인식 ──────────────────

def test_detect_format_recognizes_list_with_ointment_entry():
    text = (
        "1. 리도카인패치 1매 1일 1회 #7\n"
        "2. 하이드로코르티손연고 1회 적당량 1일 2회 도포"
    )
    assert _detect_format(text) == "list"


# ── parse_prescription — 제형별 end-to-end ─────────────────────────────────

def test_parse_prescription_syrup_reads_ml_dose_quantity():
    raw = "1. 아세트아미노펜시럽 1회 10ml, 1일 3회 (식후), 5일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == "10ml"


def test_parse_prescription_eye_drop_reads_drop_dose_quantity():
    raw = "1. 히알루론산점안액 1회 1방울, 1일 3회, 30일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["drug_name"].startswith("히알루론산점안액")
    assert meds[0]["dosage"] == "1방울"


def test_parse_prescription_patch_is_not_dropped_from_results():
    """[재현] "패치" 표기는 DRUG_NAME_RE 매칭 실패로 이 약 자체가 결과에서
    사라졌었다."""
    raw = "1. 리도카인패치 1회 1매, 1일 1회, 7일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["drug_name"].startswith("리도카인패치")


def test_parse_prescription_pill_form_is_recognized():
    raw = "1. 우황청심환 1회 1환, 1일 1회, 3일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["drug_name"].startswith("우황청심환")


def test_parse_prescription_nasal_spray_is_not_dropped_from_results():
    """[재현] "나잘스프레이"가 DRUG_NAME_RE 매칭 실패로 결과에서 통째로 사라졌었다."""
    raw = "1. 나잘스프레이 1회 2분무, 1일 3회, 7일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["drug_name"].startswith("나잘스프레이")
    assert meds[0]["dosage"] == "2분무"


def test_parse_prescription_insulin_syringe_reads_unit_dose_quantity():
    """[실사용 예시] 인슐린 프리필드시린지 — "1회 10단위"."""
    raw = "1. 인슐린프리필드시린지 1회 10단위 피하주사, 1일 1회, 30일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["drug_name"].startswith("인슐린프리필드시린지")
    assert meds[0]["dosage"] == "10단위"


def test_parse_prescription_powder_reads_gram_dose_quantity():
    raw = "1. 타이레놀산 1회 2g, 1일 3회 (식후), 5일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == "2g"


def test_parse_prescription_gum_form_is_recognized():
    raw = "1. 니코틴껌 1회 1개, 1일 4회, 14일분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["drug_name"].startswith("니코틴껌")
    assert meds[0]["dosage"] == "1개"
