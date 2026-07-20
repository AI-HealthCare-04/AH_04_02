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

import asyncio
import json
from collections.abc import Sequence
from datetime import datetime

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from models import Caregiver, GuideResult, MedicalRecord, MedicationSchedule, OcrResult
from pydantic import BaseModel
from sqlmodel import Session, select

from routers.ocr_router import run_ocr
from routers.rag_router import run_rag
from services.drug_matcher import MATCH_THRESHOLD, match_drug

router = APIRouter(prefix="/records", tags=["Records"])

# [7/9 추가] OCR은 "1일 N회"까지만 뽑아내고 몇 시에·식전/식후인지는 파싱하지 않는다
# (parsing_rules.py 참고 — 그 정보 자체가 OcrResult에 없음). 그래서 여기서는 횟수만 보고
# 합리적인 기본 시간대로 복약일정을 만들고, 식전/식후(dose_timing)는 비워서 사용자가
# Schedule.tsx에서 직접 채우게 한다 — 모르는 걸 아는 척 지어내지 않음.
_DEFAULT_TIME_SLOTS = {
    "1일 1회": ["09:00"],
    "1일 2회": ["09:00", "19:00"],
    "1일 3회": ["08:00", "13:00", "19:00"],
    "1일 4회": ["08:00", "12:00", "17:00", "21:00"],
}


def _create_schedules_from_ocr(record: MedicalRecord, ocr_items: Sequence[OcrResult], session: Session) -> None:
    for item in ocr_items:
        if not item.drug_name:
            continue
        for slot in _DEFAULT_TIME_SLOTS.get(item.frequency, ["09:00"]):
            session.add(
                MedicationSchedule(
                    patient_id=record.patient_id,
                    # [2026-07-20 버그수정] 예전엔 item.drug_name(축약명, 예: "암로디핀")을
                    # 그대로 썼다 — Dashboard.tsx/Schedule.tsx가 이 값을 표시하므로 환자가
                    # 매일 보는 화면에 짧은 이름이 노출되고 있었다. _build_record_response와
                    # 동일한 규칙(item.display_name)으로 통일.
                    drug_name=item.display_name,
                    time_slot=slot,
                    memo="처방전에서 자동 등록됨 — 시간·식전후 여부는 확인 후 수정해주세요",
                    # [2026-07-20 추가] 이 처방전을 나중에 삭제할 때 같이 비활성화할 수 있도록 연결.
                    record_id=record.id,
                )
            )
    session.commit()


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
                # [2026-07-20] item.display_name — 확신 있게 매칭됐을 때(needs_review=False)만
                # matched_drug_name(전체 제품명)을 대표 표시값으로 쓴다(models.py 참고).
                "drug_name": item.display_name,
                "drug_code": item.drug_code,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "total_days": item.total_days,
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
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    처방전 이미지를 받아서 OCR까지 끝내고 결과를 반환합니다.

    [7/9 변경] OCR 신뢰도와 상관없이 항상 review_required 상태로 반환합니다 — 가이드(RAG)
    생성은 더 이상 여기서 하지 않고, 사용자가 PrescriptionReview.tsx에서 내용을 확인/수정하고
    POST /{record_id}/confirm을 호출할 때만 트리거됩니다. run_ocr()이 신뢰도에 따라 정한
    status는 참고용으로 남겨두지 않고 덮어씁니다 — "확인 화면을 항상 거친다"는 게 지금
    유일한 진입 규칙이라, 두 상태를 따로 유지하면 나중에 헷갈리기만 합니다.

    [7/9 추가] caregiver_id를 넘기면 "보호자가 대신 업로드"로 기록됩니다(생략하면 본인 업로드).

    [7/8] 권순현님 PR #9 실제 CLOVA 로직 통합 완료 — run_ocr()가 이제 진짜 CLOVA를 호출합니다.

    ⚠️ CLOVA_OCR_API_URL/SECRET_KEY가 .env에 없으면 503으로 실패합니다(의도된 동작).
       키 없이 파이프라인만 테스트하려면 .env에 OCR_PROVIDER=mock 추가하세요.
    """
    # require_actor_patient_access/session.get 등은 동기 SQLModel 호출이라, async def
    # 안에서 그대로 부르면 이벤트 루프를 막는다 — run_ocr 내부(asyncio.to_thread로 이미
    # 감싸져 있음)와 동일한 이유로 이 함수의 DB 접근도 전부 스레드에서 실행한다.
    def _check_access() -> None:
        require_actor_patient_access(patient_id, actor, session)
        if caregiver_id is not None and not session.get(Caregiver, caregiver_id):
            raise HTTPException(404, "해당 보호자를 찾을 수 없어요")

    await asyncio.to_thread(_check_access)

    record = await run_ocr(patient_id, file, session)

    if caregiver_id is not None:
        def _mark_uploader() -> None:
            record.uploaded_by_caregiver_id = caregiver_id
            session.add(record)
            session.commit()
            session.refresh(record)

        await asyncio.to_thread(_mark_uploader)

    # 신뢰도와 무관하게 항상 확인 화면을 거치게 한다 — RAG는 /confirm에서만 호출된다.
    def _finalize_status() -> None:
        record.status = "review_required"
        session.add(record)
        session.commit()
        session.refresh(record)

    await asyncio.to_thread(_finalize_status)
    return await asyncio.to_thread(_build_record_response, record, session, None)


@router.post("/manual")
def create_manual_record(
    patient_id: int,
    caregiver_id: int | None = None,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/9 추가] 처방전 인식 실패(OcrError.tsx) 화면의 "직접 입력하기" — OCR을 거치지 않고
    빈 항목 1개짜리 review_required 기록을 만들어서 PrescriptionReview.tsx에서 그대로
    입력·수정하게 합니다. 이후 흐름(확인 완료 → RAG 가이드 생성)은 기존 확인 화면과 동일합니다.
    """
    require_actor_patient_access(patient_id, actor, session)
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
def add_medication_item(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/9 추가] 처방전확인 화면의 "약물 추가" — 빈 항목을 하나 더 만들어서, 사용자가
    처방전에 있지만 인식되지 않은 약을 직접 추가할 수 있게 합니다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    session.add(OcrResult(record_id=record_id, drug_name="", confidence=0.0, review_required=True))
    session.commit()

    return _build_record_response(record, session, None)


