"""
rag_router.py — 담당: 김영혜

지금은 "흐름 확인용 가짜 데이터"만 들어있습니다.
Day4에 할 일: stub_generate_guide() 안의 가짜 GuideResult 생성 부분을
실제 LangChain + gpt-4o-mini RAG 파이프라인 결과로 바꿔 끼우면 됩니다.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models import OcrResult, GuideResult

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "김영혜"}


@router.post("/test/{record_id}")
def stub_generate_guide(record_id: int, session: Session = Depends(get_session)):
    """
    임시 stub 엔드포인트.
    지금 하는 일: record_id로 OCR 결과를 찾아서 → 가짜 가이드 1건 생성
    TODO(김영혜): 아래 "가짜 데이터" 부분을 실제 RAG 파이프라인 결과로 교체
    (medication_guide/lifestyle_guide/source_refs는 SQLite에 JSON 타입이 없어서
     json.dumps()로 문자열로 저장 — 꺼낼 때는 json.loads() 사용)
    """
    ocr_items = session.exec(
        select(OcrResult).where(OcrResult.record_id == record_id)
    ).all()
    if not ocr_items:
        raise HTTPException(404, "해당 record_id의 OCR 결과가 없어요. 먼저 /ocr/test를 호출하세요.")

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

    return {
        "guide_id": guide.id,
        "note": "⚠️ 가짜 데이터입니다 — 실제 RAG 연동 전까지만 사용",
    }
