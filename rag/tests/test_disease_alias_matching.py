from unittest.mock import patch

from langchain_core.documents import Document
from rag.rag_chain import (
    _candidate_kdca_titles,
    _lifestyle_context_items,
    _title_matches_diagnosis,
)


def _ckd_lifestyle_doc() -> Document:
    return Document(
        page_content="[만성콩팥병 - 생활습관 관리] 싱겁게 먹고 정기적으로 진료받습니다.",
        metadata={
            "doc_type": "kdca_health_info",
            "cntnts_sn": "5457",
            "title": "만성콩팥병",
            "section_name": "생활습관 관리",
            "section_sn": "10",
            "index": 0,
            "source": "질병관리청 국가건강정보포털",
        },
    )


def _lifestyle_doc(title: str, content_id: str) -> Document:
    return Document(
        page_content=f"[{title} - 생활습관 관리] {title} 생활습관 안내입니다.",
        metadata={
            "doc_type": "kdca_health_info",
            "cntnts_sn": content_id,
            "title": title,
            "section_name": "생활습관 관리",
            "section_sn": "10",
            "index": 0,
            "source": "질병관리청 국가건강정보포털",
        },
    )


def test_registered_synonyms_match_the_same_disease():
    assert _title_matches_diagnosis("만성콩팥병", "만성 신장병")
    assert _title_matches_diagnosis("이상지질혈증", "고지혈증 환자")
    assert _title_matches_diagnosis("당뇨병", "제2형 당뇨병 진단")


def test_unregistered_spacing_and_status_variants_still_match():
    assert _title_matches_diagnosis("골다공증", "골다공증 진단 있음")
    assert _title_matches_diagnosis("역류성식도염", "역류성 식도염 환자")


def test_candidate_titles_expand_kidney_disease_synonyms():
    candidates = _candidate_kdca_titles("만성 신장병")
    assert candidates[0] == "만성 신장병"
    assert "만성콩팥병" in candidates
    assert "CKD" in candidates


def test_lifestyle_lookup_finds_kdca_title_through_synonym():
    calls = []

    def exact_title_search(title: str):
        calls.append(title)
        return [_ckd_lifestyle_doc()] if title == "만성콩팥병" else []

    with (
        patch("rag.rag_chain.search_kdca_health_info_by_title", side_effect=exact_title_search),
        patch("rag.rag_chain.search_kdca_health_info") as semantic_search,
        patch("rag.rag_chain.search_by_disease") as curated_search,
    ):
        items = _lifestyle_context_items("만성 신장병")

    assert "만성콩팥병" in calls
    semantic_search.assert_not_called()
    curated_search.assert_not_called()
    assert items[0]["source_ref"].disease == "만성콩팥병"
    assert items[0]["source_ref"].source == "질병관리청 국가건강정보포털"


def test_compound_diagnosis_keeps_lifestyle_guides_for_each_disease():
    docs = {
        "고혈압": [_lifestyle_doc("고혈압", "100")],
        "당뇨병": [_lifestyle_doc("당뇨병", "200")],
    }

    with (
        patch("rag.rag_chain.search_kdca_health_info_by_title", side_effect=lambda title: docs.get(title, [])),
        patch("rag.rag_chain.search_kdca_health_info", return_value=[]),
        patch("rag.rag_chain.search_by_disease") as curated_search,
    ):
        items = _lifestyle_context_items("고혈압, 당뇨병")

    curated_search.assert_not_called()
    assert {item["source_ref"].disease for item in items} == {"고혈압", "당뇨병"}


