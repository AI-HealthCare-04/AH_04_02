"""
patient_medications_router.py — 환자 의약품 등록/조회/일정/복약기록 (담당: 김영혜, 2026-07-14 추가)

여러 로컬 개발 환경이 공통 DB를 쓰도록 정리하면서 함께 요청된 신규 기능. 다른
patient_id 기반 라우터(monitoring_router.py 등)와 동일하게 `get_current_actor` +
`require_actor_patient_access` 패턴으로 인가한다 — 보호자 토큰이면 연결된 환자인지,
환자 본인 토큰이면 자기 자신인지 확인.

[설계 원칙]
- 의약품 마스터 테이블이 이 프로젝트에 아직 없다(rag/의 CSV·정부 API 실시간 조회로 대체
  중). 그래서 이 라우터는 drug_id/item_seq를 "클라이언트가 이미 확정 지은 값이 있으면
  그대로 저장"할 뿐, 여기서 임의로 의약품명을 검색해 자동 매칭하지 않는다 — 매칭 결과가
  하나로 확정되지 않으면 null로 남기고 원문(source_raw_text)만 보존해야 하기 때문.
- source_type="manual"(환자/보호자가 직접 입력)이면 AI 추정 단계 없이 사람이 바로 최종
  값을 넣은 것이므로 verification_status 기본값을 user_confirmed로 잡는다. 그 외
  (prescription_ocr/pill_image/api_search)는 사람 확인 전이라 unverified가 기본값.
- DELETE는 실제 행을 지우지 않고 deleted_at만 채우는 soft delete — 의료 데이터라 실수로
  지운 기록도 복구 가능해야 한다는 원칙(medication_records/스케줄에서도 참조할 수 있음).
"""
from __future__ import annotations

import json
from datetime import datetime

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from fastapi import APIRouter, Depends, HTTPException
from models import MedicationRecord, MedicationSchedule, PatientMedication
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter(prefix="/patients", tags=["PatientMedications"])


# ══════════════════════════════════════════
# 요청/응답 스키마
# ══════════════════════════════════════════
class PatientMedicationCreate(BaseModel):
    drug_id: int | None = None
    item_seq: str | None = None
    product_code: str | None = None
    medication_name: str
    manufacturer_name: str | None = None
    dosage_amount: str | None = None
    dosage_unit: str | None = None
    frequency_per_day: int | None = None
    administration_route: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    prescription_id: int | None = None
    source_type: str = "manual"  # manual / prescription_ocr / pill_image / api_search
    source_raw_text: str | None = None
    verification_status: str | None = None  # 생략하면 source_type 기준으로 자동 결정
    is_active: bool = True


class PatientMedicationUpdate(BaseModel):
    drug_id: int | None = None
    item_seq: str | None = None
    product_code: str | None = None
    medication_name: str | None = None
    manufacturer_name: str | None = None
    dosage_amount: str | None = None
    dosage_unit: str | None = None
    frequency_per_day: int | None = None
    administration_route: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    verification_status: str | None = None
    is_active: bool | None = None


class PatientMedicationPublic(BaseModel):
    id: int
    patient_id: int
    drug_id: int | None = None
    item_seq: str | None = None
    product_code: str | None = None
    medication_name: str
    manufacturer_name: str | None = None
    dosage_amount: str | None = None
    dosage_unit: str | None = None
    frequency_per_day: int | None = None
    administration_route: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    prescription_id: int | None = None
    source_type: str
    source_raw_text: str | None = None
    verification_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScheduleCreate(BaseModel):
    time_slot: str  # 예: "08:00"
    dose_timing: str | None = None
    meal_relation: str | None = None
    instructions: str | None = None
    timezone: str | None = None
    days_of_week: list[str] | None = None  # ["mon","wed","fri"] 형태 — 저장 시 JSON 문자열로 변환
    caregiver_alert: bool = True
    memo: str | None = None


class SchedulePublic(BaseModel):
    id: int
    patient_id: int
    patient_medication_id: int | None = None
    drug_name: str
    time_slot: str
    dose_timing: str | None = None
    meal_relation: str | None = None
    instructions: str | None = None
    timezone: str | None = None
    days_of_week: list[str] | None = None
    caregiver_alert: bool
    memo: str | None = None
    active: bool
    created_at: datetime


def _schedule_to_public(schedule: MedicationSchedule) -> SchedulePublic:
    return SchedulePublic(
        id=schedule.id,
        patient_id=schedule.patient_id,
        patient_medication_id=schedule.patient_medication_id,
        drug_name=schedule.drug_name,
        time_slot=schedule.time_slot,
        dose_timing=schedule.dose_timing,
        meal_relation=schedule.meal_relation,
        instructions=schedule.instructions,
        timezone=schedule.timezone,
        days_of_week=json.loads(schedule.days_of_week) if schedule.days_of_week else None,
        caregiver_alert=schedule.caregiver_alert,
        memo=schedule.memo,
        active=schedule.active,
        created_at=schedule.created_at,
    )


class MedicationRecordCreate(BaseModel):
    patient_medication_id: int
    schedule_id: int | None = None
    scheduled_at: datetime | None = None
    taken_at: datetime | None = None
    status: str = "scheduled"  # scheduled / taken / missed / skipped / duplicate_suspected
    verification_method: str = "self_report"  # self_report / caregiver / photo / device
    evidence_image_url: str | None = None
    memo: str | None = None


class MedicationRecordPublic(BaseModel):
    id: int
    patient_medication_id: int
    schedule_id: int | None = None
    scheduled_at: datetime | None = None
    taken_at: datetime | None = None
    status: str
    verification_method: str
    evidence_image_url: str | None = None
    memo: str | None = None
    created_at: datetime
    updated_at: datetime


