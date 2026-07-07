"""
rag_router.py — 담당: 김영혜

지금은 "흐름 확인용 가짜 데이터"만 들어있습니다.
Day4에 할 일: run_rag_stub() 안의 가짜 GuideResult 생성 부분을
실제 LangChain + gpt-4o-mini RAG 파이프라인 결과로 바꿔 끼우면 됩니다.

[7/6 추가] 로직을 run_rag_stub() 함수로 분리했습니다 — /rag/test/{record_id}(개별 테스트용)와
records_router.py(업로드→OCR→가이드 한번에 처리)가 이 함수를 같이 씁니다.
"""
from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models import OcrResult, GuideResult

router = APIRouter(prefix="/rag", tags=["RAG"])


def run_rag_stub(record_id: int, session: Session) -> GuideResult:
    """
    TODO(김영혜): 이 함수 내부를 실제 RAG 파이프라인 결과로 교체하면 됩니다.
    (medication_guide/lifestyle_guide/source_refs는 SQLite에 JSON 타입이 없어서
     json.dumps()로 문자열로 저장 — 꺼낼 때는 json.loads() 사용)
    """
    ocr_items = session.exec(
        select(OcrResult).where(OcrResult.record_id == record_id)
    ).all()
    if not ocr_items:
        raise ValueError("해당 record_id의 OCR 결과가 없어요. 먼저 OCR이 실행되어야 합니다.")

    # ↓↓↓ 여기부터 가짜 데이터 — RAG 파이프라인 완성되면 이 블록을 실제 결과로 교체 ↓↓↓
    fake_medication_guide = {
        "drugs": [
            {"drug_name": item.drug_name, "dosage_text": item.dosage, "caution": "테스트 주의사항"}
            for item in ocr_items
        ]
    }
    fake_lifestyle_guide = {
        "diagnosis": ocr_items[0].diagnosis,
        "diet": {"avoid": ["짠 음식"], "drug_specific": []},
        "exercise": {"type": "가벼운 걷기", "duration": "30분", "intensity": "낮음"},
    }
    fake_source_refs = [{"title": "테스트 출처", "url": "https://example.com"}]

    guide = GuideResult(
        record_id=record_id,
        medication_guide=json.dumps(fake_medication_guide, ensure_ascii=False),
        lifestyle_guide=json.dumps(fake_lifestyle_guide, ensure_ascii=False),
        source_refs=json.dumps(fake_source_refs, ensure_ascii=False),
    )
    # ↑↑↑ 여기까지 ↑↑↑

    session.add(guide)
    session.commit()
    session.refresh(guide)
    return guide


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "김영혜"}


@router.post("/test/{record_id}")
def stub_generate_guide(record_id: int, session: Session = Depends(get_session)):
    """RAG만 따로 테스트하고 싶을 때 쓰는 엔드포인트 (실제 흐름은 POST /records 사용)"""
    try:
        guide = run_rag_stub(record_id, session)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return {
        "guide_id": guide.id,
        "note": "⚠️ 가짜 데이터입니다 — 실제 RAG 연동 전까지만 사용",
    }
