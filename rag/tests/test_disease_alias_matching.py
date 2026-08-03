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