@router.delete("/{record_id}/medications/{medication_id}")
def remove_medication_item(
    record_id: int,
    medication_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/9 추가] 처방전확인 화면 — "약물 추가"로 잘못 추가했거나 필요 없는 항목을 지우는 용도.
    최소 1개는 남아 있어야 해서(약이 0개인 처방전은 의미가 없음) 마지막 항목은 못 지웁니다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)
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


class MedicationPatch(BaseModel):
    drug_name: str
    dosage: str = ""
    frequency: str = ""
    total_days: str = ""
    diagnosis: str = ""
    drug_class: str = ""


class MedicationPatchResult(BaseModel):
    id: int
    drug_name: str
    dosage: str
    frequency: str
    total_days: str
    diagnosis: str
    drug_class: str
    matched_drug_name: str
    match_score: float
    needs_review: bool
    typo_suggestion: str | None = None


@router.patch("/{record_id}/medications/{medication_id}", response_model=MedicationPatchResult)
def patch_medication_item(
    record_id: int,
    medication_id: int,
    payload: MedicationPatch,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    처방전확인 화면 — 단건 약물 항목 수정 + REQ-047 오타 제안.

    drug_name을 약물명 사전과 대조해, 사전에 정확히 없으면 가장 유사한 후보를
    typo_suggestion으로 응답에 포함한다. typo_suggestion은 저장하지 않는다.
    완전 일치 조건은 matched_name == drug_name (raw 문자열 exact match).
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    item = session.get(OcrResult, medication_id)
    if not item or item.record_id != record_id:
        raise HTTPException(404, "해당 약물 항목을 찾을 수 없어요")

    item.drug_name = payload.drug_name
    item.dosage = payload.dosage
    item.frequency = payload.frequency
    item.total_days = payload.total_days
    item.diagnosis = payload.diagnosis
    item.drug_class = payload.drug_class

    matched_name, score = match_drug(payload.drug_name)
    item.matched_drug_name = matched_name
    item.match_score = score
    item.needs_review = score < MATCH_THRESHOLD

    session.add(item)
    session.commit()
    session.refresh(item)

    typo_suggestion: str | None = None
    if matched_name and matched_name != payload.drug_name and score >= MATCH_THRESHOLD:
        typo_suggestion = matched_name

    return MedicationPatchResult(
        id=item.id,
        drug_name=item.drug_name,
        dosage=item.dosage,
        frequency=item.frequency,
        total_days=item.total_days,
        diagnosis=item.diagnosis,
        drug_class=item.drug_class,
        matched_drug_name=item.matched_drug_name,
        match_score=item.match_score,
        needs_review=item.needs_review,
        typo_suggestion=typo_suggestion,
    )


@router.get("")
def list_records(
    patient_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    환자별 처방전 이력 목록 (RecordsPage '이용 기록' 화면용).
    각 항목은 상세 조회 없이 목록에 필요한 요약 정보만 담습니다.
    """
    require_actor_patient_access(patient_id, actor, session)
    records = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .where(MedicalRecord.deleted_at.is_(None))
        .order_by(MedicalRecord.created_at.desc())  # ty: ignore[unresolved-attribute]
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


@router.delete("/{record_id}")
def delete_record(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [2026-07-16 추가] 등록내역(처방전 기록) 삭제 — 멘토링에서 지적된 "등록내역 삭제 기능
    필요" 항목. OcrResult/GuideResult 등 연결 데이터는 그대로 두고 soft-delete만 하며
    (PatientMedication.deleted_at과 동일한 관례), 목록/상세 조회에서만 제외한다.

    [2026-07-20 추가] 이 처방전에서 자동 생성된 복약 일정(MedicationSchedule.record_id로
    연결됨)도 함께 비활성화한다 — 안 그러면 "삭제한" 처방전의 약이 대시보드/스케줄러
    알림에 계속 남아있게 된다(리뷰에서 발견).
    """
    record = session.get(MedicalRecord, record_id)
    if not record or record.deleted_at is not None:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)

    record.deleted_at = datetime.now()
    session.add(record)

    schedules = session.exec(
        select(MedicationSchedule).where(MedicationSchedule.record_id == record_id)
    ).all()
    for schedule in schedules:
        schedule.active = False
        session.add(schedule)

    session.commit()
    return {"message": "삭제됐어요"}


class MedicationCorrection(BaseModel):
    id: int  # OcrResult.id
    drug_name: str
    dosage: str
    frequency: str
    total_days: str = ""  # [2026-07-18 추가] 총 투약일수
    diagnosis: str
    drug_class: str


class ConfirmMedicationsPayload(BaseModel):
    medications: list[MedicationCorrection]


@router.post("/{record_id}/confirm")
async def confirm_medications(
    record_id: int,
    payload: ConfirmMedicationsPayload,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/8 추가] 처방전확인 화면 — review_required(저신뢰) 처방전의 항목을 보호자가 직접
    수정·확정하면 그 값으로 OCR 결과를 갈아끼우고 바로 RAG 가이드 생성까지 이어서 처리합니다.
    (POST /records 상단 docstring에 있던 "재요청 엔드포인트는 별도 TODO"를 해소)
    """
    # 이 함수의 모든 SQLModel 호출(동기)은 스레드에서 실행한다 — run_ocr/run_rag와
    # 동일한 이유(async def 안에서 동기 DB 호출이 이벤트 루프를 막지 않도록).
    def _load_and_check() -> MedicalRecord:
        rec = session.get(MedicalRecord, record_id)
        if not rec:
            raise HTTPException(404, "해당 기록을 찾을 수 없어요")
        require_actor_patient_access(rec.patient_id, actor, session)
        if rec.status != "review_required":
            raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")
        return rec

    record = await asyncio.to_thread(_load_and_check)

    def _apply_corrections() -> None:
        for correction in payload.medications:
            item = session.get(OcrResult, correction.id)
            if not item or item.record_id != record_id:
                continue
            item.drug_name = correction.drug_name
            item.dosage = correction.dosage
            item.frequency = correction.frequency
            item.total_days = correction.total_days
            item.diagnosis = correction.diagnosis
            item.drug_class = correction.drug_class
            item.review_required = False
            item.user_confirmed = True
            session.add(item)
        session.commit()

    await asyncio.to_thread(_apply_corrections)

    try:
        guide, _from_cache, _cache_expires_at = await run_rag(record.id, session)
    except ValueError as exc:
        _failure_reason = str(exc)  # except 블록 밖에서 e가 삭제되기 전에 캡처

        def _mark_failed() -> None:
            record.status = "failed"
            record.failure_reason = _failure_reason
            session.add(record)
            session.commit()
            session.refresh(record)

        await asyncio.to_thread(_mark_failed)
        return await asyncio.to_thread(_build_record_response, record, session, None)

    def _mark_completed() -> None:
        record.status = "completed"
        record.failure_reason = None
        session.add(record)
        session.commit()
        session.refresh(record)

    await asyncio.to_thread(_mark_completed)

    # [7/9 추가] 확인이 끝난 약을 복약 일정에도 자동으로 등록 — 사용자가 Schedule.tsx에서
    # 매번 손으로 다시 입력하지 않도록.
    def _register_schedules() -> None:
        ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
        _create_schedules_from_ocr(record, ocr_items, session)

    await asyncio.to_thread(_register_schedules)

    return await asyncio.to_thread(_build_record_response, record, session, guide)


@router.get("/{record_id}")
def get_record(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """새로고침 등으로 결과 화면을 다시 열었을 때 재조회용 (Processing에서 받은 데이터가 없을 때 대비)"""
    record = session.get(MedicalRecord, record_id)
    if not record or record.deleted_at is not None:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)

    guide = session.exec(
        select(GuideResult)
        .where(GuideResult.record_id == record_id)
        .order_by(GuideResult.id.desc())  # ty: ignore[unresolved-attribute]
    ).first()
    return _build_record_response(record, session, guide)
