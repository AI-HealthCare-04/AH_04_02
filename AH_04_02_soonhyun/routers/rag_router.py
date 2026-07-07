"""
rag_router.py — 담당: 김영혜

Day5 구조 변경:
  generate_guide_for_record() 가 핵심 로직을 담당하고,
  엔드포인트 stub_generate_guide() 는 이 함수를 감싸기만 합니다.

  ocr_router.py 의 BackgroundTask 가 generate_guide_for_record() 를 직접 임포트해
  호출하므로, ★ 이 함수의 이름·시그니처(record_id, session)는 바꾸지 마세요 ★.
  내부 RAG 파이프라인 교체는 이 함수 안에서만 하면 됩니다.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models import OcrResult, GuideResult

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "김영혜"}


def generate_guide_for_record(record_id: int, session: Session) -> Optional[dict]:
    """
    RAG 가이드 생성 핵심 로직.

    ★ ocr_router.py 의 BackgroundTask 가 이 함수를 직접 임포트해 사용합니다.
      - 함수 이름 변경 금지
      - 첫 두 인자 (record_id: int, session: Session) 변경 금지
      - 내부 구현(RAG 파이프라인 교체)은 자유롭게 수정 가능
    OCR 결과가 없으면 None 반환 (BackgroundTask 컨텍스트에서도 안전).

    TODO(김영혜): ↓↓↓ "가짜 데이터" 블록을 실제 LangChain + gpt-4o-mini RAG 결과로 교체 ↓↓↓
    (medication_guide/lifestyle_guide/source_refs 는 SQLite JSON 미지원으로
     json.dumps() 로 저장 — 조회 시 json.loads() 사용)
    """
    ocr_items = session.exec(
        select(OcrResult).where(OcrResult.record_id == record_id)
    ).all()
    if not ocr_items:
        return None

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
    return {"guide_id": guide.id}


@router.post("/test/{record_id}")
def stub_generate_guide(record_id: int, session: Session = Depends(get_session)):
    """
    OCR 완료된 record_id 로 RAG 가이드를 생성합니다.
    (BackgroundTask 로도 자동 호출되지만, 수동 호출·재생성에도 쓸 수 있습니다.)
    """
    result = generate_guide_for_record(record_id, session)
    if result is None:
        raise HTTPException(404, "해당 record_id의 OCR 결과가 없어요. 먼저 /ocr/test를 호출하세요.")
    result["note"] = "⚠️ 가짜 데이터입니다 — 실제 RAG 연동 전까지만 사용"
    return result
