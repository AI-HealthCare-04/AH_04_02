from unittest.mock import patch

import pytest
from rag.mfds_client import (
    MfdsApiError,
    is_officially_approved,
    parse_doc_sections,
    search_by_name,
    search_permit_detail,
    search_permit_info,
)

SAMPLE_RESPONSE = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {
        "pageNo": 1,
        "totalCount": 1,
        "numOfRows": 1,
        "items": [
            {
                "entpName": "동화약품(주)",
                "itemName": "활명수",
                "itemSeq": "195700020",
                "efcyQesitm": "소화불량에 사용합니다.",
                "useMethodQesitm": "1회 1병 복용합니다.",
                "atpnWarnQesitm": None,
                "atpnQesitm": "임부는 상의하십시오.",
                "intrcQesitm": None,
                "seQesitm": None,
                "depositMethodQesitm": "실온 보관하십시오.",
                "openDe": "20210129",
                "updateDe": "2024-05-09",
                "itemImage": None,
                "bizrno": "1108100102",
            }
        ],
    },
}

ERROR_RESPONSE = {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}, "body": {}}


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_search_by_name_parses_items():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(SAMPLE_RESPONSE)):
        results = search_by_name("활명수")

    assert len(results) == 1
    assert results[0].item_name == "활명수"
    assert results[0].item_seq == "195700020"
    assert results[0].atpn_warn_qesitm is None


def test_search_by_name_raises_on_error_code():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(ERROR_RESPONSE)):
        with pytest.raises(MfdsApiError):
            search_by_name("활명수")

# DUR 병용금기 관련 테스트는 API가 아니라 로컬 CSV 조회(dur_master.py)로 옮겨졌다 —
# test_dur_master.py 참고 (contract.md §7).


# [2026-07-14] 활용신청 승인되어 재활성화 — 실제 API 호출로 필드명 재확인 완료.
PERMIT_RESPONSE_ACTIVE = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {
        "pageNo": 1,
        "totalCount": 1,
        "numOfRows": 1,
        "items": [
            {
                "ITEM_SEQ": "202106092",
                "ITEM_NAME": "타이레놀정500밀리그람(아세트아미노펜)",
                "ENTP_NAME": "켄뷰코리아판매유한회사",
                "ITEM_PERMIT_DATE": "20210823",
                "SPCLTY_PBLC": "일반의약품",
                "PRDUCT_TYPE": "[01140]해열.진통.소염제",
                "PRDUCT_PRMISN_NO": "60",
                "ITEM_INGR_NAME": "Acetaminophen",
                "PERMIT_KIND_CODE": "신고",
                "CANCEL_DATE": None,
                "CANCEL_NAME": "정상",
            }
        ],
    },
}

PERMIT_RESPONSE_CANCELLED = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {
        "pageNo": 1,
        "totalCount": 1,
        "numOfRows": 1,
        "items": [
            {
                "ITEM_SEQ": "111111111",
                "ITEM_NAME": "가짜의약품정",
                "ENTP_NAME": "테스트제약",
                "ITEM_PERMIT_DATE": "20100101",
                "CANCEL_DATE": "20200101",
                "CANCEL_NAME": "취소",
            }
        ],
    },
}

PERMIT_RESPONSE_EMPTY = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {"pageNo": 1, "totalCount": 0, "numOfRows": 10, "items": []},
}


def test_search_permit_info_parses_items():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_ACTIVE)):
        results = search_permit_info("타이레놀")

    assert len(results) == 1
    assert results[0].item_name == "타이레놀정500밀리그람(아세트아미노펜)"
    assert results[0].cancel_name == "정상"
    assert results[0].is_active is True


def test_is_officially_approved_true_when_active():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_ACTIVE)):
        assert is_officially_approved("타이레놀") is True


def test_is_officially_approved_false_when_cancelled():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_CANCELLED)):
        assert is_officially_approved("가짜의약품") is False


def test_is_officially_approved_none_when_not_found():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_EMPTY)):
        assert is_officially_approved("존재하지않는약") is None


