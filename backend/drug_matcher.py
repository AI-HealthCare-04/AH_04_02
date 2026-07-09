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

from difflib import SequenceMatcher, get_close_matches

from drug_reference import get_drug_name_list

MATCH_THRESHOLD = 0.7

_cached_names: list[str] | None = None


def _names() -> list[str]:
    global _cached_names
    if _cached_names is None:
        _cached_names = get_drug_name_list()
    return _cached_names


def match_drug(ocr_text: str) -> tuple[str, float]:
    """OCR 인식 약품명과 기준 목록 간 유사도 매칭.

    1. get_close_matches(cutoff=0.3)로 후보 5개를 좁힌다.
       (내부에서 SequenceMatcher를 사용하여 O(n) 전체 탐색을 피함)
    2. 좁혀진 후보에 대해 SequenceMatcher.ratio()로 정확한 점수를 산출한다.
    3. 후보가 없으면 전체 목록의 앞 500개에서 탐색한다(데이터 미로드 시 안전망).

    Returns:
        (matched_name, score)
        matched_name: 가장 유사한 기준 약품명 (후보 없으면 빈 문자열)
        score: 0.0 ~ 1.0 (SequenceMatcher.ratio())
    """
    if not ocr_text:
        return "", 0.0

    candidates_pool = _names()
    if not candidates_pool:
        return ocr_text, 0.0

    close = get_close_matches(ocr_text, candidates_pool, n=5, cutoff=0.3)
    candidates = close if close else candidates_pool[:500]

    best_name, best_score = "", 0.0
    for name in candidates:
        score = SequenceMatcher(None, ocr_text, name).ratio()
        if score > best_score:
            best_score, best_name = score, name

    return best_name, round(best_score, 4)
