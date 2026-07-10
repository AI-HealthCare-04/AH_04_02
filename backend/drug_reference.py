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

⚠️ [7/8 통합 메모] data/ 폴더(HIRA CSV, e약은요 xlsx)가 아직 backend/에 없음.
   아래 로더들은 파일이 없거나 pandas/openpyxl 미설치여도 전부 except Exception으로
   조용히 넘어가서 4번(ATC 패턴)·5번(하드코딩) 단계로 자동 폴백하도록 이미 설계돼 있음
   (권순현 원본 그대로, 수정 없음). data/ 폴더 생기면 이 파일은 손댈 필요 없음.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)

_BASE = Path(__file__).parent / "data"

# ──────────────────────────────────────────────────────────────────
# 1. ATC 코드 → 약효 분류 매핑 테이블
# ──────────────────────────────────────────────────────────────────

_ATC_CLASS_MAP: dict[str, str] = {
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
    "B01AA": "항응고제(쿠마린계)",
    "B01AB": "항응고제(헤파린계)",
    "B01AC": "항혈소판제",
    "B01AE": "항응고제(직접트롬빈억제제)",
    "B01AF": "항응고제(직접Xa인자억제제)",
    "B01":   "항혈전제",
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
    "G04CA": "알파1차단제(전립선비대증)",
    "G04BE": "발기부전치료제",
    "J01":   "항생제",
    "J02":   "항진균제",
    "J05":   "항바이러스제",
    "L01":   "항암제",
    "L02":   "내분비치료제(항암)",
    "L04":   "면역억제제",
    "M01AH": "COX-2선택적억제제(NSAIDs)",
    "M01AB": "소염진통제(아세트산계)",
    "M01AC": "소염진통제(옥시캄계)",
    "M01AE": "소염진통제(프로피온산계)",
    "M01":   "소염진통제",
    "M03":   "근이완제",
    "M05BA": "비스포스포네이트(골다공증치료제)",
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
    "R03":   "기관지확장제",
    "R06":   "항히스타민제",
    "R05":   "기침·감기약",
    "S01":   "안과용제",
    "S02":   "이비인후과용제",
    "V03":   "해독제/기타치료제",
}


def _class_from_atc_code(atc_code: str) -> str:
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
_hira_code_map: Optional[dict] = None
_hira_name_df = None


def _load_hira():
    global _hira_code_map, _hira_name_df
    if _hira_code_map is not None:
        return
    if not _HIRA_PATH.exists():
        _logger.warning(
            "HIRA 약가마스터 CSV가 없습니다 — HIRA 조회 비활성, ATC 패턴 폴백으로 동작합니다.\n"
            "  필요 경로: %s\n"
            "  backend/data/ 폴더에 hira_drug_master_20251031.csv를 넣으면 활성화됩니다.",
            _HIRA_PATH,
        )
        _hira_code_map = {}
        _hira_name_df = None
        return
    try:
        import pandas as pd
        df = pd.read_csv(
            _HIRA_PATH, encoding="cp949",
            usecols=["한글상품명", "품목기준코드", "국제표준코드(ATC코드)"],
            dtype={"품목기준코드": str},
        )
        df = df[df["국제표준코드(ATC코드)"].notna()].copy()
        _hira_code_map = dict(zip(df["품목기준코드"].str.strip(), df["국제표준코드(ATC코드)"]))
        _hira_name_df = (
            df[df["한글상품명"].notna()][["한글상품명", "국제표준코드(ATC코드)"]]
            .drop_duplicates("한글상품명")
            .reset_index(drop=True)
        )
    except Exception:
        _hira_code_map = {}
        _hira_name_df = None


def _lookup_hira_by_code(drug_code: str) -> str:
    if not drug_code:
        return ""
    _load_hira()
    return _hira_code_map.get(drug_code.strip(), "")


_FORM_STARTERS = set("정캡주산시액이수분과좌크겔연")


