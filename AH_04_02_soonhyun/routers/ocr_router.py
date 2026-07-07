"""
ocr_router.py — 담당: 권순현
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import requests.exceptions
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
    # 파일명·확장자 검증
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다. 파일을 다시 선택해주세요.")
    _, ext = os.path.splitext(filename)
    if ext.lower() not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다: '{ext or '확장자 없음'}'. "
                   f"지원 형식: {', '.join(sorted(_ALLOWED_EXT))}",
        )

    content = await file.read()

    # 빈 파일 검증 (MedicalRecord 생성 전에 차단 — DB에 불필요한 행 남기지 않음)
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

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

    except requests.exceptions.Timeout as exc:
        # CLOVA API가 15초 내 응답 없음 (ocr_interface.py timeout=15)
        record.status = "failed"
        record.failure_reason = "CLOVA API 타임아웃"
        session.add(record); session.commit()
        raise HTTPException(
            status_code=504,
            detail="CLOVA OCR API 응답 시간이 초과됐습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        # 네트워크 단절, DNS 실패 등
        record.status = "failed"
        record.failure_reason = "CLOVA API 연결 실패"
        session.add(record); session.commit()
        raise HTTPException(
            status_code=503,
            detail="CLOVA OCR API에 연결할 수 없습니다. 네트워크 상태를 확인해주세요.",
        ) from exc
    except requests.exceptions.HTTPError as exc:
        # CLOVA 서버가 4xx/5xx 반환 (잘못된 키, 할당량 초과 등)
        status_code = exc.response.status_code if exc.response is not None else "?"
        record.status = "failed"
        record.failure_reason = f"CLOVA API HTTP {status_code} 오류"
        session.add(record); session.commit()
        raise HTTPException(
            status_code=502,
            detail=f"CLOVA OCR API가 오류를 반환했습니다 (HTTP {status_code}). API 키·할당량을 확인해주세요.",
        ) from exc
    except RuntimeError as exc:
        # CLOVA_OCR_API_URL / SECRET_KEY 미설정 등 설정 오류
        record.status = "failed"
        record.failure_reason = str(exc)
        session.add(record); session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        session.add(record); session.commit()
        raise HTTPException(status_code=500, detail=f"OCR 처리 중 예기치 못한 오류가 발생했습니다: {exc}") from exc
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
