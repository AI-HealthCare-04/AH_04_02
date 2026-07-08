from unittest.mock import patch

import pytest
from rag_prototype.mfds_client import MfdsApiError, search_by_name

# [보류] is_officially_approved/search_permit_info가 mfds_client.py에서 주석 처리돼 있어
# (schemas.DrugPermitInfo 참고) 이 테스트들도 함께 비활성화. 나중에 풀 때 같이 복원.
# from rag_prototype.mfds_client import is_officially_approved, search_permit_info

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
    with patch("rag_prototype.mfds_client.requests.get", return_value=_FakeResponse(SAMPLE_RESPONSE)):
        results = search_by_name("활명수")

    assert len(results) == 1
    assert results[0].item_name == "활명수"
    assert results[0].item_seq == "195700020"
    assert results[0].atpn_warn_qesitm is None


def test_search_by_name_raises_on_error_code():
    with patch("rag_prototype.mfds_client.requests.get", return_value=_FakeResponse(ERROR_RESPONSE)):
        with pytest.raises(MfdsApiError):
            search_by_name("활명수")


# [보류] 허가정보 API 테스트 — mfds_client.py의 search_permit_info/is_officially_approved와
# 함께 비활성화. 나중에 코드 주석을 풀 때 여기도 같이 복원.
#
# PERMIT_RESPONSE_ACTIVE = {
#     "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
#     "body": {
#         "pageNo": 1,
#         "totalCount": 1,
#         "numOfRows": 1,
#         "items": [
#             {
#                 "ITEM_SEQ": "202106092",
#                 "ITEM_NAME": "타이레놀정500밀리그람(아세트아미노펜)",
#                 "ENTP_NAME": "켄뷰코리아판매유한회사",
#                 "ITEM_PERMIT_DATE": "20210823",
#                 "SPCLTY_PBLC": "일반의약품",
#                 "PRDUCT_TYPE": "[01140]해열.진통.소염제",
#                 "PRDUCT_PRMISN_NO": "60",
#                 "ITEM_INGR_NAME": "Acetaminophen",
#                 "PERMIT_KIND_CODE": "신고",
#                 "CANCEL_DATE": None,
#                 "CANCEL_NAME": "정상",
#             }
#         ],
#     },
# }
#
# PERMIT_RESPONSE_CANCELLED = {
#     "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
#     "body": {
#         "pageNo": 1,
#         "totalCount": 1,
#         "numOfRows": 1,
#         "items": [
#             {
#                 "ITEM_SEQ": "111111111",
#                 "ITEM_NAME": "가짜의약품정",
#                 "ENTP_NAME": "테스트제약",
#                 "ITEM_PERMIT_DATE": "20100101",
#                 "CANCEL_DATE": "20200101",
#                 "CANCEL_NAME": "취소",
#             }
#         ],
#     },
# }
#
# PERMIT_RESPONSE_EMPTY = {
#     "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
#     "body": {"pageNo": 1, "totalCount": 0, "numOfRows": 10, "items": []},
# }
#
#
# def test_search_permit_info_parses_items():
#     with patch("rag_prototype.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_ACTIVE)):
#         results = search_permit_info("타이레놀")
#
#     assert len(results) == 1
#     assert results[0].item_name == "타이레놀정500밀리그람(아세트아미노펜)"
#     assert results[0].cancel_name == "정상"
#     assert results[0].is_active is True
#
#
# def test_is_officially_approved_true_when_active():
#     with patch("rag_prototype.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_ACTIVE)):
#         assert is_officially_approved("타이레놀") is True
#
#
# def test_is_officially_approved_false_when_cancelled():
#     with patch("rag_prototype.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_CANCELLED)):
#         assert is_officially_approved("가짜의약품") is False
#
#
# def test_is_officially_approved_none_when_not_found():
#     with patch("rag_prototype.mfds_client.requests.get", return_value=_FakeResponse(PERMIT_RESPONSE_EMPTY)):
#         assert is_officially_approved("존재하지않는약") is None