def _lookup_hira_by_name(drug_name: str) -> str:
    if not drug_name or len(drug_name) < 2:
        return ""
    _load_hira()
    if _hira_name_df is None or _hira_name_df.empty:
        return ""

    n = len(drug_name)
    starts_mask = _hira_name_df["한글상품명"].str.startswith(drug_name, na=False)
    starts_hits = _hira_name_df[starts_mask]

    if not starts_hits.empty:
        def _is_direct(name: str) -> bool:
            rest = name[n:] if len(name) > n else ""
            return bool(rest) and (rest[0] in _FORM_STARTERS or rest[0].isdigit())

        direct = starts_hits[starts_hits["한글상품명"].apply(_is_direct)]
        pool = direct if not direct.empty else starts_hits
        idx = pool["한글상품명"].str.len().idxmin()
        return pool.loc[idx, "국제표준코드(ATC코드)"]

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
    # 항생제 (J01) — 아목시실린계·퀴놀론계·마크로라이드·세팔로스포린
    (r"아목시실린|아모클란|오구멘틴|아목시클라브",                 "항생제(페니실린계)"),
    (r"세팔렉신|세파클러|세픽심|세프트리악손",                    "항생제(세팔로스포린계)"),
    (r"시프로플록사신|레보플록사신|목시플록사신|플록사신",          "항생제(퀴놀론계)"),
    (r"아지트로마이신|클래리트로마이신|에리트로마이신",             "항생제(마크로라이드계)"),
    (r"독시사이클린|미노사이클린|테트라사이클린",                  "항생제(테트라사이클린계)"),
    # 부신피질호르몬제 (H02/D07) — 전신·국소 스테로이드
    (r"덱사메타손|프레드니솔론|메틸프레드니솔론|트리암시놀론|"
     r"베타메타손|하이드로코르티손|데스오웬|플루티카손|부데소니드", "부신피질호르몬제(스테로이드)"),
    # 안과용제 (S01)
    (r"히알루론산.*점안|아이드롭|인공눈물|히알루론산",             "안과용제(인공눈물)"),
    (r"라타노프로스트|트라보프로스트|비마토프로스트",              "안과용제(녹내장치료제)"),
    # 영양·보조제
    (r"엽산|폴산|폴릭애시드",                                    "조혈제(엽산)"),
    (r"철분|페러스|훼로바|황산철|글루콘산철|철결핍",              "조혈제(철분제)"),
    (r"오메가.?3|EPA|DHA|오메가쓰리|피시오일",                   "건강기능식품(오메가3)"),
    # 관절·연골
    (r"글루코사민|콘드로이친|조인트",                             "관절·연골보호제"),
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
    if not _EMED_PATH.exists():
        _logger.warning(
            "e약은요 DB xlsx가 없습니다 — e약은요 매칭 비활성, ATC 패턴 폴백으로 동작합니다.\n"
            "  필요 경로: %s\n"
            "  backend/data/ 폴더에 2_e약은요_정리.xlsx를 넣으면 활성화됩니다.",
            _EMED_PATH,
        )
        _drug_table = []
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
    norm_name = _normalize_name(drug_name)
    if len(norm_name) < 3:
        return None
    table = _load_drug_table()
    if not table:
        return None
    candidates = [e for e in table if norm_name in e["norm"] or e["norm"] in norm_name]
    if candidates:
        return min(candidates, key=lambda e: len(e["norm"]))
    best_score, best_entry = 0.0, None
    for entry in table:
        score = SequenceMatcher(None, norm_name, entry["norm"]).ratio()
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
    # key in drug_name 방향만 허용. drug_name in key(역방향)는 "프로"→"아스피린프로텍트"처럼
    # 2자 단편명이 긴 키의 부분 문자열로 오매칭되는 원인이므로 제거한다.
    for key, cls in _HARDCODED_FALLBACK.items():
        if key in drug_name:
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
      3. ATC 패턴 정규식 (성분명/브랜드명 키워드 기반, 신뢰도 높음)
      4. 하드코딩 폴백 사전 (소수 고빈도 약품 보장)
      5. e약은요 DB — OTC 부분/유사도 매칭 (마지막 수단; 유사도 매칭이라 오매칭 가능)

    [순서 변경 이유] e약은요는 약품명 유사도 매칭을 사용하므로 "아스피린프로텍트"가
    항히스타민제 약품과 매칭되거나, "베타메타손연고"가 알레르기 적응증 기준으로
    항히스타민제로 분류되는 등의 오분류가 발생한다. ATC 패턴과 폴백을 먼저 소진한
    뒤 마지막에만 e약은요를 사용한다.
    """
    if drug_code:
        atc = _lookup_hira_by_code(drug_code)
        if atc:
            cls = _class_from_atc_code(atc)
            if cls:
                return cls

    atc = _lookup_hira_by_name(drug_name)
    if atc:
        cls = _class_from_atc_code(atc)
        if cls:
            return cls

    cls = _class_from_atc_pattern(drug_name)
    if cls:
        return cls

    cls = _class_from_fallback(drug_name)
    if cls:
        return cls

    entry = _lookup_emedinfo(drug_name)
    if entry:
        cls = _class_from_efcy(entry["efcy"])
        if cls:
            return cls

    return ""


def get_drug_name_list() -> list[str]:
    """drug_matcher.py에서 재사용할 기준 약품명 목록 반환.

    HIRA 약가마스터 한글상품명 + e약은요 정규화 이름 + 하드코딩 폴백 키
    를 합쳐서 중복 제거한 리스트를 돌려준다. 데이터 파일이 없으면 하드코딩만 반환.
    """
    names: list[str] = []
    _load_hira()
    if _hira_name_df is not None and not _hira_name_df.empty:
        names.extend(_hira_name_df["한글상품명"].tolist())
    for entry in _load_drug_table():
        if entry["norm"]:
            names.append(entry["norm"])
    names.extend(_HARDCODED_FALLBACK.keys())
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def get_drug_info(drug_name: str, drug_code: str = "") -> dict:
    """상세 정보 반환 (match_source 포함). efficacy는 e약은요 매칭(emed)일 때만 채워짐."""
    if drug_code:
        atc = _lookup_hira_by_code(drug_code)
        if atc:
            cls = _class_from_atc_code(atc)
            if cls:
                return {"drug_name": drug_name, "drug_class": cls, "efficacy": "",
                        "match_source": "hira_code", "matched_item": f"코드:{drug_code}", "atc_code": atc}

    atc = _lookup_hira_by_name(drug_name)
    if atc:
        cls = _class_from_atc_code(atc)
        if cls:
            return {"drug_name": drug_name, "drug_class": cls, "efficacy": "",
                    "match_source": "hira_name", "matched_item": drug_name, "atc_code": atc}

    entry = _lookup_emedinfo(drug_name)
    if entry:
        cls = _class_from_efcy(entry["efcy"])
        return {"drug_name": drug_name, "drug_class": cls or _class_from_fallback(drug_name),
                "efficacy": entry["efcy"], "match_source": "emed", "matched_item": entry["item_name"],
                "atc_code": ""}

    cls = _class_from_atc_pattern(drug_name)
    if cls:
        return {"drug_name": drug_name, "drug_class": cls, "efficacy": "",
                "match_source": "atc_pattern", "matched_item": "", "atc_code": ""}

    cls = _class_from_fallback(drug_name)
    return {"drug_name": drug_name, "drug_class": cls, "efficacy": "",
            "match_source": "fallback" if cls else "unknown", "matched_item": "", "atc_code": ""}
