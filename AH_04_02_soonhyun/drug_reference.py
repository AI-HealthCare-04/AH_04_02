# -*- coding: utf-8 -*-
"""
drug_reference.py — HIRA 약가마스터 + e약은요 DB + ATC 패턴 기반 약효 분류 모듈

데이터 출처:
  - data/hira_drug_master_20251031.csv : 건강보험심사평가원 약가마스터 (30.5만 건, CP949)
  - data/2_e약은요_정리.xlsx           : 4,809개 일반의약품 itemName / efcyQesitm
  - data/DB_출처_sanitized.xlsx        : ATC 코드 매핑 참고

매칭 우선순위:
  1. HIRA 약가마스터 — 품목기준코드 exact 매칭 (처방전 코드 있을 때)
  2. HIRA 약가마스터 — 한글상품명 부분일치 매칭 → ATC코드 → drug_class
  3. e약은요 DB — 일반의약품(OTC) 부분/유사도 매칭 + efcyQesitm 키워드 분류
  4. ATC 코드 기반 약명 패턴 정규식 (하드코딩, 전문의약품 커버)
  5. 하드코딩 폴백 사전

Note:
  - e약은요 DB는 OTC 중심이라 전문의약품 매칭에는 사용하지 않음.
  - 전문의약품 분류는 HIRA 또는 ATC 패턴이 담당.
  - 2026-07-04 팀원 확인 후 명시.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

_BASE = Path(__file__).parent / "data"

# ──────────────────────────────────────────────────────────────────
# 1. ATC 코드 → 약효 분류 매핑 테이블
#    HIRA 매칭 후 ATC 코드로 drug_class를 결정할 때 사용
#    긴 prefix(5자)부터 짧은 prefix(3자) 순으로 체크
# ──────────────────────────────────────────────────────────────────

_ATC_CLASS_MAP: dict[str, str] = {
    # A — 소화관 및 대사
    "A02BC": "양성자펌프억제제(PPI)",
    "A02BD": "양성자펌프억제제(PPI)",
    "A02BA": "H2수용체차단제",
    "A02":   "위산관련치료제",
    "A03FA": "위장운동촉진제",
    "A03":   "소화기능제",
    "A10BA": "당뇨병용제(비구아니드)",
    "A10BB": "당뇨병용제(설포닐우레아)",
    "A10BD": "당뇨병용제(복합제)",
    "A10BH": "당뇨병용제(DPP-4억제제)",
    "A10BJ": "당뇨병용제(GLP-1수용체작용제)",
    "A10BK": "당뇨병용제(SGLT-2억제제)",
    "A10BX": "당뇨병용제(기타)",
    "A10A":  "인슐린제제",
    "A11":   "비타민제",
    # B — 혈액 및 조혈기관
    "B01AA": "항응고제(쿠마린계)",
    "B01AB": "항응고제(헤파린계)",
    "B01AC": "항혈소판제",
    "B01AE": "항응고제(직접트롬빈억제제)",
    "B01AF": "항응고제(직접Xa인자억제제)",
    "B01":   "항혈전제",
    # C — 심혈관계
    "C03":   "이뇨제",
    "C07":   "베타차단제",
    "C08CA": "칼슘채널차단제(디히드로피리딘계)",
    "C08":   "칼슘채널차단제",
    "C09AA": "ACE억제제",
    "C09CA": "ARB(안지오텐신수용체차단제)",
    "C09DA": "ARB+이뇨제 복합",
    "C09DB": "ARB+칼슘채널차단제 복합",
    "C09":   "레닌-안지오텐신계 약물",
    "C10AA": "HMG-CoA환원효소억제제(스타틴)",
    "C10AB": "피브레이트계",
    "C10AX": "기타지질저하제",
    "C10BA": "스타틴복합제",
    "C10":   "지질저하제",
    "C02":   "항고혈압제",
    # G — 비뇨생식기
    "G04CA": "알파1차단제(전립선비대증)",
    "G04BE": "발기부전치료제",
    # J — 항감염
    "J01":   "항생제",
    "J02":   "항진균제",
    "J05":   "항바이러스제",
    # L — 항암제
    "L01":   "항암제",
    "L02":   "내분비치료제(항암)",
    "L04":   "면역억제제",
    # M — 근골격계
    "M01AH": "COX-2선택적억제제(NSAIDs)",
    "M01AB": "소염진통제(아세트산계)",
    "M01AC": "소염진통제(옥시캄계)",
    "M01AE": "소염진통제(프로피온산계)",
    "M01":   "소염진통제",
    "M03":   "근이완제",
    "M05BA": "비스포스포네이트(골다공증치료제)",
    # N — 신경계
    "N02AA": "오피오이드진통제",
    "N02BA": "해열진통제(살리실산계)",
    "N02BE": "해열진통제(아세트아미노펜)",
    "N02":   "진통제",
    "N03":   "항경련제",
    "N04BA": "파킨슨치료제(레보도파계)",
    "N04":   "파킨슨치료제",
    "N05BA": "항불안제(벤조디아제핀계)",
    "N05CD": "수면유도제(벤조디아제핀계)",
    "N05CF": "수면유도제(비벤조디아제핀계)",
    "N05A":  "항정신병제",
    "N05":   "항정신성약물",
    "N06AB": "SSRI(항우울제)",
    "N06AX": "기타항우울제",
    "N06A":  "항우울제",
    "N06BA": "ADHD치료제",
    "N06BX": "인지기능개선제",
    "N07":   "기타신경계약물",
    # R — 호흡기계
    "R03":   "기관지확장제",
    "R06":   "항히스타민제",
    "R05":   "기침·감기약",
    # S — 감각기관
    "S01":   "안과용제",
    "S02":   "이비인후과용제",
    # V — 기타
    "V03":   "해독제/기타치료제",
}


def _class_from_atc_code(atc_code: str) -> str:
    """ATC 코드 문자열로 drug_class를 반환. 5→4→3자 prefix 순으로 체크."""
    if not atc_code or len(atc_code) < 3:
        return ""
    for length in (5, 4, 3):
        prefix = atc_code[:length]
        if prefix in _ATC_CLASS_MAP:
            return _ATC_CLASS_MAP[prefix]
    return ""


# ──────────────────────────────────────────────────────────────────
# 2. HIRA 약가마스터 로드 (지연 로드)
# ──────────────────────────────────────────────────────────────────

_HIRA_PATH = _BASE / "hira_drug_master_20251031.csv"
_hira_code_map: Optional[dict] = None   # {품목기준코드_str: atc_code}
_hira_name_df = None                    # pandas DataFrame (한글상품명, ATC)


def _load_hira():
    global _hira_code_map, _hira_name_df
    if _hira_code_map is not None:
        return
    try:
        import pandas as pd
        df = pd.read_csv(
            _HIRA_PATH, encoding="cp949",
            usecols=["한글상품명", "품목기준코드", "국제표준코드(ATC코드)"],
            dtype={"품목기준코드": str},
        )
        df = df[df["국제표준코드(ATC코드)"].notna()].copy()
        # 품목기준코드 → ATC 딕셔너리
        _hira_code_map = dict(zip(df["품목기준코드"].str.strip(), df["국제표준코드(ATC코드)"]))
        # 한글상품명 중복 제거 후 DataFrame 보관 (pandas vectorized search용)
        _hira_name_df = (
            df[df["한글상품명"].notna()][["한글상품명", "국제표준코드(ATC코드)"]]
            .drop_duplicates("한글상품명")
            .reset_index(drop=True)
        )
    except Exception:
        _hira_code_map = {}
        _hira_name_df = None


def _lookup_hira_by_code(drug_code: str) -> str:
    """품목기준코드로 ATC 코드 반환."""
    if not drug_code:
        return ""
    _load_hira()
    return _hira_code_map.get(drug_code.strip(), "")


_FORM_STARTERS = set("정캡주산시액이수분과좌크겔연")  # 제형 접두 한 글자


def _lookup_hira_by_name(drug_name: str) -> str:
    """한글상품명에 drug_name이 포함된 HIRA 항목의 ATC 코드 반환.

    우선순위:
      1. drug_name으로 시작 + 바로 뒤 글자가 제형(정/캡/주/산 등) → 단일제, 최단 이름
      2. drug_name으로 시작 (복합제 포함) → 최단 이름
      3. drug_name이 중간에 포함 → 최단 이름
    drug_name이 이름 중간에 삽입된 경우(가바'케이캡', 엘도스'케이캡') 억제.
    """
    if not drug_name or len(drug_name) < 2:
        return ""
    _load_hira()
    if _hira_name_df is None or _hira_name_df.empty:
        return ""

    n = len(drug_name)
    starts_mask = _hira_name_df["한글상품명"].str.startswith(drug_name, na=False)
    starts_hits = _hira_name_df[starts_mask]

    if not starts_hits.empty:
        # 단일제 우선: drug_name 바로 뒤 문자가 제형 접두이거나 숫자인 행
        def _is_direct(name: str) -> bool:
            rest = name[n:] if len(name) > n else ""
            return bool(rest) and (rest[0] in _FORM_STARTERS or rest[0].isdigit())

        direct = starts_hits[starts_hits["한글상품명"].apply(_is_direct)]
        pool = direct if not direct.empty else starts_hits
        idx = pool["한글상품명"].str.len().idxmin()
        return pool.loc[idx, "국제표준코드(ATC코드)"]

    # 중간 포함 매칭 (폴백)
    mask = _hira_name_df["한글상품명"].str.contains(drug_name, regex=False, na=False)
    hits = _hira_name_df[mask]
    if hits.empty:
        return ""
    idx = hits["한글상품명"].str.len().idxmin()
    return hits.loc[idx, "국제표준코드(ATC코드)"]


# ──────────────────────────────────────────────────────────────────
# 3. ATC 약명 패턴 정규식 (폴백용, 기존 유지)
# ──────────────────────────────────────────────────────────────────

_ATC_PATTERNS: list[tuple[str, str]] = [
    (r"메트포르민|글루코파지|다이아벡스|글루코민",                "당뇨병용제(비구아니드)"),
    (r"글리메피리드|아마릴|글리피진|글리클라지드|다이아미크론",    "당뇨병용제(설포닐우레아)"),
    (r"시타글립틴|빌다글립틴|삭사글립틴|자누비아|가브스|온글라이자", "당뇨병용제(DPP-4억제제)"),
    (r"엠파글리플로진|다파글리플로진|카나글리플로진|자디앙|포시가", "당뇨병용제(SGLT-2억제제)"),
    (r"리라글루타이드|세마글루타이드|빅토자|오젬픽",              "당뇨병용제(GLP-1수용체작용제)"),
    (r"인슐린",                                                   "인슐린제제"),
    (r"암로디핀|노바스크|니페디핀|아달라트|딜티아젬|헤르벤|베라파밀", "칼슘채널차단제"),
    (r"로자탄|로사르탄|발사르탄|디오반|이르베사르탄|올메사르탄|텔미사르탄", "ARB(안지오텐신수용체차단제)"),
    (r"에날라프릴|리시노프릴|페린도프릴|라미프릴|캡토프릴",       "ACE억제제"),
    (r"아테놀롤|메토프롤롤|카베딜롤|비소프롤롤|프로프라놀롤",     "베타차단제"),
    (r"히드로클로로티아지드|인다파마이드|클로르탈리돈|푸로세마이드|토라세미드", "이뇨제"),
    (r"아토르바스타틴|리피토|아토젯|로수바스타틴|크레스토|심바스타틴|조코|"
     r"프라바스타틴|플루바스타틴|피타바스타틴|리바로|메바로친",   "HMG-CoA환원효소억제제(스타틴)"),
    (r"에제티미브|이제티미브|로수젯",                             "콜레스테롤흡수억제제"),
    (r"아스피린프로텍트|아스트릭스|아스피린.*장용|클로피도그렐|플라빅스|티카그렐러", "항혈소판제"),
    (r"아스피린(?!.*장용)",                                       "항혈소판제"),
    (r"와파린|리바록사반|자렐토|다비가트란|프라닥사|아픽사반|엘리퀴스", "항응고제"),
    (r"오메프라졸|에소메프라졸|넥시움|판토프라졸|라베프라졸|란소프라졸|케이캡|테고프라잔", "양성자펌프억제제(PPI)"),
    (r"파모티딘|라니티딘|시메티딘|니자티딘",                      "H2수용체차단제"),
    (r"모사프리드|가스모틴|돔페리돈|메토클로프라미드",             "위장운동촉진제"),
    (r"세레콕시브|세레브렉스|에토리콕시브|아르콕시아",            "COX-2선택적억제제(NSAIDs)"),
    (r"이부프로펜|나프록센|디클로페낙|인도메타신|멜록시캄|피록시캄", "비선택적NSAIDs"),
    (r"아세트아미노펜|타이레놀|파라세타몰",                       "해열진통제(아세트아미노펜)"),
    (r"에페리손|바클로펜|시클로벤자프린",                         "근이완제"),
    (r"졸피뎀|트리아졸람|에스조피클론|스틸녹스",                  "수면유도제(비벤조디아제핀계)"),
    (r"디아제팜|알프라졸람|클로나제팜|로라제팜|자낙스",           "벤조디아제핀계"),
    (r"세르트랄린|파록세틴|에스시탈로프람|플루옥세틴|렉사프로",   "SSRI(항우울제)"),
    (r"알렌드론산|리세드론산|포사맥스|악토넬",                    "비스포스포네이트(골다공증치료제)"),
    (r"케토티펜|세티리진|로라타딘|펙소페나딘|지르텍",             "항히스타민제"),
    (r"레보티록신|신지로이드",                                    "갑상선호르몬제"),
]

_COMPILED_ATC: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), cls) for pat, cls in _ATC_PATTERNS
]


def _class_from_atc_pattern(drug_name: str) -> str:
    for pattern, drug_class in _COMPILED_ATC:
        if pattern.search(drug_name):
            return drug_class
    return ""


# ──────────────────────────────────────────────────────────────────
# 4. e약은요 DB 로드 (지연 로드, OTC 중심)
# ──────────────────────────────────────────────────────────────────

_EMED_PATH = _BASE / "2_e약은요_정리.xlsx"
_drug_table: Optional[list[dict]] = None

_STRIP_RE = re.compile(
    r"\d+(?:\.\d+)?(?:mg|g|ml|밀리그램|그램)"
    r"|(?:정|캡슐|주사|주|산|시럽|액|환|겔|크림|연고|패취|패치)\d*(?:\.\d+)?(?:mg|g|ml)?"
    r"|\([^)]+\)",
    re.IGNORECASE,
)
_EFCY_CLASS_RULES: list[tuple[list[str], str]] = [
    (["혈전 생성 억제", "혈소판 응집"],        "항혈소판제"),
    (["콜레스테롤", "중성지방", "고지혈"],      "고지혈증치료제(스타틴)"),
    (["혈당", "당뇨"],                         "당뇨병용제"),
    (["고혈압", "혈압을 낮추", "혈압"],        "항고혈압제"),
    (["불면", "수면"],                         "수면유도제"),
    (["양성자 펌프", "위궤양", "역류성 식도"],  "양성자펌프억제제(PPI)"),
    (["위산과다", "속쓰림", "신트림"],         "H2수용체차단제"),
    (["관절염", "관절 통증"],                  "소염진통제(NSAIDs)"),
    (["두통", "치통", "통증", "해열"],         "해열진통제"),
    (["기관지", "천식", "기침"],               "기관지확장제"),
    (["알레르기", "두드러기", "가려움"],        "항히스타민제"),
    (["세균", "항균"],                         "항생제"),
]


def _normalize_name(name: str) -> str:
    return _STRIP_RE.sub("", name).strip()


def _load_drug_table() -> list[dict]:
    global _drug_table
    if _drug_table is not None:
        return _drug_table
    try:
        import openpyxl
        wb = openpyxl.load_workbook(_EMED_PATH, read_only=True, data_only=True)
        ws = wb["정리데이터"]
        table = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            raw_name = str(row[1]) if row[1] else ""
            efcy = str(row[3]) if row[3] else ""
            if raw_name:
                table.append({"item_name": raw_name, "norm": _normalize_name(raw_name), "efcy": efcy})
        wb.close()
        _drug_table = table
    except Exception:
        _drug_table = []
    return _drug_table


def _class_from_efcy(efcy: str) -> str:
    m = re.search(r"이 약은\s+(.+?)(?:에 사용합니다|에 쓰입니다)", efcy, re.DOTALL)
    indication = m.group(1) if m else efcy
    for keywords, drug_class in _EFCY_CLASS_RULES:
        if any(kw in indication for kw in keywords):
            return drug_class
    return ""


def _lookup_emedinfo(drug_name: str) -> Optional[dict]:
    if len(drug_name) < 3:
        return None
    table = _load_drug_table()
    if not table:
        return None
    candidates = [e for e in table if drug_name in e["norm"] or e["norm"] in drug_name]
    if candidates:
        return min(candidates, key=lambda e: len(e["norm"]))
    best_score, best_entry = 0.0, None
    for entry in table:
        score = SequenceMatcher(None, drug_name, entry["norm"]).ratio()
        if score > best_score:
            best_score, best_entry = score, entry
    if best_score >= 0.72 and best_entry:
        return best_entry
    return None


# ──────────────────────────────────────────────────────────────────
# 5. 하드코딩 폴백
# ──────────────────────────────────────────────────────────────────

_HARDCODED_FALLBACK: dict[str, str] = {
    "세레브렉스":       "COX-2선택적억제제(NSAIDs)",
    "세레콕시브":       "COX-2선택적억제제(NSAIDs)",
    "졸피뎀":           "수면유도제(비벤조디아제핀계)",
    "파모티딘":         "H2수용체차단제",
    "아스피린프로텍트": "항혈소판제",
    "아스피린":         "항혈소판제",
    "심바스타틴":       "HMG-CoA환원효소억제제(스타틴)",
    "오메프라졸":       "양성자펌프억제제(PPI)",
    "암로디핀":         "칼슘채널차단제",
    "로자탄칼륨":       "ARB(안지오텐신수용체차단제)",
    "로자탄":           "ARB(안지오텐신수용체차단제)",
    "메트포르민":       "당뇨병용제(비구아니드)",
    "리피토":           "HMG-CoA환원효소억제제(스타틴)",
    "노바스크":         "칼슘채널차단제",
    "글루코파지":       "당뇨병용제(비구아니드)",
    "에페리손염산":     "근이완제",
    "라베프라졸":       "양성자펌프억제제(PPI)",
}


def _class_from_fallback(drug_name: str) -> str:
    for key, cls in _HARDCODED_FALLBACK.items():
        if key in drug_name or drug_name in key:
            return cls
    return ""


# ──────────────────────────────────────────────────────────────────
# 6. 공개 API
# ──────────────────────────────────────────────────────────────────

def get_drug_class(drug_name: str, drug_code: str = "") -> str:
    """
    우선순위:
      1. HIRA 약가마스터 — 품목기준코드 exact 매칭 → ATC코드 → drug_class
      2. HIRA 약가마스터 — 한글상품명 부분일치 → ATC코드 → drug_class
      3. e약은요 DB — OTC 부분/유사도 매칭 + efcyQesitm 분류
      4. ATC 패턴 정규식 (하드코딩)
      5. 하드코딩 폴백 사전
    """
    # 1. HIRA 코드 매칭
    if drug_code:
        atc = _lookup_hira_by_code(drug_code)
        if atc:
            cls = _class_from_atc_code(atc)
            if cls:
                return cls

    # 2. HIRA 이름 매칭
    atc = _lookup_hira_by_name(drug_name)
    if atc:
        cls = _class_from_atc_code(atc)
        if cls:
            return cls

    # 3. e약은요 DB (OTC)
    entry = _lookup_emedinfo(drug_name)
    if entry:
        cls = _class_from_efcy(entry["efcy"])
        if cls:
            return cls

    # 4. ATC 패턴 정규식
    cls = _class_from_atc_pattern(drug_name)
    if cls:
        return cls

    # 5. 하드코딩 폴백
    return _class_from_fallback(drug_name)


def get_drug_info(drug_name: str, drug_code: str = "") -> dict:
    """상세 정보 반환 (match_source 포함)."""
    # 1. HIRA 코드
    if drug_code:
        atc = _lookup_hira_by_code(drug_code)
        if atc:
            cls = _class_from_atc_code(atc)
            if cls:
                return {"drug_name": drug_name, "drug_class": cls,
                        "match_source": "hira_code", "matched_item": f"코드:{drug_code}", "atc_code": atc}

    # 2. HIRA 이름
    atc = _lookup_hira_by_name(drug_name)
    if atc:
        cls = _class_from_atc_code(atc)
        if cls:
            return {"drug_name": drug_name, "drug_class": cls,
                    "match_source": "hira_name", "matched_item": drug_name, "atc_code": atc}

    # 3. e약은요
    entry = _lookup_emedinfo(drug_name)
    if entry:
        cls = _class_from_efcy(entry["efcy"])
        return {"drug_name": drug_name, "drug_class": cls or _class_from_fallback(drug_name),
                "match_source": "emed", "matched_item": entry["item_name"], "atc_code": ""}

    # 4. ATC 패턴
    cls = _class_from_atc_pattern(drug_name)
    if cls:
        return {"drug_name": drug_name, "drug_class": cls,
                "match_source": "atc_pattern", "matched_item": "", "atc_code": ""}

    # 5. 폴백
    cls = _class_from_fallback(drug_name)
    return {"drug_name": drug_name, "drug_class": cls,
            "match_source": "fallback" if cls else "unknown", "matched_item": "", "atc_code": ""}


# ──────────────────────────────────────────────────────────────────
# 7. 직접 실행 — 샘플 테스트
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # 기존 9개 (mock_prescription_table/bag/abbrev)
        ("암로디핀",         "칼슘채널차단제"),
        ("로자탄칼륨",       "ARB(안지오텐신수용체차단제)"),
        ("메트포르민",       "당뇨병용제(비구아니드)"),
        ("아스피린프로텍트", "항혈소판제"),
        ("심바스타틴",       "HMG-CoA환원효소억제제(스타틴)"),
        ("오메프라졸",       "양성자펌프억제제(PPI)"),
        ("세레브렉스",       "COX-2선택적억제제(NSAIDs)"),
        ("졸피뎀",           "수면유도제(비벤조디아제핀계)"),
        ("파모티딘",         "H2수용체차단제"),
        # prescription_01.jpg (실제 처방전 — HIRA 검증 핵심)
        ("케이캡",           "양성자펌프억제제(PPI)"),
        ("엑세그란",         "항경련제"),
        ("가스모틴",         "위장운동촉진제"),
        ("마도파",           "파킨슨치료제"),
        ("뉴로메드",         "인지기능개선제"),
        ("프라닥사",         "항응고제"),
        ("메바로친",         "HMG-CoA환원효소억제제(스타틴)"),
        # 신규 샘플
        ("자낙스",           "벤조디아제핀계"),
        ("렉사프로",         "SSRI"),
        ("스틸녹스",         "수면유도제"),
        ("지르텍",           "항히스타민제"),
        ("노바스크",         "칼슘채널차단제"),
        ("리피토",           "HMG-CoA환원효소억제제(스타틴)"),
        ("엘리퀴스",         "항응고제"),
    ]

    print(f"{'약품명':<16} {'소스':<12} {'ATC코드':<10} {'결과'}")
    print("─" * 85)
    correct = 0
    for drug_name, expected in test_cases:
        info = get_drug_info(drug_name)
        got = info["drug_class"]
        ok = any(kw in got for kw in expected.split("(")[0].split()) or got == expected
        correct += ok
        mark = "✅" if ok else "❌"
        atc = info.get("atc_code", "")[:7]
        print(f"{mark} {drug_name:<16} {info['match_source']:<12} {atc:<10} {got}")

    print(f"\n정확도: {correct}/{len(test_cases)}")
