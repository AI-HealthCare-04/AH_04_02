# -*- coding: utf-8 -*-
"""
drug_matcher.py — OCR 약품명 검증·정규화 모듈 (drug_reference.py의 자매 모듈)

역할 구분:
  - drug_reference.py : "이 약이 무슨 효능군인가" → drug_class 결정 (RAG/화면 표시용)
  - drug_matcher.py    : "OCR이 읽은 이름이 실제 등록 의약품과 일치하는가, 얼마나 확신하는가"
                         → review_required 판단 + 정식 명칭 정규화

데이터 출처 (drug_reference.py와 동일 파일 재사용 — data/ 폴더에 별도 파일 추가 불필요):
  - data/hira_drug_master_20251031.csv : HIRA 약가마스터 (취소품목 제외한 활성 품목만 사용)
  - data/2_e약은요_정리.xlsx           : e약은요 4,809건 (매칭 성공 시 효능 텍스트까지 확보)

매칭 우선순위:
  1. e약은요 — 정규화 정확 일치 → 퍼지 매칭
  2. HIRA 활성 품목 — 정규화 정확 일치 → 퍼지 매칭

⚠️ drug_reference.py와 동일한 설계 원칙: data/ 파일이 없거나 pandas/openpyxl/rapidfuzz가
   미설치여도 전부 except Exception으로 조용히 넘어가서 "매칭 실패"로 처리됨 — 앱이 죽지 않음.

필요 패키지: rapidfuzz (pip install rapidfuzz --break-system-packages) — 없으면 정확 일치만 동작.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional

_BASE = Path(__file__).parent / "data"
_HIRA_PATH = _BASE / "hira_drug_master_20251031.csv"
_EMED_PATH = _BASE / "2_e약은요_정리.xlsx"

SCORE_AUTO_ACCEPT = 90    # 이상이면 자동 신뢰 (needs_review=False)
SCORE_NEEDS_REVIEW = 70   # 이상~AUTO_ACCEPT 미만이면 매칭은 되지만 검토 필요


def _normalize(name: Optional[str]) -> str:
    """OCR 노이즈 제거용 정규화: HTML 엔티티 해제 + 공백 전부 제거."""
    if not name:
        return ""
    return re.sub(r"\s+", "", html.unescape(str(name))).strip()


# ──────────────────────────────────────────────────────────────────
# e약은요 지연 로드
# ──────────────────────────────────────────────────────────────────

_easy_by_norm: Optional[dict] = None
_easy_norm_names: Optional[list] = None


def _load_easy() -> None:
    global _easy_by_norm, _easy_norm_names
    if _easy_by_norm is not None:
        return
    try:
        import openpyxl
        wb = openpyxl.load_workbook(_EMED_PATH, read_only=True, data_only=True)
        ws = wb["정리데이터"]
        by_norm: dict = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            item_name = row[1] if len(row) > 1 else None
            efcy = row[3] if len(row) > 3 else None
            norm = _normalize(item_name)
            if norm and norm not in by_norm:
                by_norm[norm] = {"item_name": item_name, "efcy": efcy}
        wb.close()
        _easy_by_norm = by_norm
        _easy_norm_names = list(by_norm.keys())
    except Exception:
        _easy_by_norm = {}
        _easy_norm_names = []


# ──────────────────────────────────────────────────────────────────
# HIRA 지연 로드 (취소품목 제외, 정규화 이름 기준 중복 제거)
# ──────────────────────────────────────────────────────────────────

_hira_by_norm: Optional[dict] = None
_hira_norm_names: Optional[list] = None


def _load_hira() -> None:
    global _hira_by_norm, _hira_norm_names
    if _hira_by_norm is not None:
        return
    try:
        import pandas as pd
        df = pd.read_csv(
            _HIRA_PATH, encoding="cp949",
            usecols=["한글상품명", "품목기준코드", "취소일자",
                     "일반명코드(성분명코드)", "국제표준코드(ATC코드)"],
            dtype=str,
        )
        df = df[df["취소일자"].isna()]
        by_norm: dict = {}
        for _, r in df.iterrows():
            norm = _normalize(r["한글상품명"])
            if norm and norm not in by_norm:
                by_norm[norm] = {
                    "product_name": r["한글상품명"],
                    "item_code": r["품목기준코드"],
                    "ingredient_code": r["일반명코드(성분명코드)"] or None,
                    "atc_code": r["국제표준코드(ATC코드)"] or None,
                }
        _hira_by_norm = by_norm
        _hira_norm_names = list(by_norm.keys())
    except Exception:
        _hira_by_norm = {}
        _hira_norm_names = []


# ──────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────

def match_drug_name(raw_name: str) -> dict:
    """
    OCR로 추출된 약품명을 e약은요 → HIRA 순으로 매칭.

    반환:
        {
          "input_name": str,
          "matched": bool,
          "matched_name": str | None,
          "score": float (0~100),
          "source": "easy_drug" | "hira_master" | None,
          "needs_review": bool,
          "ingredient_code": str | None,
          "atc_code": str | None,
          "efficacy": str | None,   # easy_drug 매칭 시에만
        }
    """
    result = {
        "input_name": raw_name, "matched": False, "matched_name": None,
        "score": 0.0, "source": None, "needs_review": True,
        "ingredient_code": None, "atc_code": None, "efficacy": None,
    }

    norm = _normalize(raw_name)
    if not norm:
        return result

    try:
        from rapidfuzz import fuzz, process
    except Exception:
        fuzz = process = None  # 미설치 시 정확 일치만 동작

    # 1순위: e약은요
    _load_easy()
    if norm in _easy_by_norm:
        e = _easy_by_norm[norm]
        result.update(matched=True, matched_name=e["item_name"], score=100.0,
                       source="easy_drug", efficacy=e["efcy"], needs_review=False)
        return result
    if process and _easy_norm_names:
        hit = process.extractOne(norm, _easy_norm_names, scorer=fuzz.WRatio)
        if hit and hit[1] >= SCORE_NEEDS_REVIEW:
            e = _easy_by_norm[hit[0]]
            result.update(matched=True, matched_name=e["item_name"], score=float(hit[1]),
                           source="easy_drug", efficacy=e["efcy"],
                           needs_review=hit[1] < SCORE_AUTO_ACCEPT)
            return result

    # 2순위: HIRA 활성 품목
    _load_hira()
    if norm in _hira_by_norm:
        h = _hira_by_norm[norm]
        result.update(matched=True, matched_name=h["product_name"], score=100.0,
                       source="hira_master", ingredient_code=h["ingredient_code"],
                       atc_code=h["atc_code"], needs_review=False)
        return result
    if process and _hira_norm_names:
        hit = process.extractOne(norm, _hira_norm_names, scorer=fuzz.WRatio)
        if hit and hit[1] >= SCORE_NEEDS_REVIEW:
            h = _hira_by_norm[hit[0]]
            result.update(matched=True, matched_name=h["product_name"], score=float(hit[1]),
                           source="hira_master", ingredient_code=h["ingredient_code"],
                           atc_code=h["atc_code"], needs_review=hit[1] < SCORE_AUTO_ACCEPT)
            return result

    return result


if __name__ == "__main__":
    for name in ["타이레놀정500mg", "타이레놀정 500 mg", "아스피린프로텍트정100mg",
                 "게보린정", "낙센정", "존재하지않는약품이름XYZ123"]:
        r = match_drug_name(name)
        print(f"{name!r:35s} → matched={r['matched']}, score={r['score']:.1f}, "
              f"source={r['source']}, needs_review={r['needs_review']}, "
              f"matched_name={r['matched_name']!r}")
