"""
ocr_router.py — 담당: 권순현

[7/8 통합] 권순현님 PR #9의 실제 CLOVA 연동 로직을 backend/ 구조에 맞춰 통합.
핵심 로직을 run_ocr() 함수로 분리해서 이 파일의 /ocr/test(개별 테스트용)와
records_router.py(실제 업로드→OCR→가이드 한 번에 처리) 양쪽에서 재사용합니다.

[7/8 추가] OCR_PROVIDER 환경변수로 clova/mock 전환 가능하게 함
— CLOVA 키 발급 전까지 팀 전체가 파이프라인을 mock으로 테스트할 수 있게 하기 위함
  (.env에 OCR_PROVIDER=mock 추가하면 됨, 없으면 기본값 clova)
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import requests.exceptions
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

# ocr_interface.py 등은 backend/ 루트(main.py와 같은 위치)에 있어서 별도 sys.path 조작 불필요
# (uvicorn을 backend/ 폴더에서 실행하면 그 폴더 자체가 이미 import 루트가 됨)
_ROOT = Path(__file__).parent.parent
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from services.ocr_interface import get_ocr_provider  # noqa: E402
from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from services.drug_matcher import MATCH_THRESHOLD, match_drug
from models import MedicalRecord, OcrResult
from services.drug_reference import get_drug_info

router = APIRouter(prefix="/ocr", tags=["OCR"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "권순현"}


@router.get("/drug-info")
def drug_info(drug_name: str):
    """
    [7/8] 약물상세 화면(DrugInfo.tsx/DrugDetail.tsx)의 "약효분류·적응증" 표시용 —
    OCR 세션과 무관하게 약품명만으로 다시 조회하는 stateless 조회입니다.
    get_drug_info()이 HIRA/e약은요/ATC/폴백 순으로 조회하는 로직을 재사용합니다.
    """
    result = get_drug_info(drug_name)
    efficacy = result["efficacy"]
    # [2026-07-19 수정] matched_name(PrescriptionReview.tsx가 "이 약품명이 실제로 맞는지"
    # 판단하는 값)은 get_drug_info()의 atc_pattern/fallback이 아니라 match_drug()의 유사도
    # 점수로 판정한다. atc_pattern/fallback은 "이름에 특정 키워드가 포함되는가"만 보는
    # 부분일치라 "졸피뎀아무말"처럼 실제 이름 뒤에 엉뚱한 말을 붙여도 "졸피뎀" 부분만으로
    # 통과해버린다. match_drug()은 (용량 표기를 정규화한 뒤) 전체 문자열 유사도를 보므로
    # 이런 "일부만 맞고 나머지는 틀린" 입력을 실제로 걸러낸다 — run_ocr()에서 이미 같은
    # 기준(MATCH_THRESHOLD)으로 review_required를 정하던 로직 재사용.
    _, score = match_drug(drug_name)
    return {
        "drug_name": drug_name,
        "matched_name": drug_name if score >= MATCH_THRESHOLD else None,
        "drug_class": result["drug_class"],
        "indication": efficacy.strip() if efficacy else efficacy,
    }


async def run_ocr(patient_id: int, file: UploadFile, session: Session) -> MedicalRecord:
    """
    처방전 이미지를 CLOVA OCR로 인식하고 DB에 저장하는 실제 로직.
    records_router.py(POST /records)와 아래 /ocr/test 양쪽에서 호출됩니다.

    - patient_id: 이 처방전의 환자 id
    - 인식된 약품마다 ocr_results 행이 1개씩 생성됩니다.
    - review_required는 처방전 전체 단위 판정(overall_confidence < 0.80)이며,
      그 값이 모든 OcrResult 행에 동일하게 기록됩니다.

    검증 실패(400)나 CLOVA 통신 오류(502/503/504)는 HTTPException으로 던져지고,
    호출부(records_router.py)에서 그대로 전파되어 프론트가 실패로 인식합니다.
    """
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="파일을 다시 선택해주시겠어요?")
    _, ext = os.path.splitext(filename)
    if ext.lower() not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail="JPG, PNG 형식의 사진 파일만 올릴 수 있어요. "
                   "다른 형식의 파일이라면 사진으로 변환한 뒤 다시 올려주시겠어요?",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="사진 파일이 비어있어요. 다시 찍어서 올려주시겠어요?")

    record = MedicalRecord(patient_id=patient_id, image_path=filename, status="processing")

    # session.add/commit/refresh는 동기 SQLModel 호출이라, async def 안에서 그대로 부르면
    # 이벤트 루프를 막는다 — 아래 CLOVA 호출(asyncio.to_thread로 이미 감싸져 있음)과 같은
    # 이유로 이 함수의 모든 DB 접근도 스레드에서 실행한다.
    def _persist(rec: MedicalRecord) -> None:
        session.add(rec)
        session.commit()

    def _persist_and_refresh(rec: MedicalRecord) -> None:
        session.add(rec)
        session.commit()
        session.refresh(rec)

    await asyncio.to_thread(_persist_and_refresh, record)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext.lower()) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        provider_kind = os.environ.get("OCR_PROVIDER", "clova")
        provider = get_ocr_provider(provider_kind)
        ocr_result = await asyncio.to_thread(provider.extract, tmp_path)

    except requests.exceptions.Timeout as exc:
        record.status = "failed"
        record.failure_reason = "CLOVA API 타임아웃"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=504,
            detail="처방전 인식에 시간이 너무 걸렸어요. 잠시 후 다시 시도해주시겠어요?",
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        record.status = "failed"
        record.failure_reason = "CLOVA API 연결 실패"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=503,
            detail="인터넷 연결을 확인하고 다시 시도해주시겠어요?",
        ) from exc
    except requests.exceptions.HTTPError as exc:
        http_status = exc.response.status_code if exc.response is not None else "?"
        record.status = "failed"
        record.failure_reason = f"CLOVA API HTTP {http_status} 오류"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=502,
            detail="처방전 인식 서비스에 일시적인 문제가 생겼어요. 잠시 후 다시 시도해주시겠어요?",
        ) from exc
    except RuntimeError as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=503,
            detail="처방전 인식 서비스를 현재 사용할 수 없어요. 관리자에게 문의해주세요.",
        ) from exc
    except Exception as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=500,
            detail="처방전을 처리하는 중에 문제가 생겼어요. 잠시 후 다시 시도해주시겠어요?",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    record.raw_text = ocr_result.raw_text
    record.status = "review_required" if ocr_result.review_required else "completed"
    session.add(record)

    if not ocr_result.medications:
        record.status = "review_required"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=422,
            detail="처방전에서 약품 정보를 찾지 못했어요. 처방전이 잘 보이도록 다시 찍어서 올려주시겠어요?",
        )

    def _save_ocr_results() -> None:
        for med in ocr_result.medications:
            matched_name, score = match_drug(med.drug_name)
            row = OcrResult(
                record_id=record.id,
                drug_name=med.drug_name,
                drug_code=med.drug_code,
                dosage=med.dosage,
                frequency=med.frequency,
                diagnosis=med.diagnosis,
                drug_class=med.drug_class,
                total_days=med.total_days,
                confidence=med.confidence,
                review_required=ocr_result.review_required,
                matched_drug_name=matched_name,
                match_score=score,
                needs_review=score < MATCH_THRESHOLD,
            )
            session.add(row)
        session.commit()
        session.refresh(record)

    await asyncio.to_thread(_save_ocr_results)
    return record


@router.post("/test")
async def test_ocr_upload(
    patient_id: int,
    file: UploadFile = File(...),
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """OCR만 따로 테스트하고 싶을 때 쓰는 엔드포인트 (실제 흐름은 POST /records 사용)"""
    # require_actor_patient_access/session.exec 둘 다 동기 SQLModel 호출이라 스레드에서 실행.
    await asyncio.to_thread(require_actor_patient_access, patient_id, actor, session)
    record = await run_ocr(patient_id, file, session)
    medications = await asyncio.to_thread(
        lambda: [
            {
                "drug_name": m.drug_name,
                "dosage": m.dosage,
                "frequency": m.frequency,
                "diagnosis": m.diagnosis,
                "drug_class": m.drug_class,
                "confidence": m.confidence,
                "review_required": m.review_required,
            }
            for m in session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
        ]
    )
    return {
        "record_id": record.id,
        "status": record.status,
        "medications": medications,
    }
