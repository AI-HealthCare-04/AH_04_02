"""
test_drug_matcher.py — drug_matcher._match_normalized() 2단계 매칭 단위 테스트

핵심 검증:
- normalized 충돌(같은 성분명 다른 용량) 시 원본 문자열 타이브레이킹으로
  정확한 용량의 항목을 선택하는지 확인.
- match_drug() 공개 API 계약(반환 타입, 빈값 처리) 확인.
"""
from __future__ import annotations

from unittest.mock import patch

from services.drug_matcher import MATCH_THRESHOLD, _match_normalized, _normalize, match_drug


# ── _normalize 단위 테스트 ───────────────────────────────────────────────────

def test_normalize_removes_dosage_unit():
    assert _normalize("메트포르민정500mg") == "메트포르민정"


def test_normalize_keeps_form_without_leading_number():
    # '정' 앞에 숫자 없으면 제형 키워드는 남아야 한다
    assert _normalize("암로디핀정5mg") == "암로디핀정"


def test_normalize_removes_percent_dosage():
    assert _normalize("케어스킨로션2.5%") == "케어스킨로션"


def test_normalize_collapses_whitespace():
    assert _normalize("암로디핀  5mg") == "암로디핀"


# ── _match_normalized 2단계 매칭 ────────────────────────────────────────────

def _pool(*names):
    """테스트용 (raw_pool, norm_pool) 생성 헬퍼."""
    return list(names), [_normalize(n) for n in names]


def test_exact_raw_match_returns_correct_dosage():
    """사전에 250/500/1000mg 세 개 있을 때 500mg 입력 → 500mg 반환."""
    raw_pool, norm_pool = _pool(
        "메트포르민정250mg",
        "메트포르민정500mg",
        "메트포르민정1000mg",
    )
    matched, score = _match_normalized("메트포르민정", "메트포르민정500mg", raw_pool, norm_pool)
    assert matched == "메트포르민정500mg", f"expected 500mg, got {matched!r}"
    assert score == 1.0


def test_exact_raw_match_250mg():
    """250mg 입력 → 250mg 반환."""
    raw_pool, norm_pool = _pool(
        "메트포르민정250mg",
        "메트포르민정500mg",
        "메트포르민정1000mg",
    )
    matched, score = _match_normalized("메트포르민정", "메트포르민정250mg", raw_pool, norm_pool)
    assert matched == "메트포르민정250mg", f"expected 250mg, got {matched!r}"
    assert score == 1.0


def test_exact_raw_match_1000mg():
    """1000mg 입력 → 1000mg 반환."""
    raw_pool, norm_pool = _pool(
        "메트포르민정250mg",
        "메트포르민정500mg",
        "메트포르민정1000mg",
    )
    matched, score = _match_normalized("메트포르민정", "메트포르민정1000mg", raw_pool, norm_pool)
    assert matched == "메트포르민정1000mg", f"expected 1000mg, got {matched!r}"
    assert score == 1.0


def test_no_collision_single_entry():
    """충돌 없는 단일 항목 — 기존 동작 유지."""
    raw_pool, norm_pool = _pool("암로디핀정5mg")
    matched, score = _match_normalized("암로디핀정", "암로디핀정5mg", raw_pool, norm_pool)
    assert matched == "암로디핀정5mg"
    assert score == 1.0


def test_partial_match_no_exact_raw():
    """OCR 입력이 사전에 없을 때 가장 유사한 항목 반환."""
    raw_pool, norm_pool = _pool("암로디핀정5mg", "로자탄정50mg")
    matched, score = _match_normalized("암로디핀", "암로디핀", raw_pool, norm_pool)
    assert "암로디핀" in matched
    assert 0.0 < score <= 1.0


# ── match_drug() 공개 API ───────────────────────────────────────────────────

def test_match_drug_empty_string():
    assert match_drug("") == ("", 0.0)


def test_match_drug_returns_tuple_float():
    with patch("services.drug_matcher._names", return_value=["암로디핀정5mg"]):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize("암로디핀정5mg")]):
            name, score = match_drug("암로디핀정5mg")
    assert isinstance(name, str)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_match_drug_score_rounded_to_4():
    """score는 소수점 4자리 이하로 반환된다."""
    with patch("services.drug_matcher._names", return_value=["암로디핀정5mg"]):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize("암로디핀정5mg")]):
            _, score = match_drug("암로디핀정5mg")
    assert score == round(score, 4)


def test_match_drug_exact_pool_match():
    """사전에 정확히 일치하는 항목이 있을 때 score == 1.0."""
    with patch("services.drug_matcher._names", return_value=["메트포르민정500mg"]):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize("메트포르민정500mg")]):
            name, score = match_drug("메트포르민정500mg")
    assert name == "메트포르민정500mg"
    assert score == 1.0


def test_match_drug_collision_500mg_wins():
    """사전에 250/500/1000mg 세 개 있을 때 match_drug("메트포르민정500mg") → 500mg."""
    pool = ["메트포르민정250mg", "메트포르민정500mg", "메트포르민정1000mg"]
    with patch("services.drug_matcher._names", return_value=pool):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize(n) for n in pool]):
            name, score = match_drug("메트포르민정500mg")
    assert name == "메트포르민정500mg", f"expected 500mg, got {name!r}"
    assert score == 1.0


def test_match_threshold_constant():
    assert MATCH_THRESHOLD == 0.7