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

DRUG_NAME_RE = re.compile(
    # (?<![가-힣\d]): 한글·숫자 바로 뒤 부분 매칭 방지 (예: '이지엔6프로연질캡슐'에서 '프로'만 잡히는 것 차단)
    # (?:\d+(?!연질)[가-힣A-Za-z]{2,})?: 숫자 삽입 복합 약품명 처리 (예: '이지엔6프로')
    #   — '연질' 앞 lookahead로 '오메가3연질캡슐'에서 3이 연질을 삼키는 것을 방지
    r"(?<![가-힣\d])([가-힣A-Za-z]{2,}(?:\d+(?!연질)[가-힣A-Za-z]{2,})?(?:\d+)?(?:연질)?(?:정|캡슐|주|산|시럽|액|크림|연고|로션|겔|패취)"
    r"|(?-i:[A-Z][a-zA-Z]{4,})(?=\s+\d))"  # 영문 PascalCase 5자+, 바로 뒤에 숫자(용량/횟수) 필수
    r"(\d+(?:\.\d+)?(?:mg|g|ml|%))?"
    r"(?:\([^)]+\))?",
    re.IGNORECASE,
)

DOSAGE_RE       = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|g|ml|%)", re.IGNORECASE)
KOR_FREQ_RE     = re.compile(r"(?:1\s*일|하루)\s*(\d+)\s*(?:회|번)")  # 1 일 3 회 같은 비표준 공백 허용
BARE_FREQ_RE    = re.compile(r"(?<!\d)(\d+)\s*회(?!\s*[가-힣\)])")
ABBREV_FREQ_RE  = re.compile(r"\b(qd|od|bid|tid|qid|prn|hs|ac|pc)\b", re.IGNORECASE)
DAYS_KOR_RE     = re.compile(r"(\d+)\s*일\s*분")
DAYS_ABBREV_RE  = re.compile(r"#\s*(\d+)")
DIAGNOSIS_KOR_RE  = re.compile(r"진단(?:명)?\s*[:：]\s*([^\[\n■]+?)(?=\s+\d+[.)]\s+|[\[\n■]|\Z)")
DRUG_CODE_RE      = re.compile(r"\[(?:급여|비급여)\]\[(\w+)\]")
DIAGNOSIS_EN_RE   = re.compile(r"Dx\s*[:：]\s*(.+?)(?=\s+Rx\b|\Z)", re.IGNORECASE)
DIAGNOSIS_CODE_RE = re.compile(r"질병분류기호\s*[:：]\s*\S+\s*[（(]([^)）]+)[)）]")

# ─────────────────────────────────────────────────────────────
# 4. 유틸리티 함수 (공개 API)
# ─────────────────────────────────────────────────────────────

def extract_dosage(text: str) -> str:
    m = DOSAGE_RE.search(text)
    return f"{m.group(1)}{m.group(2)}" if m else ""


def extract_frequency(text: str) -> str:
    """한국어 횟수 우선, 없으면 약어, 없으면 단독 N회 패턴."""
    m = KOR_FREQ_RE.search(text)
    if m:
        return f"1일 {m.group(1)}회"
    m = ABBREV_FREQ_RE.search(text)
    if m:
        return FREQ_ABBREV_MAP.get(m.group(1).lower(), m.group(1))
    m = BARE_FREQ_RE.search(text)
    if m:
        return f"1일 {m.group(1)}회"
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
    matches = DIAGNOSIS_KOR_RE.findall(text)
    if matches:
        parts = [m.strip().rstrip(",/ ") for m in matches if m.strip()]
        seen: set = set()
        deduped = [p for p in parts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
        return ", ".join(deduped)
    m = DIAGNOSIS_EN_RE.search(text)
    if m:
        return m.group(1).strip()
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
    if re.search(r"\[(?:급여|비급여)\]\[\w+\]", text):
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
    """'암로디핀정' → '암로디핀', '오메가3연질캡슐' → '오메가3', '데스오웬크림' → '데스오웬'."""
    result = re.sub(r"(?:연질)?(?:정|캡슐|주|산|시럽|액|크림|연고|로션|겔|패취)$", "", form_str)
    return result if result else form_str


def _split_by_number(text: str) -> list:
    """'1) ...\n2) ...' 또는 '1. ... 2. ...' 형식을 번호 기준으로 분리."""
    return [s.strip() for s in re.split(r"(?<![A-Za-z가-힣])\d+\s*[).](?!\d)", text) if s.strip()]


def _parse_official_format(text: str) -> list:
    """공식 처방전 포맷: [급여/비급여][코드] 약품명 1회량 1일횟수 일수"""
    segments = re.split(r"\[(?:급여|비급여)\]\[\w+\]", text)

    all_freqs = [f"1일 {n}회" for n in KOR_FREQ_RE.findall(text)]
    all_codes = extract_drug_code_list(text)

    results = []
    drug_idx = 0
    for seg in segments:
        seg = seg.strip()
        dm = DRUG_NAME_RE.search(seg)
        if not dm:
            continue
        drug_name = _drug_name_only(dm.group(1))
        dosage = dm.group(2) or extract_dosage(seg)

        post_raw = seg[dm.end():]
        post = post_raw.split("■")[0]
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
                    freq = f"1일 {col_nums[1]}회"
                elif len(col_nums) >= 1 and 0 < int(col_nums[0]) <= 6:
                    freq = f"1일 {col_nums[0]}회"
                elif drug_idx < len(all_freqs):
                    freq = all_freqs[drug_idx]

        days = f"{col_nums[2]}일" if len(col_nums) >= 3 else ""
        drug_code = all_codes[drug_idx] if drug_idx < len(all_codes) else ""

        results.append({
            "drug_name":  drug_name,
            "drug_code":  drug_code,
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
            "drug_code":  "",
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
            "drug_code":  "",
            "dosage":     dm.group(2) or extract_dosage(item),
            "frequency":  extract_frequency(item),
            "days":       extract_days(item),
            "drug_class": lookup_drug_class(drug_name),
        })
    return results


def _parse_table_format(text: str) -> list:
    """테이블 포맷: OCR이 컬럼을 그룹으로 출력."""
    drug_matches = list(DRUG_NAME_RE.finditer(text))
    if not drug_matches:
        return []

    freq_nums = KOR_FREQ_RE.findall(text)
    frequencies = [f"1일 {n}회" for n in freq_nums]

    last_freq_end = 0
    for m in re.finditer(r"(?:1\s*일|하루)\s*\d+\s*(?:회|번)", text):
        last_freq_end = m.end()
    tail = text[last_freq_end:]
    diag_m = re.search(r"진단명", tail)
    if diag_m:
        tail = tail[:diag_m.start()]
    day_nums = re.findall(r"(?<![.\d])(\d+)(?![.\d]|mg|g|ml|일|분)", tail)

    results = []
    for i, dm in enumerate(drug_matches):
        drug_name = _drug_name_only(dm.group(1))
        results.append({
            "drug_name":  drug_name,
            "drug_code":  "",
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
    """raw_text → (약품 목록, 진단명)"""
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


def parse_line(line: str) -> dict:
    return {
        "dosage":    extract_dosage(line),
        "frequency": extract_frequency(line),
    }
