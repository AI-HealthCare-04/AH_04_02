"""
처방전 raw_text 파싱 규칙

네 가지 처방전 포맷을 커버한다:
  1. 공식 포맷    : [급여/비급여][코드] 약품명 1회량 1일횟수 일수
  2. 테이블 포맷  : OCR이 약품명·용량·횟수·일수를 컬럼 그룹으로 출력
  3. 리스트 포맷  : 번호. 약품명 1회 N정, 1일 N회, N일분
  4. 약식(약어) 포맷: Dx: / Rx) / bid / qd / #N

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[진단 기록] 정규식 한계 — 약봉투 테이블 포맷 (2026-07-03 확인)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
mock_pharmacy_bag_format.png 같이 "약품명/성분 | 복약안내 | 투약량 | 횟수 | 일수"
컬럼이 순수 숫자(1 2 30)로만 구성된 약봉투 테이블 포맷은 정규식으로 해결 불가.

근거:
  1) DRUG_NAME_RE 오인식: 성분명(메트포르민염산염, 암로디핀베실산염)이
     제형 패턴(-산)에 걸려 브랜드명과 구분되지 않음 → 5개 매칭, 실제 약품 3개
  2) KOR_FREQ_RE 미검출: 복약안내가 "아침 식후 복용하세요" 형태이면
     "1일 N회" 표현이 없어 횟수 추출 불가
  3) 숫자 컬럼 행 소속 불명: CLOVA가 테이블을 flat string으로 병합하면
     "1 2 30 / 1 1 30 / 1 1 30"이 어느 약품 행인지 위치 정보가 소실됨

해결 방법 (Day2 이후 구현):
  CLOVA OCR 응답의 fields[].boundingPoly.vertices (x, y 좌표)를 활용해
  텍스트 필드를 y좌표 기준으로 행(row)으로 그룹핑한 뒤 컬럼 헤더 x범위로
  투약량·횟수·일수를 각 약품에 1:1 매핑하는 표 구조 파싱 레이어 필요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import csv
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 1. 약어 → 한국어 매핑
# ─────────────────────────────────────────────────────────────

FREQ_ABBREV_MAP: dict = {
    "qd":  "1회",
    "od":  "1회",
    "bid": "2회",
    "tid": "3회",
    "qid": "4회",
    "prn": "필요시",
    "hs":  "취침 전",
    "ac":  "식전",
    "pc":  "식후",
}

# ─────────────────────────────────────────────────────────────
# 2. 약효 분류 사전 (TODO: Day2 이후 실샘플 기반으로 계속 보강)
# ─────────────────────────────────────────────────────────────

DRUG_CLASS_DICTIONARY: dict = {
    "아스피린":   "항혈소판제",
    "로자탄":     "ARB(안지오텐신수용체차단제)",
    "메트포르민": "당뇨병용제(비구아니드)",
    "암로디핀":   "칼슘채널차단제",
    "심바스타틴": "HMG-CoA환원효소억제제(스타틴)",
    "오메프라졸": "양성자펌프억제제(PPI)",
    "세레브렉스": "COX-2선택적억제제(NSAIDs)",
    "졸피뎀":     "수면유도제(비벤조디아제핀계)",
    "파모티딘":   "H2수용체차단제",
}

# ─────────────────────────────────────────────────────────────
# 3. 정규식 상수
# ─────────────────────────────────────────────────────────────

DRUG_NAME_RE = re.compile(
    # (?<![가-힣\d]): 한글·숫자 바로 뒤 부분 매칭 방지 (예: '이지엔6프로연질캡슐'에서 '프로'만 잡히는 것 차단)
    # (?:\d+(?!연질)[가-힣A-Za-z]{2,})?: 숫자 삽입 복합 약품명 처리 (예: '이지엔6프로')
    #   — '연질' 앞 lookahead로 '오메가3연질캡슐'에서 3이 연질을 삼키는 것을 방지
    # [2026-07-27 버그수정] 정제/캡슐 위주로만 목록이 자라 있어 패치("패취"만 인식되고
    # 훨씬 흔한 표기인 "패치"는 누락)/점안액·점이액(안약/귀약)/환(알약)이 처방전에 있으면
    # 이 매칭 자체가 실패해 그 약이 통째로 인식 결과에서 사라졌다 — drug_matcher._DOSAGE_RE가
    # 이미 커버하던 제형 목록과 맞춰 추가한다.
    r"(?<![가-힣\d])([가-힣A-Za-z]{2,}(?:\d+(?!연질)[가-힣A-Za-z]{2,})?(?:\d+)?(?:연질)?(?:정|캡슐|주|산|시럽|액|크림|연고|로션|겔|패취|패치|점안|점이|환)"
    r"|(?-i:[A-Z][a-zA-Z]{4,})(?=\s+\d))"  # 영문 PascalCase 5자+, 바로 뒤에 숫자(용량/횟수) 필수
    # [2026-07-18] "정 5mg"처럼 띄어쓴 용량도 이름에 붙게 허용
    # [2026-07-19] "50/1000mg"같은 복합제 용량(성분 두 개를 슬래시로 묶고 단위는 한 번만
    # 표기)도 통째로 붙게 허용
    r"\s?(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?(?:mg|g|ml|%))?"
    r"(?:\([^)]+\))?",
    re.IGNORECASE,
)

# [2026-07-19] "50/1000mg"(복합제, 예: 글리메피리드/메트포르민)처럼 슬래시로 묶인 두 성분
# 용량도 하나로 인식 — 뒷 숫자에 붙은 단위 하나만 mg/g/ml/%로 보고, 앞 숫자는 그대로 살린다.
DOSAGE_RE       = re.compile(r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*(mg|g|ml|%)", re.IGNORECASE)

# [2026-07-23 추가] "1회 복용량"(환자가 한 번에 몇 개/단위를 먹는지 — 예: "1정", "0.5정",
# "2캡슐")은 DOSAGE_RE가 잡는 mg/g/ml/%(주성분 함량, 약품명에 붙어 나옴)와 다른 정보다.
# 실제 처방전엔 보통 (1) "1회 1정"처럼 텍스트로 풀어 쓰거나, (2) "1T"/"1C" 같은 약식
# 표기로 나오거나, (3) 공식 표 포맷에서 단위 없이 "1.00"처럼 숫자만 있는 컬럼으로 나온다.
DOSE_QTY_UNITS = "정|캡슐|캅셀|포|병|환"
DOSE_QTY_UNIT_RE   = re.compile(rf"(\d+(?:\.\d+)?)\s*({DOSE_QTY_UNITS})")
DOSE_QTY_ABBREV_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(T|C)\b")  # 1T(정)/1C(캡슐) 약식 표기
# [2026-07-27 추가] 시럽/점안액처럼 개수(정/캡슐 등)가 아니라 부피·방울 수로 1회
# 복용량을 표현하는 제형 — 이 단위들은 약품명의 제형 접미사로 나올 일이 없으므로
# DOSE_QTY_UNITS(DRUG_FORM_RE와 공유)와는 분리해서 관리한다. 이게 없으면 "1방울"의
# "1"이 단위 없는 숫자로 오인되어 (3) 폴백에서 약품명 제형("액" 등)이 엉뚱하게 붙어
# "1액" 같은 말이 안 되는 값이 만들어졌다.
DOSE_QTY_VOLUME_UNITS = "ml|mL|방울"
DOSE_QTY_VOLUME_UNIT_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({DOSE_QTY_VOLUME_UNITS})", re.IGNORECASE)
# 약품명(DRUG_NAME_RE group 1)이 실제로 끝나는 제형 — (3) 케이스에서 단위 없는 숫자 컬럼에
# 이 제형을 붙여 "1.00" + "정" → "1정"을 완성한다.
DRUG_FORM_RE = re.compile(rf"({DOSE_QTY_UNITS}|주|산|시럽|액|크림|연고|로션|겔|패취|패치|점안|점이)$")
# 단위 없는 순수 숫자 컬럼용 — 날짜/시각(-,:,.) 및 mg류/일/회/분/시/초 단위에 이미 붙은
# 숫자는 제외한다(그런 숫자는 함량·횟수·일수지 복용량이 아니다).
_BARE_QTY_RE = re.compile(
    r"(?<![./\d:-])(\d+(?:\.\d+)?)(?!\s*(?:mg|g|ml|%|일|회|분|시|초)|[./\d:-])"
)
KOR_FREQ_RE     = re.compile(r"(?:1\s*일|하루)\s*(\d+)\s*(?:회|번)")  # 1 일 3 회 같은 비표준 공백 허용
BARE_FREQ_RE    = re.compile(r"(?<!\d)(\d+)\s*회(?!\s*[가-힣\)])")
ABBREV_FREQ_RE  = re.compile(r"\b(qd|od|bid|tid|qid|prn|hs|ac|pc)\b", re.IGNORECASE)
DAYS_KOR_RE     = re.compile(r"(\d+)\s*일\s*분")
DAYS_ABBREV_RE  = re.compile(r"#\s*(\d+)")
# [2026-07-20 버그수정] CLOVA가 표(연락처/발행일/처방 내역 등)를 개행 없이 한 줄로 합쳐
# 내보내면, 원래 있던 정지 조건(숫자+".)"+공백, "[\n■", 문자열 끝)이 전혀 안 걸려서
# "진단: 제2형 당뇨병" 뒤의 연락처·처방 목록·주의문구까지 전부 diagnosis로 삼켜버렸다
# (실제 재현: 300자 넘는 문자열이 ocr_results.diagnosis VARCHAR(255)를 초과해 저장 자체가
# 실패함). 실제 처방전에 진단명 바로 뒤에 자주 오는 필드 라벨(연락처/발행일/처방/조제)도
# 정지 조건에 추가했다 — 그래도 못 거른 경우를 대비해 extract_diagnosis()에서 길이도 자른다.
DIAGNOSIS_KOR_RE  = re.compile(
    r"진단(?:명)?\s*[:：]\s*([^\[\n■]+?)"
    r"(?=\s+\d+[.)]\s+|[\[\n■]|\s*(?:연락처|발행일|처방|조제)|\Z)"
)
_MAX_DIAGNOSIS_LEN = 100  # ocr_results.diagnosis VARCHAR(255)보다 여유 있게 짧게 — 실제 진단명은 이보다 훨씬 짧다
DRUG_CODE_RE      = re.compile(r"\[(?:급여|비급여)\]\[(\w+)\]")
DIAGNOSIS_EN_RE   = re.compile(r"Dx\s*[:：]\s*(.+?)(?=\s+Rx\b|\Z)", re.IGNORECASE)
DIAGNOSIS_CODE_RE = re.compile(r"질병분류기호\s*[:：]\s*\S+\s*[（(]([^)）]+)[)）]")
# [2026-07-23 추가] 같은 처방인지 판단할 근거로 "처방번호"는 6개 mock 포맷 중 1개에만
# 등장해 신뢰도가 낮다(별도로 팀원이 조사 중) — 대신 "조제일자/처방일자/진료일자/조제일"은
# 6개 포맷 전부에 있고 "YYYY-MM-DD"/"YYYY.MM.DD" 두 형식만 확인됐다.
PRESCRIPTION_DATE_RE = re.compile(
    r"(?:조제일자|처방일자|진료일자|조제일)\s*[:：]?\s*(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})"
)

# ── 한방 첩약 포맷 전용 ──────────────────────────────────────────
# "당귀 8g", "천궁(川芎) 4g" 형태: 한글 약재명(2~6자) + 선택 한자괄호 + 중량g
_HERB_ITEM_RE    = re.compile(r"([가-힣]{2,6})(?:\([^\)]*\))?\s+(\d+(?:\.\d+)?)g\b", re.IGNORECASE)
_HERB_DETECT_RE  = re.compile(r"[가-힣]{2,6}(?:\([^\)]*\))?\s+\d+(?:\.\d+)?g\b", re.IGNORECASE)
_ORIENTAL_FREQ_RE = re.compile(r"(?:1일|하루)\s*(\d+)\s*(?:첩|회|번)")
_ORIENTAL_DAYS_RE = re.compile(r"(\d+)\s*첩")

# ─────────────────────────────────────────────────────────────
# 4. 유틸리티 함수 (공개 API)
# ─────────────────────────────────────────────────────────────

def extract_dosage(text: str) -> str:
    m = DOSAGE_RE.search(text)
    if not m:
        return ""
    # "50 / 1000mg"처럼 슬래시 앞뒤에 공백이 있어도 "50/1000mg"로 통일해서 저장한다.
    return f"{m.group(1).replace(' ', '')}{m.group(2)}"


def extract_dose_quantity(text: str, form: str = "") -> str:
    """1회 복용량 — "1정", "0.5정", "2캡슐"처럼 환자가 한 번에 먹는 개수/단위.

    1) "1회 1정"/"1정"처럼 텍스트에 단위가 그대로 있으면 그걸 쓴다.
    2) "10ml"/"1방울"처럼 부피·방울 단위(시럽/점안액 등)가 있으면 그걸 쓴다.
    3) "1T"/"1C" 같은 약식 표기(T=정, C=캡슐)를 본다.
    4) 그래도 없으면 단위 없이 숫자만 있는 컬럼(예: "1.00")을 찾아, 약품명의 제형(form,
       예: "정"/"캡슐")을 붙여 완성한다 — form이 없으면 조합할 수 없어 빈 문자열을 반환한다.
    """
    m = DOSE_QTY_UNIT_RE.search(text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = DOSE_QTY_VOLUME_UNIT_RE.search(text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = DOSE_QTY_ABBREV_RE.search(text)
    if m:
        unit = "정" if m.group(2).upper() == "T" else "캡슐"
        return f"{m.group(1)}{unit}"
    if form:
        m = _BARE_QTY_RE.search(text)
        if m:
            qty = m.group(1)
            if "." in qty and float(qty) == int(float(qty)):
                qty = str(int(float(qty)))  # "1.00" → "1" (소수부가 전부 0이면 정수로)
            return f"{qty}{form}"
    return ""


def _dm_dosage(dm: "re.Match") -> str:
    """DRUG_NAME_RE 매치의 트레일링 용량 그룹(group 2)을 "50/1000mg"처럼 공백 없이 반환.
    그룹이 없으면(용량이 이름에 안 붙어 나온 경우) 빈 문자열."""
    if not dm.group(2):
        return ""
    return dm.group(2).replace(" ", "")


# [2026-07-25 추가] "1회 투여량"(mg/ml 등 질량·부피 단위) — "1회 사용량"(정/캡슐 등
# 개수 단위)과 별개 필드. 처방전 문구에 따로 적혀 있으면(예: "1회 10mg 경구 투여") 그걸
# 쓰고, 없으면 약품명에 붙어 나오는 단위당 함량(예: "암로핀정5밀리그람"의 5mg)을 그대로
# 쓴다 — 대부분의 정제 처방전은 후자뿐이라, 이 폴백이 없으면 이 필드가 거의 항상
# 비어 있게 된다.
def extract_dose_amount(post_text: str, dm_dosage: str = "") -> str:
    return extract_dosage(post_text) or dm_dosage


# [2026-07-25 추가] 1회 사용량(dosage)과 1회 투여량(dose_amount)의 인식 결과를 조합한다.
# reconcile_dose_fields 자체는 "사용량이 비었을 때 채우는" 역할만 한다 — dose_amount는
# 이미 파싱 단계에서 결정된 값을 그대로 받는다.
#
#   사용량 O                    → 그대로 둔다(투여량 유무 무관, 이미 충분).
#   사용량 X, 투여량 O          → 약품명에 포함된 단위당 함량으로 나눠서 개수를 역산한다.
#                                  단위가 다르거나(mg vs ml), 복합제(성분 2개)거나, 약품명에서
#                                  함량을 못 찾으면 억지로 지어내지 않고 빈 문자열로 남긴다.
#   사용량 X, 투여량 X          → 빈 문자열(호출부가 review_required로 잡아냄).
def reconcile_dose_fields(dosage: str, dose_amount: str, drug_name: str) -> str:
    if dosage or not dose_amount:
        return dosage

    amount_m = DOSAGE_RE.fullmatch(dose_amount.strip())
    strength_m = DOSAGE_RE.search(drug_name)
    if not amount_m or not strength_m:
        return ""
    # drug_name은 "약품명(제형으로 끝) + ' ' + 함량(mg 등)" 구조라(_dm_dosage 조합 규칙),
    # 제형은 함량이 시작되기 직전 부분에서 찾아야 한다 — 함량이 붙으면 제형이 더 이상
    # 문자열 끝(DRUG_FORM_RE의 $ 앵커)이 아니게 되기 때문.
    form_m = DRUG_FORM_RE.search(drug_name[:strength_m.start()].rstrip())
    if not form_m:
        return ""
    # 복합제(예: "50/1000mg", 성분 2개)는 단순 나눗셈으로 개수를 정할 수 없다.
    if "/" in amount_m.group(1) or "/" in strength_m.group(1):
        return ""
    if amount_m.group(2).lower() != strength_m.group(2).lower():
        return ""  # mg vs ml처럼 단위가 다르면 나눌 수 없음

    try:
        strength_value = float(strength_m.group(1))
        if strength_value == 0:
            return ""
        qty = float(amount_m.group(1)) / strength_value
    except ValueError:
        return ""

    qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}".rstrip("0").rstrip(".")
    return f"{qty_str}{form_m.group(1)}"


def extract_frequency(text: str) -> str:
    """한국어 횟수 우선, 없으면 약어, 없으면 식사타이밍, 없으면 단독 N회 패턴.

    [2026-07-18] "1일" 접두어는 뺀다 — 프론트 라벨이 "1일 투약횟수"라 값에서
    또 반복하면 "1일 1일 1회"처럼 겹쳐 보인다. 값은 "1회"/"2회"만 담는다.

    [2026-07-18] 식전/식후(MEAL_RE) 폴백은 제거했다 — "1일 투약횟수"는 하루에 몇 번
    먹는지(횟수)를 묻는 필드인데, 식전/식후는 언제 먹는지(타이밍)라 전혀 다른 정보다.
    명시적인 횟수를 못 찾았으면 "식후"를 억지로 끼워맞추지 말고 빈 값으로 남겨서
    사용자가 직접 채우게 한다(모르는 걸 아는 척 지어내지 않음).
    """
    m = KOR_FREQ_RE.search(text)
    if m:
        return f"{m.group(1)}회"
    m = ABBREV_FREQ_RE.search(text)
    if m:
        mapped = FREQ_ABBREV_MAP.get(m.group(1).lower(), m.group(1))
        # prn/hs/ac/pc는 횟수가 아니라 타이밍/조건이라("필요시"/"취침 전"/"식전"/"식후")
        # 위와 같은 이유로 여기서도 걸러낸다 — 진짜 횟수(qd/od/bid/tid/qid)만 반환.
        if mapped.endswith("회"):
            return mapped
        return ""
    m = BARE_FREQ_RE.search(text)
    if m:
        return f"{m.group(1)}회"
    return ""


def extract_drug_code_list(text: str) -> list:
    """공식 처방전의 [급여/비급여][코드] 패턴을 순서대로 추출해 리스트로 반환."""
    return DRUG_CODE_RE.findall(text)


def extract_days(text: str) -> str:
    m = DAYS_KOR_RE.search(text)
    if m:
        return f"{m.group(1)}일"
    m = DAYS_ABBREV_RE.search(text)
    if m:
        return f"{m.group(1)}일"
    return ""


def extract_diagnosis(text: str) -> str:
    if matches := DIAGNOSIS_KOR_RE.findall(text):
        parts = [m.strip().rstrip(",/ ") for m in matches if m.strip()]
        seen: set = set()
        deduped = [p for p in parts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
        result = ", ".join(deduped)
    elif m := DIAGNOSIS_EN_RE.search(text):
        result = m.group(1).strip()
    elif m := DIAGNOSIS_CODE_RE.search(text):
        result = m.group(1).strip()
    else:
        result = ""
    # [2026-07-20] 정지 조건을 다 못 거른 텍스트가 와도(예: 예상 못 한 OCR 포맷) DB
    # 컬럼(ocr_results.diagnosis VARCHAR(255)) 저장 자체가 실패하지 않도록 방어적으로 자른다.
    return result[:_MAX_DIAGNOSIS_LEN]


def extract_prescription_date(text: str) -> str:
    """조제일자/처방일자/진료일자/조제일 → "YYYY-MM-DD". 못 찾으면 빈 문자열
    (날짜를 모르면 그냥 모르는 대로 두고, 이름만으로 비교하던 기존 중복판정 방식으로 폴백한다)."""
    m = PRESCRIPTION_DATE_RE.search(text)
    if not m:
        return ""
    year, month, day = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def lookup_drug_class(drug_name: str) -> str:
    for key, cls in DRUG_CLASS_DICTIONARY.items():
        if key in drug_name:
            return cls
    return ""


# ── 한방 첩약 보조 함수 ──────────────────────────────────────────

_herb_name_set: set | None = None


def _load_herb_names() -> set[str]:
    """herb_reference.csv의 herb_name 컬럼을 set으로 지연 로드."""
    global _herb_name_set
    if _herb_name_set is not None:
        return _herb_name_set
    try:
        csv_path = Path(__file__).parent.parent / "herb_reference.csv"
        names: set[str] = set()
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get("herb_name", "").strip()
                if name:
                    names.add(name)
        _herb_name_set = names
    except Exception:
        _herb_name_set = set()
    return _herb_name_set


def _is_oriental_format(text: str) -> bool:
    """'약재명 Ng' 패턴이 2개 이상이면 한방 첩약 처방전으로 판정."""
    return len(_HERB_DETECT_RE.findall(text)) >= 2


def _extract_oriental_frequency(text: str) -> str:
    m = _ORIENTAL_FREQ_RE.search(text)
    if m:
        unit = "첩" if "첩" in m.group(0) else "회"
        return f"{m.group(1)}{unit}"
    return extract_frequency(text)


def _extract_oriental_days(text: str) -> str:
    # frequency 패턴("1일 N첩/회")을 먼저 소비한 나머지에서 days를 탐색.
    # 이렇게 하지 않으면 "1일 2첩 … 20첩"에서 2첩이 days로 잘못 잡힌다.
    freq_m = _ORIENTAL_FREQ_RE.search(text)
    search_text = text[freq_m.end():] if freq_m else text
    m = _ORIENTAL_DAYS_RE.search(search_text)
    if m:
        return f"{m.group(1)}첩"
    return extract_days(text)


# ─────────────────────────────────────────────────────────────
# 5. 포맷 감지
# ─────────────────────────────────────────────────────────────

def _detect_format(text: str) -> str:
    """'oriental' | 'official' | 'abbrev' | 'list' | 'table' 반환."""
    if _is_oriental_format(text):
        return "oriental"
    if re.search(r"\[(?:급여|비급여)\]\[\w+\]", text):
        return "official"
    if re.search(r"\b(?:bid|qd|tid|qid)\b", text, re.IGNORECASE):
        return "abbrev"
    # [2026-07-27 버그수정] DRUG_NAME_RE가 이미 커버하는 제형 목록보다 좁아서, 크림/연고/
    # 로션/겔/패치류 처방전이 리스트 포맷인데도 (더 약한 파싱을 쓰는) table로 빠졌다 —
    # DRUG_NAME_RE와 동일한 제형 목록으로 맞춘다.
    if re.search(r"\d+[.)]\s+[가-힣A-Za-z]+(?:\d+)?(?:연질)?(?:정|캡슐|시럽|액|주|산|크림|연고|로션|겔|패취|패치|점안|점이|환)", text):
        return "list"
    return "table"

# ─────────────────────────────────────────────────────────────
# 6. 포맷별 파서
# ─────────────────────────────────────────────────────────────

def _split_by_number(text: str) -> list:
    """'1) ...\n2) ...' 또는 '1. ... 2. ...' 형식을 번호 기준으로 분리."""
    return [s.strip() for s in re.split(r"(?<![A-Za-z가-힣])\d+\s*[).](?!\d)", text) if s.strip()]


def _parse_official_format(text: str) -> list:
    """공식 처방전 포맷: [급여/비급여][코드] 약품명 1회량 1일횟수 일수"""
    segments = re.split(r"\[(?:급여|비급여)\]\[\w+\]", text)

    all_freqs = [f"{n}회" for n in KOR_FREQ_RE.findall(text)]
    all_codes = extract_drug_code_list(text)

    results = []
    drug_idx = 0
    for seg in segments:
        seg = seg.strip()
        dm = DRUG_NAME_RE.search(seg)
        if not dm:
            continue
        # [2026-07-18] 약품명에 제형(정/캡슐 등)과 용량을 그대로 남긴다 — "암로디핀"이
        # 아니라 "암로디핀정 5mg"까지가 그 약을 특정하는 실제 이름이라, e약은요·HIRA
        # 매칭에도 이쪽이 더 정확하다.
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")

        post_raw = seg[dm.end():]
        post = post_raw.split("■")[0]
        # [2026-07-23 수정] dosage는 이제 "1회 복용량"(예: "1정") — 약품명의 제형을
        # 이 약의 단위로 보고, post(약품명 뒤 텍스트, 여기 "1회 투약량" 컬럼 값이 있다)에서
        # 수량을 찾는다. mg 등 성분 함량(_dm_dosage/extract_dosage)은 더 이상 dosage로
        # 쓰지 않는다 — 그건 이미 drug_name에 그대로 남아있다.
        form_m = DRUG_FORM_RE.search(dm.group(1))
        dosage = extract_dose_quantity(post, form_m.group(1) if form_m else "")
        dose_amount = extract_dose_amount(post, _dm_dosage(dm))
        # 날짜(2026-07-09)·시각(10:00) 앞뒤 숫자를 col_nums에서 제외하기 위해
        # 기존 패턴에 '-' ':' 추가
        col_nums = re.findall(
            r"(?<![./\d:-])(\d+)(?![./\d:-]|mg|g|ml|분|시|초)", post
        )

        seg_clean = seg.split("■")[0]

        # [중단]/[중지] 약물은 복약 횟수 없음
        if re.search(r"\[중단\]|\[중지\]", seg):
            freq = ""
        else:
            freq = extract_frequency(seg_clean)
            if not freq:
                # ① col_nums[1] 우선 (1일 최대 6회 기준 — 초과 시 일수로 판단)
                # ② col_nums[1]이 일수로 추정되면 col_nums[0] 시도
                # ③ 숫자 컬럼 없거나 모두 범위 초과 시 all_freqs 폴백
                #    (CLOVA 컬럼 그룹 출력: 약품명 전체→횟수 전체 순으로 출력되는 경우)
                if len(col_nums) >= 2 and 0 < int(col_nums[1]) <= 6:
                    freq = f"{col_nums[1]}회"
                elif len(col_nums) >= 1 and 0 < int(col_nums[0]) <= 6:
                    freq = f"{col_nums[0]}회"
                elif drug_idx < len(all_freqs):
                    freq = all_freqs[drug_idx]

        days = f"{col_nums[2]}일" if len(col_nums) >= 3 else ""
        drug_code = all_codes[drug_idx] if drug_idx < len(all_codes) else ""

        results.append({
            "drug_name":   drug_name,
            "drug_code":   drug_code,
            "dosage":      dosage,
            "dose_amount": dose_amount,
            "frequency":   freq,
            "total_days":  days,
            "drug_class":  lookup_drug_class(drug_name),
        })
        drug_idx += 1
    return results


def _parse_abbrev_format(text: str) -> list:
    """약식(약어) 포맷: Rx) 1) 약품명 1T bid #14"""
    rx_m = re.search(r"Rx\s*[)]", text, re.IGNORECASE)
    body = text[rx_m.end():] if rx_m else text

    results = []
    for item in _split_by_number(body):
        dm = DRUG_NAME_RE.search(item)
        if not dm:
            continue
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")
        form_m = DRUG_FORM_RE.search(dm.group(1))
        post = item[dm.end():]
        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      extract_dose_quantity(post, form_m.group(1) if form_m else ""),
            "dose_amount": extract_dose_amount(post, _dm_dosage(dm)),
            "frequency":   extract_frequency(item),
            "total_days":  extract_days(item),
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