def test_unregistered_disease_matches_full_title_list_through_variant_spelling():
    """DIAGNOSIS_DISEASE_ALIASES에 없는 질환(천식)도, 표기가 KDCA title과 정확히
    같지 않으면(예: "기관지 천식") 663개 제목 전체 대조를 통해 찾아진다 —
    질환마다 동의어를 수동 등록하지 않아도 되는 게 이 일반화의 핵심이다."""
    calls = []

    def exact_title_search(title: str):
        calls.append(title)
        return [_lifestyle_doc("천식", "6784")] if title == "천식" else []

    with (
        patch("rag.rag_chain._all_kdca_titles", return_value=("천식", "당뇨병")),
        patch("rag.rag_chain.search_kdca_health_info_by_title", side_effect=exact_title_search),
        patch("rag.rag_chain.search_kdca_health_info") as semantic_search,
        patch("rag.rag_chain.search_by_disease") as curated_search,
    ):
        items = _lifestyle_context_items("기관지 천식")

    assert "천식" in calls
    semantic_search.assert_not_called()
    curated_search.assert_not_called()
    assert items[0]["source_ref"].disease == "천식"


def test_exact_title_match_skips_full_title_list_scan():
    """진단명이 이미 KDCA title과 정확히 일치하면(예: "고혈압"), 663개 전체 스캔
    단계는 실행되지 않는다 — 기존 정확 매칭 동작에 이번 일반화가 영향을 주지 않음을
    보장하는 회귀 테스트다."""
    calls = []

    def exact_title_search(title: str):
        calls.append(title)
        return [_lifestyle_doc("고혈압", "100")] if title == "고혈압" else []

    with (
        patch("rag.rag_chain._all_kdca_titles", return_value=("고혈압", "노인 고혈압")),
        patch("rag.rag_chain.search_kdca_health_info_by_title", side_effect=exact_title_search),
        patch("rag.rag_chain.search_kdca_health_info") as semantic_search,
    ):
        items = _lifestyle_context_items("고혈압")

    # "노인 고혈압"은 _title_matches_diagnosis("노인 고혈압", "고혈압")이 True더라도,
    # 정확 매칭(1단계)에서 이미 찾았으므로 전체 스캔(2단계)까지 안 가서 조회되지 않는다.
    assert calls == ["고혈압"]
    semantic_search.assert_not_called()
    assert items[0]["source_ref"].disease == "고혈압"


def test_multiple_matching_titles_stop_at_the_first_one_found():
    """[버그수정 회귀 테스트] 정규화 후 부분일치 특성상 하나의 진단명이 여러 KDCA
    title과 동시에 매칭될 수 있다(예: "알레르기성 천식"이 "알레르기"와 "천식" 둘 다에
    매칭) — 매칭되는 title을 전부 순회하며 계속 누적하면 서로 다른(연관은 있지만
    별개인) 주제가 한 결과에 섞이고, title마다 실제 벡터DB 조회가 나가 과도한 순차
    호출이 쌓인다. 바로 위 exact-candidate 루프와 동일하게, 문서를 실제로 찾은 첫
    title에서 멈춰야 한다."""
    calls = []

    def exact_title_search(title: str):
        calls.append(title)
        if title == "알레르기":
            return [_lifestyle_doc("알레르기", "111")]
        if title == "천식":
            return [_lifestyle_doc("천식", "222")]
        return []

    with (
        patch("rag.rag_chain._all_kdca_titles", return_value=("알레르기", "천식")),
        patch("rag.rag_chain.search_kdca_health_info_by_title", side_effect=exact_title_search),
        patch("rag.rag_chain.search_kdca_health_info") as semantic_search,
        patch("rag.rag_chain.search_by_disease") as curated_search,
    ):
        items = _lifestyle_context_items("알레르기성 천식")

    # 1단계(exact-candidate 루프)가 진단명 원문("알레르기성 천식") 자체를 후보로 먼저
    # 한 번 시도하고(매칭 없음), 2단계(전체 title 스캔)에서 "알레르기"를 찾으면 거기서
    # 멈춰야 한다 — "천식"까지 순회하면 안 된다.
    assert calls == ["알레르기성 천식", "알레르기"]
    semantic_search.assert_not_called()
    curated_search.assert_not_called()
    assert {item["source_ref"].disease for item in items} == {"알레르기"}