# ══════════════════════════════════════════
# 헬퍼
# ══════════════════════════════════════════
def _get_owned_medication(
    patient_id: int, medication_id: int, session: Session
) -> PatientMedication:
    """patient_id 소유의 medication_id를 찾는다 — 다른 환자의 medication_id를 넣으면
    (경로의 patient_id는 본인/케어 대상이라도) 404로 막아 IDOR을 방지한다."""
    medication = session.get(PatientMedication, medication_id)
    if not medication or medication.patient_id != patient_id or medication.deleted_at is not None:
        raise HTTPException(404, "해당 의약품을 찾을 수 없어요")
    return medication


# ══════════════════════════════════════════
# 환자 의약품 CRUD
# ══════════════════════════════════════════
@router.post("/{patient_id}/medications", response_model=PatientMedicationPublic)
def create_medication(
    patient_id: int,
    payload: PatientMedicationCreate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)

    verification_status = payload.verification_status
    if not verification_status:
        # 사람이 직접 입력(manual)했으면 AI 추정 단계가 없으므로 바로 확정 상태로 본다.
        verification_status = "user_confirmed" if payload.source_type == "manual" else "unverified"

    medication = PatientMedication(
        **payload.model_dump(exclude={"verification_status"}),
        patient_id=patient_id,
        verification_status=verification_status,
    )
    session.add(medication)
    session.commit()
    session.refresh(medication)
    return medication


@router.get("/{patient_id}/medications", response_model=list[PatientMedicationPublic])
def list_medications(
    patient_id: int,
    include_inactive: bool = True,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    query = select(PatientMedication).where(
        PatientMedication.patient_id == patient_id,
        PatientMedication.deleted_at.is_(None),
    )
    if not include_inactive:
        query = query.where(PatientMedication.is_active.is_(True))
    return session.exec(query.order_by(PatientMedication.created_at.desc())).all()


@router.get("/{patient_id}/medications/{medication_id}", response_model=PatientMedicationPublic)
def get_medication(
    patient_id: int,
    medication_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    return _get_owned_medication(patient_id, medication_id, session)


@router.patch("/{patient_id}/medications/{medication_id}", response_model=PatientMedicationPublic)
def update_medication(
    patient_id: int,
    medication_id: int,
    payload: PatientMedicationUpdate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    medication = _get_owned_medication(patient_id, medication_id, session)
    # [주의] medication_name을 사용자가 최종 확인해 고치더라도 source_raw_text(AI/OCR
    # 원문)는 여기서 절대 건드리지 않는다 — "AI가 처음에 뭐라고 봤는지"를 계속 추적 가능해야 함.
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(medication, key, value)
    medication.updated_at = datetime.now()
    session.add(medication)
    session.commit()
    session.refresh(medication)
    return medication


@router.delete("/{patient_id}/medications/{medication_id}")
def delete_medication(
    patient_id: int,
    medication_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """실제로 행을 지우지 않고 deleted_at만 채우는 soft delete — 의료 데이터 특성상
    실수로 지운 기록도 복구할 수 있어야 한다."""
    require_actor_patient_access(patient_id, actor, session)
    medication = _get_owned_medication(patient_id, medication_id, session)
    medication.deleted_at = datetime.now()
    medication.is_active = False
    medication.updated_at = datetime.now()
    session.add(medication)
    session.commit()
    return {"deleted": medication_id}


# ══════════════════════════════════════════
# 복약 일정
# ══════════════════════════════════════════
@router.post(
    "/{patient_id}/medications/{medication_id}/schedules", response_model=SchedulePublic
)
def create_schedule_for_medication(
    patient_id: int,
    medication_id: int,
    payload: ScheduleCreate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    medication = _get_owned_medication(patient_id, medication_id, session)

    schedule = MedicationSchedule(
        patient_id=patient_id,
        patient_medication_id=medication.id,
        drug_name=medication.medication_name,  # 기존 스케줄 테이블은 drug_name이 필수라 채워줌
        time_slot=payload.time_slot,
        dose_timing=payload.dose_timing,
        meal_relation=payload.meal_relation,
        instructions=payload.instructions,
        timezone=payload.timezone,
        days_of_week=json.dumps(payload.days_of_week) if payload.days_of_week else None,
        caregiver_alert=payload.caregiver_alert,
        memo=payload.memo,
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return _schedule_to_public(schedule)


# ══════════════════════════════════════════
# 복약 기록
# ══════════════════════════════════════════
@router.post("/{patient_id}/medication-records", response_model=MedicationRecordPublic)
def create_medication_record(
    patient_id: int,
    payload: MedicationRecordCreate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    # patient_medication_id가 진짜 이 환자 것인지 확인 — 다른 환자의 의약품 id를 넣어서
    # 남의 기록에 끼워넣는 것을 방지.
    _get_owned_medication(patient_id, payload.patient_medication_id, session)

    record = MedicationRecord(**payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/{patient_id}/medication-records", response_model=list[MedicationRecordPublic])
def list_medication_records(
    patient_id: int,
    patient_medication_id: int | None = None,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    medication_ids = session.exec(
        select(PatientMedication.id).where(PatientMedication.patient_id == patient_id)
    ).all()
    if not medication_ids:
        return []

    query = select(MedicationRecord).where(MedicationRecord.patient_medication_id.in_(medication_ids))
    if patient_medication_id is not None:
        if patient_medication_id not in medication_ids:
            raise HTTPException(404, "해당 의약품을 찾을 수 없어요")
        query = query.where(MedicationRecord.patient_medication_id == patient_medication_id)
    return session.exec(query.order_by(MedicationRecord.created_at.desc())).all()
