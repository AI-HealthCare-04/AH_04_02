"""
test_drug_matcher.py — drug_matcher._match_normalized() 2단계 매칭 단위 테스트

핵심 검증:
- normalized 충돌(같은 성분명 다른 용량) 시 원본 문자열 타이브레이킹으로
  정확한 용량의 항목을 선택하는지 확인.
- match_drug() 공개 API 계약(반환 타입, 빈값 처리) 확인.
"""
from __future__ import annotations

from unittest.mock import patch

from services.drug_matcher import (
    MATCH_THRESHOLD,
    _fuzzy_fallback,
    _match_normalized,
    _normalize,
    match_drug,
)

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


# ── [2026-07-20 버그수정] 한글 용량 표기("밀리그램"/"밀리그람") 정규화 ──────────────

def test_normalize_strips_korean_gram_unit_variants():
    """HIRA 약가마스터가 같은 성분의 다른 용량끼리도 "밀리그램"/"밀리그람" 표기를
    섞어 쓴다 — 영문 단위(mg/g)만 인식하던 예전 정규식은 이 표기를 전혀 못 지웠다."""
    assert _normalize("노바스크정5밀리그램") == "노바스크정"
    assert _normalize("노바스크정5밀리그람") == "노바스크정"
    assert _normalize("리피토정10밀리그램") == "리피토정"


# ── [2026-07-27 버그수정] 주사제 농도 표기("5mg/ml") 정규화 ────────────────────

def test_normalize_strips_injection_concentration_notation():
    """[재현] 슬래시 뒤에 단위만 오고 숫자가 없는 주사제 농도 표기("5mg/ml")는
    예전엔 분자(5mg)만 지워지고 "/ml"이 그대로 남아 정규화된 이름이 지저분해졌다
    (유사도 매칭 점수가 떨어져 실제로는 맞는 약인데 검토 필요로 잘못 넘어감)."""
    assert _normalize("에피네프린주 5mg/ml") == "에피네프린주"


def test_normalize_still_strips_combo_drug_slash_dosage():
    """복합제("50/1000mg", 숫자+단위) 정규화는 회귀 없이 그대로 동작해야 한다."""
    assert _normalize("글루코파지 500mg/5mg") == "글루코파지"


def test_match_drug_prefers_exact_dosage_over_similar_length_wrong_dose():
    """[실사용 재현] "노바스크정5밀리그램"(OCR 원문)이 정답("노바스크정5밀리그람",
    표기만 다름)이 아니라 우연히 전체 문자열 유사도가 근소하게 더 높은 다른 용량
    ("노바스크정2.5밀리그램")으로 오매칭되던 문제 — 용량 숫자가 정확히 일치하는
    후보를 최우선으로 골라야 한다."""
    pool = ["노바스크정2.5밀리그램", "노바스크정5밀리그람", "노바스크정10밀리그램"]
    with patch("services.drug_matcher._names", return_value=pool):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize(n) for n in pool]):
            name, score = match_drug("노바스크정5밀리그램")
    assert name == "노바스크정5밀리그람", f"expected 5mg(그람 표기), got {name!r}"
    assert score == 1.0


# ── [2026-07-28 추가] rapidfuzz 부분 유사도 폴백 ────────────────────────────

def test_fuzzy_fallback_empty_pool_returns_zero():
    assert _fuzzy_fallback("암로디핀정5mg", []) == ("", 0.0)


def test_fuzzy_fallback_finds_substring_match():
    """OCR이 약품명을 조각내 인식해도(뒤에 잡음 텍스트 포함) 부분 유사도로 잡아낸다."""
    pool = ["글루코파지XR정500mg", "암로디핀정5mg", "리피토정10mg"]
    name, score = _fuzzy_fallback("글루코파지XR정500mg 1일2회", pool)
    assert name == "글루코파지XR정500mg"
    assert score > 0.0


def test_match_drug_fuzzy_fallback_rescues_low_difflib_score():
    """[재현] 분리 인식으로 difflib 점수가 임계값 미만이 되어도, 부분 문자열이
    충분히 일치하면 rapidfuzz 폴백이 정답을 찾아 needs_review 오탐을 줄인다."""
    pool = ["글루코파지XR정500mg"]
    ocr_text = "관련없는잡음텍스트 글루코파지XR정500mg"
    with patch("services.drug_matcher._names", return_value=pool):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize(n) for n in pool]):
            name, score = match_drug(ocr_text)
    assert name == "글루코파지XR정500mg"
    assert score >= MATCH_THRESHOLD


def test_match_drug_fuzzy_fallback_not_used_when_difflib_already_confident():
    """difflib 매칭이 이미 MATCH_THRESHOLD 이상이면(정확 매칭 등) 폴백이 끼어들어
    기존 스코어(1.0)를 바꾸지 않는다 — 기존 회귀 테스트들의 정확 스코어 보존."""
    pool = ["메트포르민정500mg"]
    with patch("services.drug_matcher._names", return_value=pool):
        with patch("services.drug_matcher._norm_names", return_value=[_normalize(n) for n in pool]):
            name, score = match_drug("메트포르민정500mg")
    assert name == "메트포르민정500mg"
    assert score == 1.0
