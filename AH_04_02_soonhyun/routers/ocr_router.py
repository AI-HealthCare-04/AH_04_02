"""
ocr_router.py — 담당: 권순현
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

# 프로젝트 루트(ocr_interface.py 위치)를 sys.path에 보장
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from ocr_interface import get_ocr_provider  # noqa: E402
from database import engine, get_session
from models import MedicalRecord, OcrResult

router = APIRouter(prefix="/ocr", tags=["OCR"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


def _bg_rag_task(record_id: int) -> None:
    """OCR 완료 직후 자동으로 RAG 가이드를 생성하는 백그라운드 태스크.

    lazy import 로 rag_router 를 불러와 순환 임포트를 방지한다.
    실패해도 이미 응답이 나간 뒤이므로 예외를 삼키고 로그만 남긴다.
    """
    try:
        from routers.rag_router import generate_guide_for_record  # lazy import
        with Session(engine) as session:
            generate_guide_for_record(record_id, session)
    except Exception as exc:
        # BackgroundTask 실패는 OCR 응답에 영향 없음. GuideResult 미생성으로 남음.
        print(f"[BackgroundTask] RAG 가이드 생성 실패 (record_id={record_id}): {exc}")


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "권순현"}


@router.post("/test")
async def stub_ocr_upload(
    patient_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    처방전 이미지를 업로드하면 CLOVA OCR로 인식하고 DB에 저장합니다.

    - patient_id: 이 처방전의 환자 id (데모용 id=1 사용)
    - 인식된 약품마다 ocr_results 행이 1개씩 생성됩니다.
    """
    # 확장자 검증
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식: {ext}")

    content = await file.read()

    # MedicalRecord 먼저 생성 (OCR 실패 시에도 업로드 기록은 남김)
    record = MedicalRecord(patient_id=patient_id, image_path=file.filename, status="processing")
    session.add(record)
    session.commit()
    session.refresh(record)

    tmp_path: str | None = None
    try:
        # 임시 파일로 저장 → ClovaOCRProvider는 파일 경로를 받음
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext.lower()) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        provider = get_ocr_provider("clova")
        ocr_result = provider.extract(tmp_path)

    except RuntimeError as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        session.add(record)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        session.add(record)
        session.commit()
        raise HTTPException(status_code=500, detail=f"OCR 처리 중 오류: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # MedicalRecord에 raw_text 업데이트
    record.raw_text = ocr_result.raw_text
    record.status = "review_required" if ocr_result.review_required else "completed"
    session.add(record)

    # 인식된 약품마다 OcrResult 행 생성
    saved_results = []
    for med in ocr_result.medications:
        row = OcrResult(
            record_id=record.id,
            drug_name=med.drug_name,
            drug_code=med.drug_code,
            dosage=med.dosage,
            frequency=med.frequency,
            diagnosis=med.diagnosis,
            drug_class=med.drug_class,
            confidence=med.confidence,
            review_required=ocr_result.review_required,
        )
        session.add(row)
        saved_results.append({
            "drug_name": med.drug_name,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "diagnosis": med.diagnosis,
            "drug_class": med.drug_class,
            "confidence": med.confidence,
            "review_required": ocr_result.review_required,
        })

    session.commit()

    # review_required 이면 사람이 확인 후 /rag/test/{record_id} 수동 호출
    # completed 이면 응답 직후 자동으로 RAG 가이드 생성
    if record.status == "completed":
        background_tasks.add_task(_bg_rag_task, record.id)

    return {
        "record_id": record.id,
        "status": record.status,
        "overall_confidence": ocr_result.overall_confidence,
        "review_required": ocr_result.review_required,
        "rag_scheduled": record.status == "completed",
        "medications": saved_results,
    }
