# -*- coding: utf-8 -*-
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

from drug_reference import get_drug_name_list

MATCH_THRESHOLD = 0.7

_cached_names: list[str] | None = None
_cached_norm_names: list[str] | None = None  # _normalize() 적용된 기준 목록

# 용량·제형 정보 패턴 — OCR과 기준 목록 양쪽에 동일하게 적용
_DOSAGE_RE = re.compile(
    r'\s*\d+(\.\d+)?\s*'
    r'(mg|ml|mcg|μg|ug|g|mEq|IU|%|정|캡슐|연질캡슐|장용정|장용캡슐|서방정|분산정|액|시럽|주|크림|연고|겔|패취|패치|점안|점이)'
    r'(\s*/\s*\d+(\.\d+)?\s*(mg|ml|mcg|μg|ug|g|mEq|IU|%|정|캡슐|연질캡슐|장용정|장용캡슐|서방정|분산정))?',
    re.IGNORECASE,
)


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


def _match_normalized(norm_ocr: str, raw_pool: list[str], norm_pool: list[str]) -> tuple[str, float]:
    """정규화된 문자열로 기준 목록과 매칭, (원본 기준명, score) 반환."""
    close_norm = get_close_matches(norm_ocr, norm_pool, n=5, cutoff=0.3)
    if close_norm:
        norm_to_raw: dict[str, str] = {}
        for raw, norm in zip(raw_pool, norm_pool):
            if norm in close_norm and norm not in norm_to_raw:
                norm_to_raw[norm] = raw
        candidates = [(norm_to_raw[n], n) for n in close_norm if n in norm_to_raw]
    else:
        candidates = list(zip(raw_pool[:500], norm_pool[:500]))

    best_name, best_score = "", 0.0
    for raw_name, norm_name in candidates:
        score = SequenceMatcher(None, norm_ocr, norm_name).ratio()
        if score > best_score:
            best_score, best_name = score, raw_name
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

    best_name, best_score = _match_normalized(norm_ocr, raw_pool, norm_pool)

    # 정규화로 너무 짧아진 경우(예: "엽산 400mcg" → "엽산") 원본도 시도
    if len(norm_ocr) < 3:
        raw_close = get_close_matches(ocr_text, raw_pool, n=5, cutoff=0.3)
        candidates_raw = raw_close if raw_close else raw_pool[:500]
        for raw_name in candidates_raw:
            score = SequenceMatcher(None, ocr_text, raw_name).ratio()
            if score > best_score:
                best_score, best_name = score, raw_name

    return best_name, round(best_score, 4)