# [2026-07-14 추가] 상세정보(getDrugPrdtPrmsnDtlInq06) — NB_DOC_DATA(사용상의주의사항)는
# 실제 API 응답과 동일하게 <DOC><SECTION><ARTICLE>...</ARTICLE></SECTION></DOC> 구조이며,
# PARAGRAPH 안에 표 마크업(CDATA로 온 HTML)이 섞여 있는 경우까지 재현한다.
NB_DOC_DATA_SAMPLE = """<DOC title="사용상의주의사항" type="NB">
<SECTION title="">
<ARTICLE title="1. 경고">
<PARAGRAPH tagName="p">간손상을 일으킬 수 있으므로 정해진 용법·용량을 지키십시오.</PARAGRAPH>
</ARTICLE>
<ARTICLE title="2. 다음 환자에는 투여하지 말 것">
<PARAGRAPH tagName="p"><![CDATA[이 약 또는 이 약의 구성성분에 과민증 환자<table><tbody><tr><td>구분</td></tr></tbody></table>]]></PARAGRAPH>
</ARTICLE>
</SECTION>
</DOC>"""

PERMIT_DETAIL_RESPONSE = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {
        "pageNo": 1,
        "totalCount": 1,
        "numOfRows": 1,
        "items": [
            {
                "ITEM_SEQ": "202106092",
                "ITEM_NAME": "타이레놀정500밀리그람(아세트아미노펜)",
                "ENTP_NAME": "켄뷰코리아판매유한회사",
                "NB_DOC_DATA": NB_DOC_DATA_SAMPLE,
            }
        ],
    },
}

PERMIT_DETAIL_RESPONSE_NO_PRECAUTIONS = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {
        "pageNo": 1,
        "totalCount": 1,
        "numOfRows": 1,
        "items": [
            {
                "ITEM_SEQ": "202106092",
                "ITEM_NAME": "타이레놀정500밀리그람(아세트아미노펜)",
                "NB_DOC_DATA": None,
            }
        ],
    },
}


def test_search_permit_detail_parses_items():
    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_DETAIL_RESPONSE)):
        results = search_permit_detail("타이레놀")

    assert len(results) == 1
    assert results[0].item_name == "타이레놀정500밀리그람(아세트아미노펜)"
    assert results[0].nb_doc_data == NB_DOC_DATA_SAMPLE


def test_parse_doc_sections_extracts_titles_and_strips_embedded_html():
    sections = parse_doc_sections(NB_DOC_DATA_SAMPLE)

    assert sections == [
        ("1. 경고", "간손상을 일으킬 수 있으므로 정해진 용법·용량을 지키십시오."),
        ("2. 다음 환자에는 투여하지 말 것", "이 약 또는 이 약의 구성성분에 과민증 환자 구분"),
    ]


def test_parse_doc_sections_returns_empty_list_when_no_data():
    assert parse_doc_sections(None) == []
    assert parse_doc_sections("") == []


def test_parse_doc_sections_returns_empty_list_on_invalid_xml():
    assert parse_doc_sections("<DOC><ARTICLE title=") == []


# ── 디스크 캐시 동작 검증 ────────────────────────────────────────────────────
# conftest._isolate_mfds_disk_cache(autouse)가 각 테스트에 격리된 임시 캐시를 주입한다.

def test_search_by_name_cache_hit_skips_api():
    """같은 인자로 두 번 호출 시 두 번째는 requests.get을 호출하지 않아야 한다."""
    import rag.mfds_client as mfds_mod

    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(SAMPLE_RESPONSE)):
        search_by_name("활명수")

    with patch("rag.mfds_client.requests.get") as mock_get:
        result = search_by_name("활명수")

    mock_get.assert_not_called()
    assert result[0].item_name == "활명수"


def test_search_by_name_cache_miss_stores_result():
    """API 응답을 캐시에 저장해 다음 호출에서 재사용할 수 있어야 한다."""
    import rag.mfds_client as mfds_mod

    with patch("rag.mfds_client.requests.get", return_value=_FakeResponse(SAMPLE_RESPONSE)):
        search_by_name("활명수")

    cached = mfds_mod._disk_cache.get("mfds.search_by_name|활명수|10|1")
    assert cached is not None
    assert len(cached) == 1
    assert cached[0]["item_name"] == "활명수"


def test_search_by_name_falls_back_to_api_on_cache_read_error():
    """캐시 read가 예외를 던져도 API 호출로 폴백되어 정상 결과를 반환해야 한다."""
    import rag.mfds_client as mfds_mod

    with (
        patch.object(mfds_mod._disk_cache, "get", side_effect=Exception("disk error")),
        patch("rag.mfds_client.requests.get", return_value=_FakeResponse(SAMPLE_RESPONSE)) as mock_api,
    ):
        results = search_by_name("활명수")

    mock_api.assert_called_once()
    assert results[0].item_name == "활명수"