def _parse_list_format(text: str) -> list:
    """리스트 포맷: 1. 약품명 1회 1정, 1일 1회, 30일분"""
    results = []
    for item in _split_by_number(text):
        dm = DRUG_NAME_RE.search(item)
        if not dm:
            continue
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")
        form_m = DRUG_FORM_RE.search(dm.group(1))
        post = item[dm.end():]
        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      extract_dose_quantity(post, form_m.group(1) if form_m else ""),
            "dose_amount": extract_dose_amount(post, _dm_dosage(dm)),
            "frequency":   extract_frequency(item),
            "total_days":  extract_days(item),
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


def _parse_oriental_format(text: str) -> list:
    """한방 첩약 처방전: '약재명 Ng' 반복 패턴.

    herb_reference.csv 로드 후 herb_name 컬럼으로 검증.
    CSV에 없는 약재명도 포함하되 drug_class를 '한방 첩약(미확인)'으로 표시.
    """
    herb_names = _load_herb_names()
    freq = _extract_oriental_frequency(text)
    days = _extract_oriental_days(text)

    results = []
    for m in _HERB_ITEM_RE.finditer(text):
        name = m.group(1).strip()
        weight = m.group(2)
        in_ref = name in herb_names
        results.append({
            "drug_name":   name,
            "drug_code":   "",
            "dosage":      f"{weight}g",
            "dose_amount": "",
            "frequency":   freq,
            "total_days":  days,
            "drug_class":  "한방 첩약" if in_ref else "한방 첩약(미확인)",
        })
    return results


