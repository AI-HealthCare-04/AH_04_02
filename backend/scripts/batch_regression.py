#!/usr/bin/env python3
"""
24개 목업 이미지 배치 회귀 테스트 — parsing_rules.py 직접 호출 방식

이 스크립트는 파싱 로직(parsing_rules.py)을 검증합니다.
MockOCRProvider의 이미지 인식 자체를 검증하려면 별도 테스트가 필요합니다.

각 mock 이미지에 대응하는 대표 raw_text를 parse_prescription()에 직접 입력해
실제 포맷 분기(_detect_format)와 파싱 결과(약품명·용량·횟수·drug_class 등)를 검증합니다.
"""
import sys
from pathlib import Path

BACKEND = Path("/Users/admin/backend")
sys.path.insert(0, str(BACKEND))

from services.drug_reference import get_drug_class
from services.parsing_rules import _detect_format, parse_prescription


# parse_prescription()이 반환하는 drug_class는 parsing_rules.DRUG_CLASS_DICTIONARY(9종)
# 기반의 lookup_drug_class()만 사용한다.
# 실제 파이프라인(ocr_interface._build_medications)은 이 값이 비어 있으면
# drug_reference.get_drug_class()(HIRA + ATC 패턴 + 폴백 전체 체인)로 보완한다.
# 아래 일부 check 람다는 이 동작을 반영해 get_drug_class()를 직접 호출한다.
def _dc(med: dict) -> str:
    """parsed drug_class가 비면 get_drug_class()로 보완 — ocr_interface와 동일 로직."""
    return med.get("drug_class") or get_drug_class(med["drug_name"], "")

# ─────────────────────────────────────────────────────────────────────
# 테스트 케이스 정의
# image       : samples/ 기준 파일명 (추적용 레이블)
# raw_text    : 해당 이미지의 OCR 대표 출력 텍스트
# expect_fmt  : 기대 포맷
# min_drugs   : 최소 기대 약품 수
# checks      : [(설명, lambda meds, diag: bool)] — 추가 검증 조건
# notes       : 알려진 한계 또는 특이사항
# ─────────────────────────────────────────────────────────────────────

