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
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models import Caregiver, GuideResult, MedicalRecord, OcrResult, Patient
from routers.ocr_router import run_ocr
from routers.rag_router import run_rag

router = APIRouter(prefix="/records", tags=["Records"])


def _build_record_response(record: MedicalRecord, session: Session, guide: GuideResult | None) -> dict:
    ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
    uploader = (
        session.get(Caregiver, record.uploaded_by_caregiver_id)
        if record.uploaded_by_caregiver_id
        else None
    )
    return {
        "record_id": record.id,
        "status": record.status,
        "failure_reason": record.failure_reason,
        "created_at": record.created_at.isoformat(),
        "uploaded_by_name": uploader.name if uploader else None,
        "medications": [
            {
                "id": item.id,  # [7/8 추가] 처방전확인 화면에서 항목별 수정 시 식별용
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
    patient_id: int,
    file: UploadFile = File(...),
    caregiver_id: int | None = None,
    session: Session = Depends(get_session),
):
    """
    처방전 이미지를 받아서 OCR → RAG 가이드 생성까지 끝내고 결과를 반환합니다.

    [7/9 추가] caregiver_id를 넘기면 "보호자가 대신 업로드"로 기록됩니다(생략하면 본인 업로드).

    [7/8] 권순현님 PR #9 실제 CLOVA 로직 통합 완료 — run_ocr()가 이제 진짜 CLOVA를 호출합니다.
    review_required(저신뢰, 보호자 확인 필요)면 RAG는 호출하지 않고 그 상태로 바로 반환합니다.
    프론트(Result.tsx)는 review_required를 받으면 "확인 필요" 배지를 보여주고,
    보호자가 확인/수정한 뒤 재요청하는 흐름으로 이어집니다(재요청 엔드포인트는 별도 TODO).

    ⚠️ CLOVA_OCR_API_URL/SECRET_KEY가 .env에 없으면 503으로 실패합니다(의도된 동작).
       키 없이 파이프라인만 테스트하려면 .env에 OCR_PROVIDER=mock 추가하세요.

    [7/8] run_rag_stub -> run_rag로 이름이 바뀌고 async def가 됐습니다 (김영혜).
    RAG_PROVIDER=real로 켜지 않는 한 지금까지와 동일한 가짜 데이터가 나갑니다 — 자세한
    내용은 rag_router.py 상단 설명 참고. 반드시 await로 호출해야 합니다(안 붙이면
    coroutine 객체만 만들고 실제로 실행되지 않는데 예외도 안 떠서 발견하기 어렵습니다).
    """
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")
    if caregiver_id is not None and not session.get(Caregiver, caregiver_id):
        raise HTTPException(404, "해당 보호자를 찾을 수 없어요")

    record = await run_ocr(patient_id, file, session)

    if caregiver_id is not None:
        record.uploaded_by_caregiver_id = caregiver_id
        session.add(record)
        session.commit()
        session.refresh(record)

    if record.status == "review_required":
        # RAG 호출 자체를 안 함 — OCR 결과만 담아서 바로 반환
        return _build_record_response(record, session, None)

    try:
        guide = await run_rag(record.id, session)
    except ValueError as e:
        # OCR은 됐는데 RAG가 실패한 경우 — records/OCR결과는 남기고 실패로 표시
        record.status = "failed"
        record.failure_reason = str(e)
        session.add(record)
        session.commit()
        session.refresh(record)
        return _build_record_response(record, session, None)

    return _build_record_response(record, session, guide)


@router.post("/manual")
def create_manual_record(
    patient_id: int, caregiver_id: int | None = None, session: Session = Depends(get_session)
):
    """
    [7/9 추가] 처방전 인식 실패(OcrError.tsx) 화면의 "직접 입력하기" — OCR을 거치지 않고
    빈 항목 1개짜리 review_required 기록을 만들어서 PrescriptionReview.tsx에서 그대로
    입력·수정하게 합니다. 이후 흐름(확인 완료 → RAG 가이드 생성)은 기존 확인 화면과 동일합니다.
    """
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")
    if caregiver_id is not None and not session.get(Caregiver, caregiver_id):
        raise HTTPException(404, "해당 보호자를 찾을 수 없어요")

    record = MedicalRecord(
        patient_id=patient_id,
        image_path="manual_entry",
        status="review_required",
        uploaded_by_caregiver_id=caregiver_id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    session.add(OcrResult(record_id=record.id, drug_name="", confidence=0.0, review_required=True))
    session.commit()

    return _build_record_response(record, session, None)


@router.post("/{record_id}/medications")
def add_medication_item(record_id: int, session: Session = Depends(get_session)):
    """
    [7/9 추가] 처방전확인 화면의 "약물 추가" — 빈 항목을 하나 더 만들어서, 사용자가
    처방전에 있지만 인식되지 않은 약을 직접 추가할 수 있게 합니다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    session.add(OcrResult(record_id=record_id, drug_name="", confidence=0.0, review_required=True))
    session.commit()

    return _build_record_response(record, session, None)


@router.delete("/{record_id}/medications/{medication_id}")
def remove_medication_item(record_id: int, medication_id: int, session: Session = Depends(get_session)):
    """
    [7/9 추가] 처방전확인 화면 — "약물 추가"로 잘못 추가했거나 필요 없는 항목을 지우는 용도.
    최소 1개는 남아 있어야 해서(약이 0개인 처방전은 의미가 없음) 마지막 항목은 못 지웁니다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    item = session.get(OcrResult, medication_id)
    if not item or item.record_id != record_id:
        raise HTTPException(404, "해당 약물 항목을 찾을 수 없어요")

    remaining = session.exec(select(OcrResult).where(OcrResult.record_id == record_id)).all()
    if len(remaining) <= 1:
        raise HTTPException(409, "처방전에는 최소 1개의 약물 항목이 있어야 해요")

    session.delete(item)
    session.commit()

    return _build_record_response(record, session, None)


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
        uploader = session.get(Caregiver, r.uploaded_by_caregiver_id) if r.uploaded_by_caregiver_id else None
        summaries.append(
            {
                "record_id": r.id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "diagnosis": ocr_items[0].diagnosis if ocr_items else "",
                "drug_names": [item.drug_name for item in ocr_items],
                "uploaded_by_name": uploader.name if uploader else None,
            }
        )
    return summaries


class MedicationCorrection(BaseModel):
    id: int  # OcrResult.id
    drug_name: str
    dosage: str
    frequency: str
    diagnosis: str
    drug_class: str


class ConfirmMedicationsPayload(BaseModel):
    medications: list[MedicationCorrection]


@router.post("/{record_id}/confirm")
async def confirm_medications(
    record_id: int, payload: ConfirmMedicationsPayload, session: Session = Depends(get_session)
):
    """
    [7/8 추가] 처방전확인 화면 — review_required(저신뢰) 처방전의 항목을 보호자가 직접
    수정·확정하면 그 값으로 OCR 결과를 갈아끼우고 바로 RAG 가이드 생성까지 이어서 처리합니다.
    (POST /records 상단 docstring에 있던 "재요청 엔드포인트는 별도 TODO"를 해소)
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    for correction in payload.medications:
        item = session.get(OcrResult, correction.id)
        if not item or item.record_id != record_id:
            continue
        item.drug_name = correction.drug_name
        item.dosage = correction.dosage
        item.frequency = correction.frequency
        item.diagnosis = correction.diagnosis
        item.drug_class = correction.drug_class
        item.review_required = False
        item.user_confirmed = True
        session.add(item)
    session.commit()

    try:
        guide = await run_rag(record.id, session)
    except ValueError as e:
        record.status = "failed"
        record.failure_reason = str(e)
        session.add(record)
        session.commit()
        session.refresh(record)
        return _build_record_response(record, session, None)

    record.status = "completed"
    record.failure_reason = None
    session.add(record)
    session.commit()
    session.refresh(record)
    return _build_record_response(record, session, guide)


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
