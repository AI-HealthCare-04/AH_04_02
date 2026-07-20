"""
GET /ocr/drug-info의 matched_name이 실제로 유사한 약품명일 때만 채워지는지 검증한다.

get_drug_info()의 atc_pattern/fallback은 "이름에 특정 키워드가 포함되는가"만 보는
부분일치라, "졸피뎀아무말"처럼 실제 약품명 뒤에 엉뚱한 말을 붙여도 통과해버렸다 —
PrescriptionReview.tsx가 이 값으로 "약품명이 실제로 맞는지" 판단하므로, match_drug()의
전체 문자열 유사도(MATCH_THRESHOLD)로 판정하도록 바꿨다.
"""
from fastapi.testclient import TestClient

from main import app
import routers.ocr_router as ocr_router

client = TestClient(app, raise_server_exceptions=False)


def test_high_similarity_returns_matched_name(monkeypatch):
    monkeypatch.setattr(ocr_router, "match_drug", lambda name: ("졸피뎀", 1.0))
    r = client.get("/ocr/drug-info", params={"drug_name": "졸피뎀"})
    assert r.status_code == 200
    assert r.json()["matched_name"] == "졸피뎀"


def test_low_similarity_returns_none(monkeypatch):
    # 실제 약품명 뒤에 엉뚱한 말이 붙어 전체 유사도가 임계값 아래로 떨어지는 경우
    monkeypatch.setattr(ocr_router, "match_drug", lambda name: ("졸피뎀", 0.5))
    r = client.get("/ocr/drug-info", params={"drug_name": "졸피뎀아무말"})
    assert r.status_code == 200
    assert r.json()["matched_name"] is None
