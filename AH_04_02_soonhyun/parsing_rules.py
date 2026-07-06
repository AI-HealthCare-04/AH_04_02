# -*- coding: utf-8 -*-
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

import re

# ─────────────────────────────────────────────────────────────
# 1. 약어 → 한국어 매핑
# ─────────────────────────────────────────────────────────────

FREQ_ABBREV_MAP: dict = {
    "qd":  "1일 1회",
    "od":  "1일 1회",
    "bid": "1일 2회",
    "tid": "1일 3회",
    "qid": "1일 4회",
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

# 약품명: 한글·영문 3자 이상 + 선택적 숫자(오메가3 등) + 선택적 연질 수식어 + 제형
# {3,} 조건으로 '개인정보'→'개인정' 오인식 방지 (2자 이하 불가)
# (?:\d+)? : 브랜드에 숫자 포함된 경우 허용 (오메가3연질캡슐)
# (?:연질)?: '연질캡슐' 복합 제형 허용
DRUG_NAME_RE = re.compile(
    r"([가-힣A-Za-z]{3,}(?:\d+)?(?:연질)?(?:정|캡슐|주|산|시럽|액))"
    r"(\d+(?:\.\d+)?(?:mg|g|ml))?"
    r"(?:\([^)]+\))?",
    re.IGNORECASE,
)

DOSAGE_RE       = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|g|ml)", re.IGNORECASE)
# TODO: 실제 처방전(prescription_01.jpg)에서 "7 회", "1 회" 처럼 숫자와 '회' 사이에
#       공백이 들어간 비표준 표기가 확인됨. Day2 이후 실샘플 10장 기반으로 패턴 보강 필요.
KOR_FREQ_RE     = re.compile(r"(?:1일|하루)\s*(\d+)\s*(?:회|번)")
ABBREV_FREQ_RE  = re.compile(r"\b(qd|od|bid|tid|qid|prn|hs|ac|pc)\b", re.IGNORECASE)
DAYS_KOR_RE     = re.compile(r"(\d+)\s*일\s*분")
DAYS_ABBREV_RE  = re.compile(r"#\s*(\d+)")
# '진단명:' 과 '진단:' 모두 허용 (대학병원 다과 협진 포맷 지원)
# non-greedy: 다음 목록 번호("1. "/"2) "), '[', 줄바꿈, 또는 문자열 끝에서 중단
DIAGNOSIS_KOR_RE  = re.compile(r"진단(?:명)?\s*[:：]\s*([^\[\n]+?)(?=\s+\d+[.)]\s+|[\[\n]|\Z)")
DIAGNOSIS_EN_RE   = re.compile(r"Dx\s*[:：]\s*(.+?)(?=\s+Rx\b|\Z)", re.IGNORECASE)
# 공식 처방전: "질병분류기호:M17 (무릎관절증)" → "무릎관절증"
DIAGNOSIS_CODE_RE = re.compile(r"질병분류기호\s*[:：]\s*\S+\s*[（(]([^)）]+)[)）]")

# ─────────────────────────────────────────────────────────────
# 4. 유틸리티 함수 (공개 API)
# ─────────────────────────────────────────────────────────────

def extract_dosage(text: str) -> str:
    m = DOSAGE_RE.search(text)
    return f"{m.group(1)}{m.group(2)}" if m else ""


def extract_frequency(text: str) -> str:
    """한국어 횟수 우선, 없으면 약어 변환."""
    m = KOR_FREQ_RE.search(text)
    if m:
        return f"1일 {m.group(1)}회"
    m = ABBREV_FREQ_RE.search(text)
    if m:
        return FREQ_ABBREV_MAP.get(m.group(1).lower(), m.group(1))
    return ""


def extract_days(text: str) -> str:
    m = DAYS_KOR_RE.search(text)
    if m:
        return f"{m.group(1)}일"
    m = DAYS_ABBREV_RE.search(text)
    if m:
        return f"{m.group(1)}일"
    return ""