def _parse_table_format(text: str) -> list:
    """테이블 포맷: OCR이 컬럼을 그룹으로 출력."""
    drug_matches = list(DRUG_NAME_RE.finditer(text))
    if not drug_matches:
        return []

    # KOR_FREQ_RE("1일 N회")와 BARE_FREQ_RE(독립 "N회") 모두 수집, 중복 없이 위치 순 정렬.
    # KOR 매치 구간을 consumed로 표시해 BARE가 같은 숫자를 다시 소비하지 않도록 한다.
    kor_spans: list[tuple[int, int]] = []
    freq_entries: list[tuple[int, int, str]] = []  # (start, end, freq_str)
    for m in re.finditer(r"(?:1\s*일|하루)\s*(\d+)\s*(?:회|번)", text):
        freq_entries.append((m.start(), m.end(), f"{m.group(1)}회"))
        kor_spans.append((m.start(), m.end()))
    for m in BARE_FREQ_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in kor_spans):
            freq_entries.append((m.start(), m.end(), f"{m.group(1)}회"))
    freq_entries.sort()
    frequencies = [freq for _, _, freq in freq_entries]

    # 마지막 freq 매치 이후 텍스트에서만 일수를 탐색 (freq 숫자를 일수로 오인하지 않도록)
    last_freq_end = max((end for _, end, _ in freq_entries), default=0)
    tail = text[last_freq_end:]
    diag_m = re.search(r"진단명", tail)
    if diag_m:
        tail = tail[:diag_m.start()]
    day_nums = re.findall(r"(?<![.\d])(\d+)(?![.\d]|mg|g|ml|일|분)", tail)

    # [2026-07-23 추가] "1회 복용량"(예: "1정", "1T") — 단위가 붙은 수량 표기만 위치 순으로
    # 모아 약품 순서에 매핑한다. 단위 없는 숫자 컬럼(공식 포맷의 "1.00" 같은)은 이 포맷에서는
    # 어느 약의 것인지 위치 정보가 약해 신뢰도가 낮으므로 시도하지 않는다.
    qty_entries: list[tuple[int, str]] = []
    for m in DOSE_QTY_UNIT_RE.finditer(text):
        qty_entries.append((m.start(), f"{m.group(1)}{m.group(2)}"))
    for m in DOSE_QTY_ABBREV_RE.finditer(text):
        qty_entries.append((m.start(), f"{m.group(1)}{'정' if m.group(2).upper() == 'T' else '캡슐'}"))
    # [2026-07-27 추가] 시럽/점안액처럼 부피·방울 단위로 복용량을 쓰는 제형도 다른 단위와
    # 동일하게 위치 순으로 모은다 — 이게 없으면 정/캡슐 처방과 섞인 테이블에서 시럽/점안액
    # 항목의 복용량만 항상 빈 값이 된다.
    for m in DOSE_QTY_VOLUME_UNIT_RE.finditer(text):
        qty_entries.append((m.start(), f"{m.group(1)}{m.group(2)}"))
    qty_entries.sort()
    dose_quantities = [qty for _, qty in qty_entries]

    results = []
    for i, dm in enumerate(drug_matches):
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")
        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      dose_quantities[i] if i < len(dose_quantities) else "",
            # [2026-07-25 추가] 테이블 포맷은 컬럼 그룹 출력이라 사용량처럼 위치 기반으로
            # 신뢰도 있게 "1회 투여량" 문구를 찾기 어렵다 — 약품명에 붙어 나오는 단위당
            # 함량(_dm_dosage)만 폴백으로 쓴다.
            "dose_amount": _dm_dosage(dm),
            "frequency":   frequencies[i] if i < len(frequencies) else "",
            "total_days":  f"{day_nums[i]}일" if i < len(day_nums) else "",
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


# ─────────────────────────────────────────────────────────────
# 7. 공개 메인 API
# ─────────────────────────────────────────────────────────────

def parse_prescription(raw_text: str) -> tuple:
    """raw_text → (약품 목록, 진단명)"""
    fmt = _detect_format(raw_text)
    if fmt == "oriental":
        meds = _parse_oriental_format(raw_text)
    elif fmt == "official":
        meds = _parse_official_format(raw_text)
    elif fmt == "abbrev":
        meds = _parse_abbrev_format(raw_text)
    elif fmt == "list":
        meds = _parse_list_format(raw_text)
    else:
        meds = _parse_table_format(raw_text)
    for m in meds:
        m["dosage"] = reconcile_dose_fields(m["dosage"], m.get("dose_amount", ""), m["drug_name"])
    return meds, extract_diagnosis(raw_text)


def parse_line(line: str) -> dict:
    return {
        "dosage":    extract_dosage(line),
        "frequency": extract_frequency(line),
    }
