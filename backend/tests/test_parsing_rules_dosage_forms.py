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


# ── DRUG_NAME_RE — [2026-07-28 추가] 한글+영문 방출제어 접미사 혼용 약품명 ──────
# CLOVA가 bbox 병합으로 "글루코파지XR"처럼 한글+영문이 공백 없이 붙은 텍스트를
# 만들어내도(ocr_interface._merge_split_drug_name_fields), 기존 regex는 이걸 하나의
# 약품명으로 못 묶었다 — 순수 한글 분기는 SR/XR 등 뒤에 오는 지정 제형 접미사가
# 없어서 실패하고, 순수 영문 분기는 앞에 한글이 있어서 실패했기 때문.

def test_drug_name_re_matches_hangul_plus_release_suffix_with_dosage():
    m = DRUG_NAME_RE.search("글루코파지XR 500mg 1일 2회")
    assert m.group(1) == "글루코파지XR"


def test_drug_name_re_matches_hangul_plus_release_suffix_with_form_word():
    """제형 단어("정")가 접미사 뒤에 바로 붙어도 함께 인식된다."""
    assert DRUG_NAME_RE.search("글루코파지XR정500mg").group(1) == "글루코파지XR정"


def test_drug_name_re_matches_release_suffix_directly_followed_by_dosage_number():
    """접미사 뒤에 공백 없이 용량 숫자가 바로 붙어도(병합 필드에 흔함) 접미사까지만 약품명으로 잡는다."""
    assert DRUG_NAME_RE.search("디아미크롱MR60 1정").group(1) == "디아미크롱MR"


def test_drug_name_re_release_suffix_branch_is_case_sensitive():
    """소문자로 끝나는 일반 영단어(예: 'concor cor')는 방출제어 접미사로 오인하지 않는다 —
    regex 전체가 re.IGNORECASE라 이 분기만 (?-i:...)로 대소문자 구분을 강제한다."""
    assert DRUG_NAME_RE.search("concor cor 5mg") is None


def test_drug_name_re_still_matches_pure_korean_forms_without_english_suffix():
    """영문 접미사 분기가 추가돼도 순수 한글 제형 이름 매칭은 회귀 없이 그대로 동작한다."""
    assert DRUG_NAME_RE.search("암로디핀정5mg").group(1) == "암로디핀정"
    assert DRUG_NAME_RE.search("타이레놀8시간이알서방정").group(1) == "타이레놀8시간이알서방정"


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


# ── [2026-07-27 버그수정, PR #99 코드 리뷰 반영 — pecs0310] "N개월분"이 복용량으로 오인식 ──

def test_extract_dose_quantity_does_not_treat_month_supply_as_gae_unit():
    """[재현] "1개월분"의 "1개"가 DOSE_QTY_UNITS의 "개"에 걸려 1회 복용량으로
    오인식됐다 — "개월"은 공급 기간이지 낱개 수량이 아니다."""
    assert extract_dose_quantity("1개월분", form="") == ""


def test_extract_dose_quantity_still_recognizes_gae_unit_without_month():
    """"개"가 실제 낱개 단위로 쓰이는 경우(월 뒤따르지 않음)는 회귀 없이 그대로 인식돼야 한다."""
    assert extract_dose_quantity("1회 1개, 1일 4회", form="") == "1개"


def test_parse_prescription_month_supply_does_not_produce_fake_dosage():
    """[실사용 재현] "인슐린프리필드시린지 1일 1회 1개월분" → dosage가 "1개"(개월분의 개)나
    "1시린지"(개 제외 후 bare-fallback으로 드러난 약품명 제형)로 잘못 채워지면 안 된다 —
    이 텍스트엔 1회 복용량 정보 자체가 없으므로 빈 값이어야 한다."""
    raw = "1. 인슐린프리필드시린지 1일 1회 1개월분"
    meds, _ = parse_prescription(raw)
    assert len(meds) == 1
    assert meds[0]["dosage"] == ""
