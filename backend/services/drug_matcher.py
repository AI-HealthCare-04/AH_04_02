"""
drug_matcher.py — OCR 약품명 유사도 매칭

역할: OCR이 읽은 약품명 텍스트와 기준 약품명 목록 간의 오타·부분일치를 처리한다.
      drug_reference.py의 약효 분류(drug_class/drug_code)와 역할이 겹치지 않도록
      "어떤 표준 이름에 가장 가까운가"만 판정하고 분류는 하지 않는다.

사용처: routers/ocr_router.py의 run_ocr() — OcrResult.matched_drug_name / match_score /
        needs_review 컬럼을 채울 때 호출.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher, get_close_matches

from services.drug_reference import get_drug_name_list

MATCH_THRESHOLD = 0.7

_cached_names: list[str] | None = None
_cached_norm_names: list[str] | None = None  # _normalize() 적용된 기준 목록

# 용량·제형 정보 패턴 — OCR과 기준 목록 양쪽에 동일하게 적용
# [2026-07-20 버그수정] HIRA 약가마스터가 같은 성분의 다른 용량 항목끼리도 "밀리그램"/
# "밀리그람"(마이크로그램도 마찬가지) 표기를 섞어 쓴다(정부 데이터 자체의 표기 불일치,
# 예: "노바스크정5밀리그람" vs "노바스크정2.5밀리그램") — 영문 단위(mg/g 등)만 인식하던
# 기존 패턴은 이 한글 표기를 전혀 못 지워서, 정규화를 거쳐도 용량이 그대로 남아있었다.
# 그 결과 "노바스크정5밀리그램"(OCR 원문)이 정답("노바스크정5밀리그람", 표기만 다름)보다
# 전혀 다른 약("노바크정5밀리그램", 우연히 "그램" 철자가 똑같아 근소하게 더 높은 점수)에
# 더 가깝게 계산되는 오매칭이 실제로 재현됐다.
_DOSAGE_RE = re.compile(
    r'\s*\d+(\.\d+)?\s*'
    r'(mg|ml|mcg|μg|ug|g|mEq|IU|%'
    r'|밀리그램|밀리그람|마이크로그램|마이크로그람|그램|그람|밀리리터|리터'
    r'|정|캡슐|연질캡슐|장용정|장용캡슐|서방정|분산정|액|시럽|주|크림|연고|겔|패취|패치|점안|점이)'
    # [2026-07-27 버그수정] 슬래시 뒤가 "50/1000mg"(복합제, 숫자+단위)뿐 아니라 "5mg/ml"
    # (주사제 농도 표기, 단위만)일 수도 있다 — 원래 \d+(숫자 필수)였는데 주사제는 분모
    # 단위 앞에 숫자가 없어서 이 그룹이 매칭에 실패했고, "5mg/ml"에서 "5mg"만 지워지고
    # "/ml"이 그대로 남아 정규화된 이름이 지저분해졌다(유사도 매칭 점수 하락 → 실제로는
    # 맞는 약인데 "검토 필요"로 잘못 넘어감). \d*로 바꿔 숫자 없이 단위만 오는 경우도 지운다.
    r'(\s*/\s*\d*(\.\d+)?\s*(mg|ml|mcg|μg|ug|g|mEq|IU|%'
    r'|밀리그램|밀리그람|마이크로그램|마이크로그람|그램|그람|밀리리터|리터'
    r'|정|캡슐|연질캡슐|장용정|장용캡슐|서방정|분산정))?',
    re.IGNORECASE,
)

_DOSAGE_NUMBER_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(?:mg|ml|mcg|μg|ug|g|mEq|IU|%|밀리그램|밀리그람|마이크로그램|마이크로그람|그램|그람|밀리리터|리터)',
    re.IGNORECASE,
)


def _extract_dosage_number(text: str) -> str | None:
    """이름에서 단위 직전 첫 용량 숫자를 추출한다("5"/"2.5" 등) — 없으면 None."""
    m = _DOSAGE_NUMBER_RE.search(text)
    return m.group(1) if m else None


def _normalize(text: str) -> str:
    """용량·제형 표기를 제거하고 공백을 정규화한 약품명 반환.

    "암로디핀 5mg" → "암로디핀"
    "글루코파지 500mg/5mg" → "글루코파지"
    "히알루론산 1% 점안액" → "히알루론산 점안액" (수치만 제거, 제형 키워드 유지)
    """
    normalized = _DOSAGE_RE.sub("", text).strip()
    # 연속 공백 정리
    return re.sub(r'\s+', ' ', normalized).strip()


def _names() -> list[str]:
    global _cached_names
    if _cached_names is None:
        _cached_names = get_drug_name_list()
    return _cached_names


def _norm_names() -> list[str]:
    """기준 약품명 목록을 _normalize() 적용한 버전으로 캐싱."""
    global _cached_norm_names
    if _cached_norm_names is None:
        _cached_norm_names = [_normalize(n) for n in _names()]
    return _cached_norm_names


def _match_normalized(
    norm_ocr: str, ocr_text: str, raw_pool: list[str], norm_pool: list[str]
) -> tuple[str, float]:
    """정규화된 문자열로 기준 목록과 매칭, (원본 기준명, score) 반환.

    1단계: normalized 문자열로 유사도 점수 계산.
    동점 시 2단계: 용량 숫자가 원본과 정확히 같은 후보를 우선한다 — 3단계: 그래도
    못 가르면 원본 ocr_text vs raw 기준명 전체 문자열 유사도로 타이브레이킹한다.

    [2026-07-20 버그수정] 2단계(용량 숫자 우선)가 없었을 때는, 같은 성분명 다른
    용량("노바스크정2.5밀리그램"/"노바스크정5밀리그람" 등, 정규화 후 전부 "노바스크정"
    으로 뭉쳐짐)이 동시에 후보가 되면 3단계(전체 문자열 유사도)만으로 골랐는데,
    difflib.SequenceMatcher.ratio()가 문자열 길이·삽입 위치에 따라 부정확하게 흔들려서
    OCR 원문이 "5mg"인데 "2.5mg" 항목이 오히려 근소하게 더 높은 점수로 뽑히는 실제
    오매칭이 있었다(용량이 다른 약을 골라버리는 건 복약 안전상 특히 위험). 용량 숫자가
    명시적으로 일치하는 후보가 있으면 그걸 최우선으로 삼아 이 위험을 없앤다.
    """
    close_norm = get_close_matches(norm_ocr, norm_pool, n=5, cutoff=0.3)
    if close_norm:
        norm_to_raws: dict[str, list[str]] = {}
        for raw, norm in zip(raw_pool, norm_pool):
            if norm in close_norm:
                norm_to_raws.setdefault(norm, []).append(raw)
        candidates = [
            (raw, norm)
            for norm in close_norm
            for raw in norm_to_raws.get(norm, [])
        ]
    else:
        candidates = list(zip(raw_pool[:500], norm_pool[:500]))

    ocr_dosage = _extract_dosage_number(ocr_text)

    best_name, best_score = "", 0.0
    for raw_name, norm_name in candidates:
        score = SequenceMatcher(None, norm_ocr, norm_name).ratio()
        if score > best_score:
            best_score, best_name = score, raw_name
        elif score == best_score and best_name:
            if ocr_dosage is not None:
                raw_matches_dosage = _extract_dosage_number(raw_name) == ocr_dosage
                best_matches_dosage = _extract_dosage_number(best_name) == ocr_dosage
                if raw_matches_dosage and not best_matches_dosage:
                    best_name = raw_name
                    continue
                if best_matches_dosage and not raw_matches_dosage:
                    continue
            raw_score = SequenceMatcher(None, ocr_text, raw_name).ratio()
            prev_raw_score = SequenceMatcher(None, ocr_text, best_name).ratio()
            if raw_score > prev_raw_score:
                best_name = raw_name
    return best_name, best_score


def match_drug(ocr_text: str) -> tuple[str, float]:
    """OCR 인식 약품명과 기준 목록 간 유사도 매칭.

    OCR 입력과 기준 목록 양쪽에 _normalize()를 적용한 뒤 비교하므로
    "암로디핀 5mg"(OCR) vs "암로디핀정5mg"(기준) 같이 용량 표기가
    다를 때도 정확하게 매칭된다. 정규화 후 3자 미만으로 짧아지는 케이스는
    원본 텍스트로도 병행 매칭해 더 높은 score를 취한다.

    Returns:
        (matched_name, score)
        matched_name: 원본 기준 약품명 (정규화 전)
        score: 0.0 ~ 1.0 (SequenceMatcher.ratio())
    """
    if not ocr_text:
        return "", 0.0

    raw_pool = _names()
    if not raw_pool:
        return ocr_text, 0.0

    norm_ocr = _normalize(ocr_text)
    norm_pool = _norm_names()

    best_name, best_score = _match_normalized(norm_ocr, ocr_text, raw_pool, norm_pool)

    # 정규화로 너무 짧아진 경우(예: "엽산 400mcg" → "엽산") 원본도 시도
    if len(norm_ocr) < 3:
        raw_close = get_close_matches(ocr_text, raw_pool, n=5, cutoff=0.3)
        candidates_raw = raw_close if raw_close else raw_pool[:500]
        for raw_name in candidates_raw:
            score = SequenceMatcher(None, ocr_text, raw_name).ratio()
            if score > best_score:
                best_score, best_name = score, raw_name

    return best_name, round(best_score, 4)
