"""
records_router.py — 담당: 박소정 (전체 흐름 연결)

schedule_v6의 "동기 방식" 원칙 그대로: 폴링도 스트리밍도 없이,
처방전 업로드 요청 하나로 OCR → RAG까지 다 처리해서 결과를 한 번에 돌려줍니다.

프론트 흐름:
1) Upload.tsx — 파일 선택만 하고 /processing으로 이동 (아직 요청 안 보냄)
2) Processing.tsx — 마운트되자마자 이 POST /records를 호출하고 기다림 (몇 초 걸릴 수 있음)
   기다리는 동안 기존 3단계 애니메이션을 그냥 시각 효과로 보여줌
3) 응답이 오면 그 데이터를 그대로 들고 /result로 이동 (재조회 없음)
"""
from __future__ import annotations
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from database import get_session
from models import GuideResult, MedicalRecord, OcrResult, Patient
from routers.ocr_router import run_ocr
from routers.rag_router import run_rag_stub

router = APIRouter(prefix="/records", tags=["Records"])


def _build_record_response(record: MedicalRecord, session: Session, guide: GuideResult | None) -> dict:
    ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
    return {
        "record_id": record.id,
        "status": record.status,
        "failure_reason": record.failure_reason,
        "medications": [
            {
                "drug_name": item.drug_name,
                "drug_code": item.drug_code,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "diagnosis": item.diagnosis,
                "drug_class": item.drug_class,
                "confidence": item.confidence,
                "review_required": item.review_required,
            }
            for item in ocr_items
        ],
        "guide": (
            {
                "medication_guide": json.loads(guide.medication_guide),
                "lifestyle_guide": json.loads(guide.lifestyle_guide),
                "source_refs": json.loads(guide.source_refs),
            }
            if guide
            else None
        ),
    }


@router.post("")
async def create_record(
    patient_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    """
    처방전 이미지를 받아서 OCR → RAG 가이드 생성까지 끝내고 결과를 반환합니다.

    [7/8] 권순현님 PR #9 실제 CLOVA 로직 통합 완료 — run_ocr()가 이제 진짜 CLOVA를 호출합니다.
    review_required(저신뢰, 보호자 확인 필요)면 RAG는 호출하지 않고 그 상태로 바로 반환합니다.
    프론트(Result.tsx)는 review_required를 받으면 "확인 필요" 배지를 보여주고,
    보호자가 확인/수정한 뒤 재요청하는 흐름으로 이어집니다(재요청 엔드포인트는 별도 TODO).

    ⚠️ CLOVA_OCR_API_URL/SECRET_KEY가 .env에 없으면 503으로 실패합니다(의도된 동작).
       키 없이 파이프라인만 테스트하려면 .env에 OCR_PROVIDER=mock 추가하세요.

    김영혜의 실제 RAG 로직이 붙기 전까지는 run_rag_stub의 가짜 데이터가 나갑니다.
    """
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    record = await run_ocr(patient_id, file, session)

    if record.status == "review_required":
        # RAG 호출 자체를 안 함 — OCR 결과만 담아서 바로 반환
        return _build_record_response(record, session, None)

    try:
        guide = run_rag_stub(record.id, session)
    except ValueError as e:
        # OCR은 됐는데 RAG가 실패한 경우 — records/OCR결과는 남기고 실패로 표시
        record.status = "failed"
        record.failure_reason = str(e)
        session.add(record)
        session.commit()
        session.refresh(record)
        return _build_record_response(record, session, None)

    return _build_record_response(record, session, guide)


@router.get("")
def list_records(patient_id: int, session: Session = Depends(get_session)):
    """
    환자별 처방전 이력 목록 (RecordsPage '이용 기록' 화면용).
    각 항목은 상세 조회 없이 목록에 필요한 요약 정보만 담습니다.
    """
    records = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    ).all()

    summaries = []
    for r in records:
        ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == r.id)).all()
        summaries.append(
            {
                "record_id": r.id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "diagnosis": ocr_items[0].diagnosis if ocr_items else "",
                "drug_names": [item.drug_name for item in ocr_items],
            }
        )
    return summaries


@router.get("/{record_id}")
def get_record(record_id: int, session: Session = Depends(get_session)):
    """새로고침 등으로 결과 화면을 다시 열었을 때 재조회용 (Processing에서 받은 데이터가 없을 때 대비)"""
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")

    guide = session.exec(
        select(GuideResult)
        .where(GuideResult.record_id == record_id)
        .order_by(GuideResult.id.desc())
    ).first()
    return _build_record_response(record, session, guide)
