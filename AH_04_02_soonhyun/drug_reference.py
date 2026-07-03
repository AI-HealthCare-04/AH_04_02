# -*- coding: utf-8 -*-
"""
drug_reference.py — e약은요 DB + ATC 코드 기반 약효 분류 모듈

데이터 출처:
  - data/2_e약은요_정리.xlsx  : 4,809개 의약품 itemName / efcyQesitm
  - data/DB_출처_sanitized.xlsx: ATC 코드 매핑 참고 (고혈압 C02-C09, 당뇨 A10, 고지혈 C10)

매칭 우선순위:
  1. ATC 기반 약명 패턴 정규식 (전문의약품 포함, 가장 정확)
  2. e약은요 DB 부분/유사 매칭 + efcyQesitm 키워드 분류 (OTC 중심)
  3. parsing_rules.py 하드코딩 폴백

Note: e약은요 DB는 일반의약품/OTC 중심이므로 고혈압·당뇨·고지혈증 전문의약품
(암로디핀, 메트포르민 등)은 거의 미수록. → ATC 패턴이 1차 분류를 담당.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────
# 1. ATC 코드 기반 약명 패턴  (DB 출처.xlsx 참고)
#    C02-C09: 고혈압, A10: 당뇨병, C10: 고지혈증
# ──────────────────────────────────────────────────────────────────

_ATC_PATTERNS: list[tuple[str, str]] = [
    # ── 고혈압 (ATC C02-C09) ───────────────────────────────────────
    (r"메트포르민|글루코파지|다이아벡스|글루코민|다이아닐",
     "당뇨병용제(비구아니드)"),
    (r"글리벤클라마이드|글리메피리드|아마릴|글리피진|글리클라지드|다이아미크론",
     "당뇨병용제(설포닐우레아)"),
    (r"시타글립틴|빌다글립틴|삭사글립틴|알로글립틴|자누비아|가브스|온글라이자",
     "당뇨병용제(DPP-4억제제)"),
    (r"엠파글리플로진|다파글리플로진|카나글리플로진|자디앙|포시가",
     "당뇨병용제(SGLT-2억제제)"),
    (r"리라글루타이드|세마글루타이드|빅토자|오젬픽",
     "당뇨병용제(GLP-1수용체작용제)"),
    (r"인슐린",
     "인슐린제제"),
    # ── 고혈압 (ATC C07-C09) ───────────────────────────────────────
    (r"암로디핀|노바스크|레코르달|니페디핀|아달라트|딜티아젬|헤르벤|베라파밀",
     "칼슘채널차단제"),
    (r"로자탄|로사르탄|발사르탄|디오반|이르베사르탄|아프로벨|올메사르탄|텔미사르탄",
     "ARB(안지오텐신수용체차단제)"),
    (r"에날라프릴|리시노프릴|페린도프릴|라미프릴|캡토프릴",
     "ACE억제제"),
    (r"아테놀롤|메토프롤롤|카베딜롤|비소프롤롤|프로프라놀롤",
     "베타차단제"),
    (r"히드로클로로티아지드|인다파마이드|클로르탈리돈|푸로세마이드|토라세미드",
     "이뇨제"),
    (r"독사조신|테라조신|프라조신",
     "알파차단제"),
    # ── 고지혈증 (ATC C10) ─────────────────────────────────────────
    (r"아토르바스타틴|리피토|아토젯|로수바스타틴|크레스토|심바스타틴|조코|"
     r"프라바스타틴|플루바스타틴|피타바스타틴|리바로",
     "HMG-CoA환원효소억제제(스타틴)"),
    (r"에제티미브|이제티미브|로수젯",
     "콜레스테롤흡수억제제"),
    (r"페노피브레이트|페노피브릭산|베자피브레이트|제노피브레이트",
     "피브레이트계"),
    # ── 순환기 ─────────────────────────────────────────────────────
    (r"아스피린프로텍트|아스트릭스|아스피린.*장용|클로피도그렐|플라빅스|티카그렐러",
     "항혈소판제"),
    (r"아스피린(?!.*장용)",
     "항혈소판제"),
    (r"와파린|쿠마딘|리바록사반|자렐토|다비가트란|프라닥사|아픽사반|엘리퀴스",
     "항응고제"),
    # ── 위장 ──────────────────────────────────────────────────────
    (r"오메프라졸|에소메프라졸|넥시움|판토프라졸|판토락|라베프라졸|파리에트|란소프라졸",
     "양성자펌프억제제(PPI)"),
    (r"파모티딘|라니티딘|시메티딘|니자티딘",
     "H2수용체차단제"),
    (r"모사프리드|가스모틴|돔페리돈|메토클로프라미드",
     "위장운동촉진제"),
    (r"수크랄페이트|아르기닌",
     "위점막보호제"),
    # ── 소염진통 ──────────────────────────────────────────────────
    (r"세레콕시브|세레브렉스|에토리콕시브|아르콕시아|로페콕시브",
     "COX-2선택적억제제(NSAIDs)"),
    (r"이부프로펜|나프록센|나프록센나트륨|디클로페낙|인도메타신|멜록시캄|피록시캄",
     "비선택적NSAIDs"),
    (r"아세트아미노펜|타이레놀|파라세타몰",
     "해열진통제(아세트아미노펜)"),
    (r"에페리손|바클로펜|시클로벤자프린",
     "근이완제"),
    # ── 신경/정신 ─────────────────────────────────────────────────
    (r"졸피뎀|트리아졸람|에스조피클론|루네스타",
     "수면유도제(비벤조디아제핀계)"),
    (r"디아제팜|알프라졸람|클로나제팜|로라제팜",
     "벤조디아제핀계"),
    (r"세르트랄린|파록세틴|에스시탈로프람|플루옥세틴",
     "SSRI(선택적세로토닌재흡수억제제)"),
    # ── 골관절/기타 ───────────────────────────────────────────────
    (r"알렌드론산|리세드론산|포사맥스|악토넬",
     "비스포스포네이트(골다공증치료제)"),
    (r"콘드로이친|글루코사민",
     "관절영양제"),
    (r"케토티펜|세티리진|로라타딘|펙소페나딘",
     "항히스타민제"),
    (r"레보티록신|신지로이드",
     "갑상선호르몬제"),
]

# 컴파일된 패턴 (모듈 로드 시 1회)
_COMPILED_ATC: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), cls)
    for pat, cls in _ATC_PATTERNS
]

# ──────────────────────────────────────────────────────────────────
# 2. efcyQesitm → 약효 분류 키워드 맵  (e약은요 DB 히트 시 사용)
# ──────────────────────────────────────────────────────────────────

_EFCY_CLASS_RULES: list[tuple[list[str], str]] = [
    (["혈전 생성 억제", "혈소판 응집"],           "항혈소판제"),
    (["콜레스테롤", "중성지방", "고지혈"],          "고지혈증치료제(스타틴)"),
    (["혈당", "당뇨"],                            "당뇨병용제"),
    (["고혈압", "혈압을 낮추"],                   "항고혈압제"),
    (["혈압"],                                    "항고혈압제"),
    (["불면", "수면"],                            "수면유도제"),
    (["양성자 펌프", "위궤양", "역류성 식도"],     "양성자펌프억제제(PPI)"),
    (["위산과다", "속쓰림", "신트림"],            "H2수용체차단제"),
    (["관절염", "관절 통증"],                     "소염진통제(NSAIDs)"),
    (["두통", "치통", "통증", "해열"],            "해열진통제"),
    (["기관지", "천식", "기침"],                  "기관지확장제"),
    (["알레르기", "두드러기", "가려움"],           "항히스타민제"),
    (["세균", "항균"],                            "항생제"),
]

# ──────────────────────────────────────────────────────────────────
# 3. parsing_rules.py DRUG_CLASS_DICTIONARY 폴백
# ──────────────────────────────────────────────────────────────────

_HARDCODED_FALLBACK: dict[str, str] = {
    "세레브렉스":     "COX-2선택적억제제(NSAIDs)",
    "세레콕시브":     "COX-2선택적억제제(NSAIDs)",
    "졸피뎀":         "수면유도제(비벤조디아제핀계)",
    "파모티딘":       "H2수용체차단제",
    "아스피린프로텍트": "항혈소판제",
    "아스피린":       "항혈소판제",
    "심바스타틴":     "HMG-CoA환원효소억제제(스타틴)",
    "오메프라졸":     "양성자펌프억제제(PPI)",
    "암로디핀":       "칼슘채널차단제",
    "로자탄칼륨":     "ARB(안지오텐신수용체차단제)",
    "로자탄":         "ARB(안지오텐신수용체차단제)",
    "메트포르민":     "당뇨병용제(비구아니드)",
    "리피토":         "HMG-CoA환원효소억제제(스타틴)",
    "노바스크":       "칼슘채널차단제",
    "글루코파지":     "당뇨병용제(비구아니드)",
    "에페리손염산":   "근이완제",
    "라베프라졸":     "양성자펌프억제제(PPI)",
}

# ──────────────────────────────────────────────────────────────────
# 4. e약은요 DB 로드  (지연 로드, 모듈 사용 전까지 파일 미오픈)
# ──────────────────────────────────────────────────────────────────

_DATA_PATH = Path(__file__).parent / "data" / "2_e약은요_정리.xlsx"
_drug_table: Optional[list[dict]] = None  # 지연 초기화

_STRIP_RE = re.compile(
    r"\d+(?:\.\d+)?(?:mg|g|ml|밀리그램|그램)"     # 용량 제거
    r"|(?:정|캡슐|주사|주|산|시럽|액|환|겔|크림|연고|패취|패치)\d*(?:\.\d+)?(?:mg|g|ml)?"
    r"|\([^)]+\)",                               # 제조사 괄호 제거
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    return _STRIP_RE.sub("", name).strip()


def _load_drug_table() -> list[dict]:
    global _drug_table
    if _drug_table is not None:
        return _drug_table
    try:
        import openpyxl
        wb = openpyxl.load_workbook(_DATA_PATH, read_only=True, data_only=True)
        ws = wb["정리데이터"]
        table = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            raw_name = str(row[1]) if row[1] else ""
            efcy = str(row[3]) if row[3] else ""
            if raw_name:
                table.append({
                    "item_name": raw_name,
                    "norm": _normalize_name(raw_name),
                    "efcy": efcy,
                })
        wb.close()
        _drug_table = table
    except Exception:
        _drug_table = []
    return _drug_table


# ──────────────────────────────────────────────────────────────────
# 5. 내부 매칭 로직
# ──────────────────────────────────────────────────────────────────

def _class_from_atc(drug_name: str) -> str:
    for pattern, drug_class in _COMPILED_ATC:
        if pattern.search(drug_name):
            return drug_class
    return ""


def _class_from_efcy(efcy: str) -> str:
    # efcyQesitm에서 "이 약은 X에 사용합니다" 부분만 추출
    m = re.search(r"이 약은\s+(.+?)(?:에 사용합니다|에 쓰입니다)", efcy, re.DOTALL)
    indication = m.group(1) if m else efcy

    for keywords, drug_class in _EFCY_CLASS_RULES:
        if any(kw in indication for kw in keywords):
            return drug_class
    return ""


def _lookup_emedinfo(drug_name: str) -> Optional[dict]:
    # 2자 이하 단편 이름은 오매칭 가능성 높음 → e약은요 DB 조회 생략
    if len(drug_name) < 3:
        return None
    table = _load_drug_table()
    if not table:
        return None

    # 1. 정규화된 이름으로 부분 매칭
    candidates = [
        e for e in table
        if drug_name in e["norm"] or e["norm"] in drug_name
    ]
    if candidates:
        return min(candidates, key=lambda e: len(e["norm"]))

    # 2. 유사도 매칭 (threshold 0.72)
    best_score, best_entry = 0.0, None
    for entry in table:
        score = SequenceMatcher(None, drug_name, entry["norm"]).ratio()
        if score > best_score:
            best_score, best_entry = score, entry
    if best_score >= 0.72 and best_entry:
        return best_entry

    return None


def _class_from_fallback(drug_name: str) -> str:
    for key, cls in _HARDCODED_FALLBACK.items():
        if key in drug_name or drug_name in key:
            return cls
    return ""


# ──────────────────────────────────────────────────────────────────
# 6. 공개 API
# ──────────────────────────────────────────────────────────────────

def get_drug_class(drug_name: str) -> str:
    """
    parsing_rules.py에서 추출한 drug_name으로 약효 분류를 반환한다.

    우선순위:
      1. ATC 코드 기반 약명 패턴 (고혈압·당뇨·고지혈증 우선)
      2. e약은요 DB 매칭 + efcyQesitm 분류
      3. 하드코딩 폴백
    """
    # 1. ATC 패턴
    cls = _class_from_atc(drug_name)
    if cls:
        return cls

    # 2. e약은요 DB
    entry = _lookup_emedinfo(drug_name)
    if entry:
        cls = _class_from_efcy(entry["efcy"])
        if cls:
            return cls

    # 3. 하드코딩 폴백
    return _class_from_fallback(drug_name)


def get_drug_info(drug_name: str) -> dict:
    """
    drug_name에 대한 상세 정보를 반환한다.

    Returns:
        {
            "drug_name":    str,       # 입력된 약명
            "drug_class":   str,       # 약효 분류
            "match_source": str,       # "atc" | "emed" | "fallback" | "unknown"
            "matched_item": str,       # e약은요 매칭 품목명 (emed 소스일 때)
            "efcy_summary": str,       # efcyQesitm 앞 100자 (emed 소스일 때)
        }
    """
    # 1. ATC 패턴
    cls = _class_from_atc(drug_name)
    if cls:
        return {
            "drug_name": drug_name,
            "drug_class": cls,
            "match_source": "atc",
            "matched_item": "",
            "efcy_summary": "",
        }

    # 2. e약은요 DB
    entry = _lookup_emedinfo(drug_name)
    if entry:
        cls = _class_from_efcy(entry["efcy"])
        return {
            "drug_name": drug_name,
            "drug_class": cls or _class_from_fallback(drug_name),
            "match_source": "emed",
            "matched_item": entry["item_name"],
            "efcy_summary": entry["efcy"][:100],
        }

    # 3. 하드코딩 폴백
    cls = _class_from_fallback(drug_name)
    return {
        "drug_name": drug_name,
        "drug_class": cls,
        "match_source": "fallback" if cls else "unknown",
        "matched_item": "",
        "efcy_summary": "",
    }


# ──────────────────────────────────────────────────────────────────
# 7. 직접 실행 — 샘플 테스트
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # mock_prescription_table.png (2-2)
        ("암로디핀",       "칼슘채널차단제"),
        ("로자탄칼륨",     "ARB(안지오텐신수용체차단제)"),
        ("메트포르민",     "당뇨병용제(비구아니드)"),
        # mock_prescription_bag.png (2-3)
        ("아스피린프로텍트", "항혈소판제"),
        ("심바스타틴",     "HMG-CoA환원효소억제제(스타틴)"),
        ("오메프라졸",     "양성자펌프억제제(PPI)"),
        # mock_prescription_abbrev.png (2-4)
        ("세레브렉스",     "COX-2선택적억제제(NSAIDs)"),
        ("졸피뎀",         "수면유도제(비벤조디아제핀계)"),
        ("파모티딘",       "H2수용체차단제"),
    ]

    print(f"{'약품명':<18} {'예상':^28} {'결과':^28} {'소스':<10} {'OK'}")
    print("-" * 95)
    correct = 0
    for drug_name, expected in test_cases:
        info = get_drug_info(drug_name)
        got = info["drug_class"]
        # 핵심 키워드 포함 여부로 정답 판정
        ok = (expected.split("(")[0] in got) or (got.split("(")[0] in expected) or (got == expected)
        correct += ok
        mark = "✅" if ok else "❌"
        print(f"{drug_name:<18} {expected:^28} {got:^28} {info['match_source']:<10} {mark}")

    print(f"\n정확도: {correct}/{len(test_cases)}")