def extract_diagnosis(text: str) -> str:
    # 다과 협진 처방전(대학병원)은 '진단:' 이 여러 번 등장할 수 있음 → findall
    matches = DIAGNOSIS_KOR_RE.findall(text)
    if matches:
        parts = [m.strip().rstrip(",/ ") for m in matches if m.strip()]
        # 중복 제거(순서 유지)
        seen: set = set()
        deduped = [p for p in parts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
        return ", ".join(deduped)
    m = DIAGNOSIS_EN_RE.search(text)
    if m:
        return m.group(1).strip()
    # 공식 처방전: 질병분류기호:M17 (무릎관절증)
    m = DIAGNOSIS_CODE_RE.search(text)
    if m:
        return m.group(1).strip()
    return ""


def lookup_drug_class(drug_name: str) -> str:
    for key, cls in DRUG_CLASS_DICTIONARY.items():
        if key in drug_name:
            return cls
    return ""


# ─────────────────────────────────────────────────────────────
# 5. 포맷 감지
# ─────────────────────────────────────────────────────────────

def _detect_format(text: str) -> str:
    """'official' | 'abbrev' | 'list' | 'table' 반환."""
    if re.search(r"\[(?:급여|비급여)\]\[\d+\]", text):
        return "official"
    if re.search(r"\b(?:bid|qd|tid|qid)\b", text, re.IGNORECASE):
        return "abbrev"
    if re.search(r"\d+[.)]\s+[가-힣A-Za-z]+(?:\d+)?(?:연질)?(?:정|캡슐|시럽|액|주|산)", text):
        return "list"
    return "table"

# ─────────────────────────────────────────────────────────────
# 6. 포맷별 파서
# ─────────────────────────────────────────────────────────────

def _drug_name_only(form_str: str) -> str:
    """'암로디핀정' → '암로디핀', '오메가3연질캡슐' → '오메가3'."""
    result = re.sub(r"(?:연질)?(?:정|캡슐|주|산|시럽|액)$", "", form_str)
    return result if result else form_str


def _split_by_number(text: str) -> list:
    """'1) ...\n2) ...' 또는 '1. ... 2. ...' 형식을 번호 기준으로 분리.
    ICD 코드(F41.1, E11.9)나 소수점(5.2)은 분리하지 않음.
    - (?<![A-Za-z가-힣]) : 알파벳·한글 직후 숫자는 ICD 코드 → 제외
    - (?!\\d)           : 숫자 직후 또 숫자면 소수점 → 제외
    """
    return [s.strip() for s in re.split(r"(?<![A-Za-z가-힣])\d+\s*[).](?!\d)", text) if s.strip()]


def _parse_official_format(text: str) -> list:
    """
    공식 처방전 포맷: [급여/비급여][코드] 약품명 1회량 1일횟수 일수
    - 용법 자유서술형("1일 1회 취침전 복용하세요")은 KOR_FREQ_RE로 흡수
    - "110/500" 같은 복합 용량은 col_nums에서 자동 제외(/ 앞뒤 숫자 필터)

    CLOVA 컬럼 그룹 출력 대응:
    CLOVA가 테이블을 컬럼 단위로 플래튼할 때 약품명 컬럼 전체 → 횟수 컬럼 전체 순으로
    출력하면, 첫 번째·두 번째 약품 세그먼트에는 횟수 텍스트가 없고 마지막 세그먼트에만
    전체 횟수가 몰린다. 이를 대비해 전체 텍스트에서 횟수 목록을 미리 추출해두고
    세그먼트 내에서 찾지 못하면 약품 순서(0-based index)로 배정한다.
    """
    # [급여/비급여][코드] 경계로 분리 → 각 항목이 약품 1줄
    segments = re.split(r"\[(?:급여|비급여)\]\[\d+\]", text)

    # 전체 텍스트에서 "1일 N회" 목록을 순서대로 추출 (컬럼 그룹 출력 대응)
    all_freqs = [f"1일 {n}회" for n in KOR_FREQ_RE.findall(text)]

    results = []
    drug_idx = 0
    for seg in segments:
        seg = seg.strip()
        dm = DRUG_NAME_RE.search(seg)
        if not dm:
            continue
        drug_name = _drug_name_only(dm.group(1))
        dosage = dm.group(2) or extract_dosage(seg)

        # DRUG_NAME_RE 매치 이후 텍스트에서 숫자 컬럼 추출
        # .(소수점) / (분수) 앞뒤 숫자, mg/g/ml 단위 붙은 숫자는 제외
        post = seg[dm.end():]
        col_nums = re.findall(
            r"(?<![./\d])(\d+)(?![./\d]|mg|g|ml)", post
        )

        # 우선순위: ① 세그먼트 내 "1일 N회" → ② 전체 목록 약품 순서 배정
        #           → ③ col_nums[1] 폴백
        freq = extract_frequency(seg)
        if not freq:
            if drug_idx < len(all_freqs):
                freq = all_freqs[drug_idx]
            elif len(col_nums) >= 2:
                freq = f"1일 {col_nums[1]}회"

        days = f"{col_nums[2]}일" if len(col_nums) >= 3 else ""

        results.append({
            "drug_name":  drug_name,
            "dosage":     dosage,
            "frequency":  freq,
            "days":       days,
            "drug_class": lookup_drug_class(drug_name),
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
        drug_name = _drug_name_only(dm.group(1))
        results.append({
            "drug_name":  drug_name,
            "dosage":     dm.group(2) or extract_dosage(item),
            "frequency":  extract_frequency(item),
            "days":       extract_days(item),
            "drug_class": lookup_drug_class(drug_name),
        })
    return results


def _parse_list_format(text: str) -> list:
    """리스트 포맷: 1. 약품명 1회 1정, 1일 1회, 30일분"""
    results = []
    for item in _split_by_number(text):
        dm = DRUG_NAME_RE.search(item)
        if not dm:
            continue
        drug_name = _drug_name_only(dm.group(1))
        results.append({
            "drug_name":  drug_name,
            "dosage":     dm.group(2) or extract_dosage(item),
            "frequency":  extract_frequency(item),
            "days":       extract_days(item),
            "drug_class": lookup_drug_class(drug_name),
        })
    return results


def _parse_table_format(text: str) -> list:
    """
    테이블 포맷: OCR이 컬럼을 그룹으로 출력.
    약품명 그룹 → 1회량 그룹 → 횟수 그룹 → 일수 그룹 순서를 가정.
    """
    drug_matches = list(DRUG_NAME_RE.finditer(text))
    if not drug_matches:
        return []

    # 모든 한국어 횟수 순서대로 추출
    freq_nums = KOR_FREQ_RE.findall(text)
    frequencies = [f"1일 {n}회" for n in freq_nums]

    # 마지막 횟수 패턴 이후 영역에서 단독 정수를 일수로 추출
    last_freq_end = 0
    for m in re.finditer(r"(?:1일|하루)\s*\d+\s*(?:회|번)", text):
        last_freq_end = m.end()
    tail = text[last_freq_end:]
    diag_m = re.search(r"진단명", tail)
    if diag_m:
        tail = tail[:diag_m.start()]
    # 소수점·단위에 붙지 않은 단독 정수만 추출
    day_nums = re.findall(r"(?<![.\d])(\d+)(?![.\d]|mg|g|ml|일|분)", tail)

    results = []
    for i, dm in enumerate(drug_matches):
        drug_name = _drug_name_only(dm.group(1))
        results.append({
            "drug_name":  drug_name,
            "dosage":     dm.group(2) or "",
            "frequency":  frequencies[i] if i < len(frequencies) else "",
            "days":       f"{day_nums[i]}일" if i < len(day_nums) else "",
            "drug_class": lookup_drug_class(drug_name),
        })
    return results


# ─────────────────────────────────────────────────────────────
# 7. 공개 메인 API
# ─────────────────────────────────────────────────────────────

def parse_prescription(raw_text: str) -> tuple:
    """
    raw_text → (약품 목록, 진단명)
    각 약품 dict: drug_name / dosage / frequency / days / drug_class
    """
    fmt = _detect_format(raw_text)
    if fmt == "official":
        meds = _parse_official_format(raw_text)
    elif fmt == "abbrev":
        meds = _parse_abbrev_format(raw_text)
    elif fmt == "list":
        meds = _parse_list_format(raw_text)
    else:
        meds = _parse_table_format(raw_text)
    return meds, extract_diagnosis(raw_text)


# 하위 호환: 단일 라인 파싱
def parse_line(line: str) -> dict:
    return {
        "dosage":    extract_dosage(line),
        "frequency": extract_frequency(line),
    }


if __name__ == "__main__":
    import json

    samples = [
        (
            "테이블",
            "처방전 환자 성명: 홍길동 (개인정보 목업) 질병분류기호: 110 (본태성 고혈압) "
            "의약품명 1회 투약량 1일 투여횟수 총 투약일수 "
            "암로디핀정5mg(한미) 로자탄칼륨정50mg(종근당) 메트포르민정500mg(대웅) "
            "1.00 1.00 2.00 1일 1회 1일 2회 1일 1회 30 30 30 "
            "진단명: 고혈압, 제2형 당뇨병",
        ),
        (
            "리스트",
            "00약국 환자: 김철수 (개인정보 목업) 조제일자: 2026-07-01 "
            "1. 아스피린프로텍트정100mg 1회 1정, 1일 1회, 30일분 복용 "
            "2. 심바스타틴정20mg(유한양행) 1회 1정, 1일 1회 (취침전), 30일분 "
            "3. 오메프라졸캡슐20mg 1회 1캡슐, 1일 1회 (식전), 30일분 "
            "진단명: 관상동맥질환, 위염",
        ),
        (
            "약어",
            "처방전 (약식) Pt: 이영희(모) Dx: 골관절염, 불면증 "
            "Rx) 1) 세레브렉스캡슐200mg 1C bid #14 "
            "2) 졸피뎀정10mg 1T qd(취침전) #7 "
            "3) 파모티딘정20mg 1T bid #14",
        ),
    ]

    samples.append((
        "공식",
        "[조제기관] 00약국 [처방기관] 00의원 질병분류기호:M17 (무릎관절증) "
        "[급여][649500560] 세레콕시브캡슐200mg 1 2 7 "
        "[급여][642201540] 에페리손염산염정50mg 1 3 7 "
        "[급여][644308830] 라베프라졸나트륨장용정 1 1 7 1일 1회 취침전 복용하세요 "
        "[급여][658101480] 조인트콘드로이친캡슐 110/500 1 1 1 "
        "[비급여][643501070] 파스(온습포) 1 2 7",
    ))

    for label, text in samples:
        meds, diag = parse_prescription(text)
        print(f"\n{'=' * 40}")
        print(f"[{label}] 진단명: {diag}")
        print(json.dumps(meds, ensure_ascii=False, indent=2))
