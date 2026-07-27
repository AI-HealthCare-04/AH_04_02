"""
test_drug_reference.py — get_drug_name_list()이 성분명 하드코딩 사전을 후보로
안 섞는지 검증 (2026-07-20, REQ-037 관련 버그 수정)

_HARDCODED_FALLBACK(services/drug_reference.py)은 get_drug_class()의 "약효분류
부분일치" 판정 전용 사전이라 키가 "메트포르민"처럼 성분명일 뿐 실제 완전한 제품명이
아니다. get_drug_name_list()가 이 키들도 매칭 후보(drug_matcher.py)로 함께 섞었던
탓에, OCR이 "메트포르민정500mg"을 읽어도 이 성분명과 유사도 0.9 이상으로 매칭돼
(needs_review=False) OcrResult.display_name이 원문(전체 제품명)보다 정보가 적은
성분명을 오히려 우선 표시했다.
"""
from unittest.mock import patch

import pandas as pd
import services.drug_reference as drug_reference
from services.drug_reference import _HARDCODED_FALLBACK, _clean_product_name, get_drug_name_list


def test_get_drug_name_list_excludes_hardcoded_fallback_keys():
    """HIRA/e약은요 데이터가 전혀 없어도(하드코딩만 남는 상황) 결과가 비어야 한다 —
    _HARDCODED_FALLBACK 키(성분명)가 더 이상 매칭 후보로 섞이지 않는지 확인."""
    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", None),
        patch("services.drug_reference._load_drug_table", return_value=[]),
    ):
        names = get_drug_name_list()

    assert names == []
    for ingredient_name in _HARDCODED_FALLBACK:
        assert ingredient_name not in names


def test_metformin_ocr_text_does_not_match_bare_ingredient_name():
    """[재현] "메트포르민정500mg"이 성분명 "메트포르민"과 오매칭돼 needs_review=False로
    확정되던 문제 — 하드코딩 사전만 남은 상황에서는 매칭 후보 자체가 없어 낮은 점수로
    떨어지고(needs_review=True), 원문이 그대로 표시 대상으로 유지돼야 한다."""
    from services.drug_matcher import MATCH_THRESHOLD, match_drug

    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", None),
        patch("services.drug_reference._load_drug_table", return_value=[]),
        patch("services.drug_matcher._cached_names", None),
        patch("services.drug_matcher._cached_norm_names", None),
    ):
        _, score = match_drug("메트포르민정500mg")

    assert score < MATCH_THRESHOLD


def test_clean_product_name_strips_parenthetical_ingredient_suffix():
    assert _clean_product_name("태극암로디핀정(암로디핀말레산염)") == "태극암로디핀정"
    assert _clean_product_name("타이레놀정500밀리그람(아세트아미노펜)") == "타이레놀정500밀리그람"
    assert _clean_product_name("낙센정(나프록센)") == "낙센정"
    assert _clean_product_name("암로사정10밀리그램") == "암로사정10밀리그램"  # 괄호 없으면 그대로


def test_get_drug_name_list_uses_full_emed_item_name_not_over_stripped_norm():
    """[재현] entry["norm"](drug_reference.py 자체 약효분류용, 용량·제형까지 제거)이
    아니라 entry["item_name"](원본 전체 품목명)이 후보로 쓰여야 한다."""
    fake_table = [
        {"item_name": "휴온스암로디핀정5mg", "norm": "휴온스암로디핀", "efcy": ""},
    ]
    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", None),
        patch("services.drug_reference._load_drug_table", return_value=fake_table),
    ):
        names = get_drug_name_list()

    assert "휴온스암로디핀정5mg" in names
    assert "휴온스암로디핀" not in names


def test_lookup_hira_by_name_treats_patch_form_as_direct_match():
    """[2026-07-27 버그수정, 재현] 짧은 성분명("리도카인")과 그 성분의 실제 패치
    제품("리도카인패치8mg")이 둘 다 "startswith" 후보에 걸릴 때, _FORM_STARTERS에
    "패"(패치/패취)가 빠져 있으면 둘 다 "직접 일치"로 인정 안 돼 최단이름 휴리스틱이
    (엉뚱하게) 더 짧은 성분명 쪽을 골라버렸다 — 이제는 제형이 이어지는 쪽을 직접
    일치로 인정해 올바른 제품을 골라야 한다."""
    from services.drug_reference import _lookup_hira_by_name

    fake_df = pd.DataFrame(
        {
            "한글상품명": ["리도카인", "리도카인패치8mg"],
            "국제표준코드(ATC코드)": ["BARE-INGREDIENT-CODE", "PATCH-CODE"],
        }
    )
    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", fake_df),
    ):
        code = _lookup_hira_by_name("리도카인")

    assert code == "PATCH-CODE"


def test_lookup_hira_by_name_treats_eye_drop_form_as_direct_match():
    """위와 동일한 문제를 점안액 제형으로 재현 — "점"이 _FORM_STARTERS에 빠져 있었다."""
    from services.drug_reference import _lookup_hira_by_name

    fake_df = pd.DataFrame(
        {
            "한글상품명": ["히알루론산", "히알루론산점안액0.1%"],
            "국제표준코드(ATC코드)": ["BARE-INGREDIENT-CODE", "EYE-DROP-CODE"],
        }
    )
    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", fake_df),
    ):
        code = _lookup_hira_by_name("히알루론산")

    assert code == "EYE-DROP-CODE"


def test_match_drug_prefers_exact_prefix_match_over_similar_length_wrong_brand():
    """[실제 재현] "태극암로디핀정(암로디핀말레산염)"이 후보 풀에 있을 때, OCR이
    "태극암로디핀정"을 읽으면 그 항목과 정확히 매칭돼야 한다 — 예전엔
    SequenceMatcher.ratio()가 괄호 부기 때문에 길이 차이로 점수를 깎아서, 우연히
    총 길이가 비슷한 완전히 다른 브랜드("파마킹암로디핀정")가 더 높은 점수로 이겼다."""
    from services.drug_matcher import match_drug

    fake_df = pd.DataFrame(
        {"한글상품명": ["태극암로디핀정(암로디핀말레산염)", "파마킹암로디핀정"]}
    )
    with (
        patch("services.drug_reference._load_hira"),
        patch.object(drug_reference, "_hira_name_df", fake_df),
        patch("services.drug_reference._load_drug_table", return_value=[]),
        patch("services.drug_matcher._cached_names", None),
        patch("services.drug_matcher._cached_norm_names", None),
    ):
        name, score = match_drug("태극암로디핀정")

    assert name == "태극암로디핀정"
    assert score == 1.0