CASES = [
    # ── TABLE 포맷 ────────────────────────────────────────────────
    {
        "image": "prescription_01.jpg",
        "raw_text": (
            "케이캡정50mg 7 회 30일분\n"
            "엑세그란정500mg\n"
            "가스모틴정5mg 3 회 30일분\n"
            "마도파정\n"
            "뉴로메드정800mg\n"
            "프라닥사캡슐110mg\n"
            "메바로친정20mg"
        ),
        "expect_fmt": "table",
        "min_drugs": 5,
        "checks": [
            ("케이캡 약품명 포함", lambda m, _: any("케이캡" in x["drug_name"] for x in m)),
            # BARE_FREQ_RE 동작 확인: '7 회' → 케이캡(index 0)에 '1일 7회' 배분
            # 가스모틴(index 2)은 글로벌 freq 배분 한계로 빈값 — 알려진 table 포맷 제약
            ("BARE_FREQ_RE 동작(케이캡 1일 7회)", lambda m, _: any("케이캡" in x["drug_name"] and x["frequency"] == "7회" for x in m)),
        ],
        "notes": "비표준 '7 회' 공백 — BARE_FREQ_RE 경로, 가스모틴 freq 빈값은 table 글로벌 배분 한계",
    },
    {
        "image": "mock_prescription_table.png",
        "raw_text": (
            "진단명: 고혈압, 제2형 당뇨병\n"
            "암로디핀정5mg 1일 1회 30일분\n"
            "로자탄칼륨정50mg 1일 2회 30일분\n"
            "메트포르민정500mg 1일 1회 30일분"
        ),
        "expect_fmt": "table",
        "min_drugs": 3,
        "checks": [
            ("암로디핀 drug_class", lambda m, _: any("암로디핀" in x["drug_name"] and "칼슘채널차단제" in x.get("drug_class","") for x in m)),
            ("진단명 추출", lambda _, d: "고혈압" in d),
        ],
        "notes": "",
    },
    {
        "image": "mock_prescription_table_tilt_blur.jpg",
        "raw_text": (
            "진단명: 고혈압, 제2형 당뇨병\n"
            "암로디핀정5mg 1일 1회 30일분\n"
            "로자탄칼륨정50mg 1일 2회 30일분\n"
            "메트포르민정500mg 1일 1회 30일분"
        ),
        "expect_fmt": "table",
        "min_drugs": 3,
        "checks": [
            ("로자탄칼륨 freq", lambda m, _: any("로자탄칼륨" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
        ],
        "notes": "기울어진/흐린 이미지 — raw_text는 정상 CLOVA 출력 가정",
    },
    {
        "image": "mock_pharmacy_bag_format.png",
        "raw_text": (
            "글루코파지정500mg 1일 2회 30일분\n"
            "메트포르민염산염정500mg\n"
            "노바스크정5mg 1일 1회 30일분\n"
            "암로디핀베실산염정5mg\n"
            "리피토정10mg 1일 1회 30일분"
        ),
        "expect_fmt": "table",
        "min_drugs": 3,
        "checks": [
            ("글루코파지 drug_class(get_drug_class 체인)", lambda m, _: any("글루코파지" in x["drug_name"] and "비구아니드" in _dc(x) for x in m)),
        ],
        "notes": "성분명(메트포르민염산염·암로디핀베실산염) DRUG_NAME_RE 오인식 알려진 한계",
    },
    {
        "image": "mock_stamp_overlap.png",
        "raw_text": (
            "암로디핀정5mg 1일 1회 30일분\n"
            "로자탄정50mg 1일 1회 30일분\n"
            "메트포르민정500mg 1일 2회 30일분"
        ),
        "expect_fmt": "table",
        "min_drugs": 3,
        "checks": [
            ("메트포르민 freq 1일 2회", lambda m, _: any("메트포르민" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
        ],
        "notes": "스탬프 겹침 노이즈는 이미지 레이어 — raw_text 파싱에는 영향 없음",
    },
    # ── LIST 포맷 ─────────────────────────────────────────────────
    {
        "image": "mock_prescription_bag.png",
        "raw_text": (
            "진단명: 관상동맥질환, 위염\n"
            "1. 아스피린프로텍트장용정100mg 1회 1정, 1일 1회, 30일분\n"
            "2. 심바스타틴정20mg 1회 1정, 1일 1회, 30일분\n"
            "3. 오메프라졸캡슐20mg 1회 1캡슐, 1일 1회, 30일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 3,
        "checks": [
            ("아스피린 drug_class 항혈소판제", lambda m, _: any("아스피린" in x["drug_name"] and "항혈소판제" in x.get("drug_class","") for x in m)),
            ("심바스타틴 스타틴", lambda m, _: any("심바스타틴" in x["drug_name"] and "스타틴" in x.get("drug_class","") for x in m)),
        ],
        "notes": "",
    },
    {
        "image": "mock_dental_bag.png",
        "raw_text": (
            "1) 아모클란정375mg 1회 1정, 1일 3회, 5일분\n"
            "2) 이지엔6프로연질캡슐 1회 1캡슐, 1일 3회, 5일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 2,
        "checks": [
            ("아모클란 freq 1일 3회", lambda m, _: any("아모클란" in x["drug_name"] and x["frequency"] == "3회" for x in m)),
        ],
        "notes": "이지엔6프로 drug_class 빈값 알려진 한계(ATC 미등재)",
    },
    {
        "image": "mock_ophthalmology.png",
        "raw_text": (
            "1. 플록사신점안액0.3% 1회 2방울, 1일 4회, 7일분\n"
            "2. 히알루론산나트륨점안액1% 1회 1방울, 1일 4회, 7일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 2,
        "checks": [
            ("플록사신 dosage 0.3%", lambda m, _: any("플록사신" in x["drug_name"] and x["dosage"] == "0.3%" for x in m)),
            ("히알루론산 dosage 1%", lambda m, _: any("히알루론산" in x["drug_name"] and x["dosage"] == "1%" for x in m)),
        ],
        "notes": "점안액 % 용량 파싱 검증",
    },
    {
        "image": "mock_pediatric.png",
        "raw_text": (
            "진단명: 급성 중이염\n"
            "1. 오구멘틴시럽 5mL 1일 2회, 7일분\n"
            "2. 지르텍시럽 2.5mL 1일 1회, 7일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 2,
        "checks": [
            ("지르텍 drug_class 항히스타민제(get_drug_class 체인)", lambda m, _: any("지르텍" in x["drug_name"] and "항히스타민제" in _dc(x) for x in m)),
            ("진단명 중이염", lambda _, d: "중이염" in d),
        ],
        "notes": "시럽·mL 포맷 파싱 (list 감지 정규식에 시럽|액 추가로 수정됨)",
    },
    {
        "image": "mock_psychiatry.png",
        "raw_text": (
            "진단명: F41.1 범불안장애\n"
            "1. 자낙스정0.25mg 1회 1정, 1일 2회, 30일분\n"
            "2. 렉사프로정10mg 1회 1정, 1일 1회, 30일분\n"
            "3. 스틸녹스정10mg 1회 1정, 1일 1회, 30일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 3,
        "checks": [
            ("자낙스 freq 1일 2회", lambda m, _: any("자낙스" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
            ("진단명 F41.1", lambda _, d: "F41.1" in d or "범불안" in d),
        ],
        "notes": "F41.1 코드 오분할 수정됨(_split_by_number lookbehind)",
    },
    {
        "image": "mock_dermatology.png",
        "raw_text": (
            "1. 데스오웬크림0.05% 1일 2회, 7일분\n"
            "2. 베타메타손연고0.1% 1일 2회, 7일분\n"
            "3. 세티리진정10mg 1일 1회, 30일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 3,
        "checks": [
            ("데스오웬크림 인식", lambda m, _: any("데스오웬" in x["drug_name"] for x in m)),
            ("베타메타손연고 인식", lambda m, _: any("베타메타손" in x["drug_name"] for x in m)),
        ],
        "notes": "크림/연고 제형 DRUG_NAME_RE 파싱 검증",
    },
    {
        "image": "mock_er.png",
        "raw_text": (
            "1. 아스피린장용정100mg 1회 1정, 1일 1회, 7일분\n"
            "2. 오메프라졸캡슐20mg 1회 1캡슐, 1일 1회, 7일분\n"
            "3. 이부프로펜정400mg 1회 1정, 1일 3회, 3일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 3,
        "checks": [
            ("이부프로펜 drug_class NSAIDs(get_drug_class 체인)", lambda m, _: any("이부프로펜" in x["drug_name"] and "NSAIDs" in _dc(x) for x in m)),
        ],
        "notes": "",
    },
    {
        "image": "mock_obgyn.png",
        "raw_text": (
            "1. 엽산정0.4mg 1회 1정, 1일 1회, 90일분\n"
            "2. 오메가3연질캡슐 1회 1캡슐, 1일 1회, 90일분\n"
            "3. 칼슘정500mg 1회 1정, 1일 1회, 90일분"
        ),
        "expect_fmt": "list",
        "min_drugs": 3,
        "checks": [
            ("오메가3 연질캡슐 인식", lambda m, _: any("오메가" in x["drug_name"] for x in m)),
        ],
        "notes": "오메가3연질캡슐 — (?:\\d+)?(?:연질)? 패턴 수정됨",
    },
    # ── OFFICIAL 포맷 ─────────────────────────────────────────────
    {
        "image": "mock_nursing_hospital.png",
        "raw_text": (
            "[급여][A001] 아스피린프로텍트장용정100mg 1정 1일 1회 30일분\n"
            "[급여][B002] 메트포르민정500mg 1정 1일 2회 30일분\n"
            "[급여][C003] 암로디핀정5mg 1정 1일 1회 30일분\n"
            "[급여][D004] 심바스타틴정20mg 1정 1일 1회 30일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 4,
        "checks": [
            ("아스피린프로텍트 항혈소판제", lambda m, _: any("아스피린" in x["drug_name"] and "항혈소판제" in x.get("drug_class","") for x in m)),
        ],
        "notes": "",
    },
    {
        "image": "mock_discharge.png",
        "raw_text": (
            "진단명: 허혈성심질환, 제2형 당뇨병\n"
            "[급여][A001] 아스피린프로텍트장용정100mg 1정 1일 1회 90일분\n"
            "[급여][B002] 메트포르민정500mg 2정 1일 2회 90일분\n"
            "[급여][C003] 암로디핀정5mg 1정 1일 1회 90일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 3,
        "checks": [
            ("메트포르민 freq 1일 2회", lambda m, _: any("메트포르민" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
            ("진단명 당뇨병", lambda _, d: "당뇨병" in d),
        ],
        "notes": "퇴원 처방전 — official 포맷 일수 90일",
    },
    {
        "image": "mock_substitution_checkbox.png",
        "raw_text": (
            "[급여][A001] 암로디핀정5mg 1정 1일 1회 30일분\n"
            "[급여][B002] 메트포르민정500mg 2정 1일 2회 30일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 2,
        "checks": [
            ("암로디핀 drug_code 추출", lambda m, _: any("암로디핀" in x["drug_name"] and x.get("drug_code") for x in m)),
        ],
        "notes": "대체조제 체크박스는 파싱 결과에 영향 없음",
    },
    {
        "image": "mock_followup_change.png",
        "raw_text": (
            "진단명: 고혈압, 위염\n"
            "[급여][A001] 암로디핀정5mg 1정 1일 1회 30일분\n"
            "[급여][B002] [중단] 로자탄정50mg 1일 1회 30일분\n"
            "[급여][C003] 오메프라졸캡슐20mg 1캡슐 1일 1회 30일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 3,
        "checks": [
            ("중단 약물 freq 빈값", lambda m, _: any("로자탄" in x["drug_name"] and x["frequency"] == "" for x in m)),
        ],
        "notes": "[중단] 마킹 약물은 frequency 빈값 처리 확인",
    },
    {
        "image": "mock_university_hospital.png",
        "raw_text": (
            "진단명: 제2형 당뇨병, 이상지질혈증, 본태성 고혈압, 심방세동\n"
            "[급여][A011] 자누메트정1000mg 1정 1일 2회 30일분\n"
            "[급여][B022] 아토젯정40mg 1정 1일 1회 30일분\n"
            "[급여][C033] 엘리퀴스정5mg 1정 1일 2회 30일분\n"
            "[급여][D044] 오메가3연질캡슐 1캡슐 1일 1회 30일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 4,
        "checks": [
            ("아토젯 스타틴(get_drug_class 체인)", lambda m, _: any("아토젯" in x["drug_name"] and "스타틴" in _dc(x) for x in m)),
            ("복수 진단명", lambda _, d: "당뇨병" in d and "고혈압" in d),
        ],
        "notes": "자누메트 drug_class 빈값(복합제 미등재) 알려진 한계",
    },
    {
        "image": "mock_prescription_official.png",
        "raw_text": (
            "질병분류기호：M17(무릎관절증)\n"
            "[급여][A001234] 세레콕시브캡슐200mg 1캡슐 1일 2회 7일분\n"
            "[급여][B005678] 에페리손염산염정50mg 1정 1일 3회 7일분\n"
            "[급여][C009999] 라베프라졸나트륨장용정10mg 1캡슐 1일 1회 7일분\n"
            "[급여][D001111] 조인트콘드로이친산나트륨캡슐 1캡슐 1일 1회 1일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 4,
        "checks": [
            ("세레콕시브 freq 1일 2회", lambda m, _: any("세레콕시브" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
            ("에페리손 freq 1일 3회", lambda m, _: any("에페리손" in x["drug_name"] and x["frequency"] == "3회" for x in m)),
            ("진단명 무릎관절증", lambda _, d: "무릎관절증" in d),
        ],
        "notes": "",
    },
    {
        "image": "mock_seoul_clinic_prescription.png",
        "raw_text": (
            "[급여][A1001] 아목시실린캡슐500mg 1캡슐 1일 3회 7일분\n"
            "[급여][B1002] 이부프로펜정400mg\n"
            "[급여][C1003] 오메프라졸캡슐20mg 2회 7일분\n"
            "[급여][D1004] 덱사메타손정0.5mg 1회 1일 7일분"
        ),
        "expect_fmt": "official",
        "min_drugs": 4,
        "checks": [
            ("아목시실린 freq 1일 3회", lambda m, _: any("아목시실린" in x["drug_name"] and x["frequency"] == "3회" for x in m)),
            ("오메프라졸 freq 추출(BARE_FREQ)", lambda m, _: any("오메프라졸" in x["drug_name"] and x["frequency"] for x in m)),
        ],
        "notes": "Day5 수정: BARE_FREQ_RE·seg_clean 확장으로 오메프라졸·덱사메타손 freq 복원",
    },
    # ── ABBREV 포맷 ───────────────────────────────────────────────
    {
        "image": "mock_prescription_abbrev.png",
        "raw_text": (
            "Dx: 골관절염, 불면증\n"
            "Rx)\n"
            "1) 세레브렉스캡슐200mg 1T bid #14\n"
            "2) 졸피뎀정10mg 1T qd #7\n"
            "3) 파모티딘정20mg 1T bid #14"
        ),
        "expect_fmt": "abbrev",
        "min_drugs": 3,
        "checks": [
            ("세레브렉스 bid→1일 2회", lambda m, _: any("세레브렉스" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
            ("졸피뎀 qd→1일 1회", lambda m, _: any("졸피뎀" in x["drug_name"] and x["frequency"] == "1회" for x in m)),
            ("진단명 골관절염", lambda _, d: "골관절염" in d),
        ],
        "notes": "",
    },
    {
        "image": "mock_english_mixed.png",
        "raw_text": (
            "Dx: Hypertension, Dyslipidemia\n"
            "Rx)\n"
            "1) Amlodipine정5mg 1T qd #30\n"
            "2) 메트포르민정500mg 2T bid #30\n"
            "3) Rosuvastatin정10mg 1T qd #30"
        ),
        "expect_fmt": "abbrev",
        "min_drugs": 2,
        "checks": [
            ("메트포르민 bid→1일 2회", lambda m, _: any("메트포르민" in x["drug_name"] and x["frequency"] == "2회" for x in m)),
        ],
        "notes": "영문 PascalCase 약품명은 5자+ 매칭(Amlodipine ✓, Rosuvastatin ✓)",
    },
    # ── ORIENTAL 포맷 ─────────────────────────────────────────────
    {
        "image": "mock_oriental_prescription.png",
        "raw_text": (
            "당귀(當歸) 8g 천궁(川芎) 4g 작약(芍藥) 4g 숙지황(熟地黃) 8g "
            "황기(黃芪) 6g 백출(白朮) 4g 백복령(白茯苓) 4g 감초(甘草) 2g "
            "계피(桂皮) 2g 생강(生薑) 4g 대추(大棗) 4g 인삼(人蔘) 4g "
            "1일 2첩 식후 30분 복용 20첩"
        ),
        "expect_fmt": "oriental",
        "min_drugs": 12,
        "checks": [
            ("12약재 전량", lambda m, _: len(m) == 12),
            ("days 20첩", lambda m, _: m[0]["total_days"] == "20첩" if m else False),
            ("drug_class 한방 첩약", lambda m, _: all("한방 첩약" in x.get("drug_class","") for x in m)),
        ],
        "notes": "72cf011 수정: freq 소비 후 days 탐색으로 days=20첩 정상 파싱",
    },
    {
        "image": "mock_oriental_medicine.png",
        "raw_text": "십전대보탕 인삼 백출 백복령 감초 당귀 천궁 백작약 숙지황 황기 육계 1일 2회",
        "expect_fmt": "table",  # 약재명 Ng 패턴 없음 → oriental 미감지 → table 폴백
        "min_drugs": 0,
        "checks": [
            ("oriental 미감지(Ng 패턴 없음)", lambda m, _: True),  # 0개여도 정상
        ],
        "notes": "중량(Ng) 없는 한약 처방 → oriental 미감지, medications 0개 예상. 별도 처리 미구현",
    },
]

# ─────────────────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────────────────

PASS = "✓"
FAIL = "✗"
anomalies = []
total_checks = 0
passed_checks = 0

W = 125
print("=" * W)
print(f"{'이미지':<40} {'기대포맷':<10} {'실제포맷':<10} {'약품수':>5}  {'포맷':^4}  {'검증':^6}  비고")
print("=" * W)

for c in CASES:
    raw_text     = c["raw_text"]
    expect_fmt   = c["expect_fmt"]
    image        = c["image"]
    min_drugs    = c["min_drugs"]
    notes        = c["notes"]

    detected = _detect_format(raw_text)
    meds, diag = parse_prescription(raw_text)

    fmt_ok   = detected == expect_fmt
    cnt_ok   = len(meds) >= min_drugs

    check_results = []
    for desc, fn in c.get("checks", []):
        total_checks += 1
        try:
            ok = fn(meds, diag)
        except Exception:
            ok = False
        check_results.append((desc, ok))
        if ok:
            passed_checks += 1

    all_checks_ok = all(ok for _, ok in check_results)
    row_ok = fmt_ok and cnt_ok and all_checks_ok

    fmt_mark   = PASS if fmt_ok   else FAIL
    check_mark = PASS if all_checks_ok else FAIL

    print(f"  {image:<38} {expect_fmt:<10} {detected:<10} {len(meds):>5}  {fmt_mark:^4}  {check_mark:^6}  {notes[:42]}")

    if not fmt_ok:
        anomalies.append((image, f"포맷불일치: 기대={expect_fmt} 실제={detected}"))
        print(f"    {'':40} ✗ 포맷 기대={expect_fmt} 실제={detected}")
    if not cnt_ok:
        anomalies.append((image, f"약품수 부족: 기대≥{min_drugs} 실제={len(meds)}"))
        print(f"    {'':40} ✗ 약품수 기대≥{min_drugs} 실제={len(meds)}개")
    for desc, ok in check_results:
        if not ok:
            anomalies.append((image, f"검증실패: {desc}"))
            print(f"    {'':40} ✗ {desc}")

print("=" * W)
print()
print(f"총 {len(CASES)}개 이미지 / 검증 조건 {total_checks}건 통과 {passed_checks}건")
print(f"포맷 불일치·조건 실패: {len(anomalies)}건")
if anomalies:
    print()
    print("[anomaly 목록]")
    for img, msg in anomalies:
        print(f"  ✗ {img} — {msg}")
else:
    print("  → anomaly 없음 ✓")

print()
print("─" * 60)
print("NOTE: 이 스크립트는 parsing_rules.py 파싱 로직을 검증합니다.")
print("      MockOCRProvider의 이미지 인식 자체를 검증하려면 별도 테스트가 필요합니다.")
print("─" * 60)
