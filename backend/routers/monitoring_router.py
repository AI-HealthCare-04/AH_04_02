"""
monitoring_router.py — 담당: 박소정 (멘토 최우선 지정 기능)

[7/6 변경] 환자 구분 추가 — 한 보호자가 여러 환자를 케어할 수 있도록
patients / caregivers / caregiver_patients(다대다)를 도입함.

[7/6 보류] JWT 로그인은 만들어뒀지만(auth.py, dependencies.py, routers/auth_router.py)
이번 스프린트 스코프에서는 뺐습니다(백엔드 경험 0명 + 남은 시간 대응, schedule_v6 결정).
그래서 "누가 보고 있는지"는 프론트가 caregiver_id를 들고 있다가
쿼리 파라미터로 넘겨주는 방식으로 대체함 (Upload.tsx의 localStorage user_id와 같은 패턴).
나중에 로그인을 붙이게 되면 각 함수 시그니처의 caregiver_id 파라미터를
`caregiver: Caregiver = Depends(get_current_caregiver)`로 바꾸고 caregiver.id를 쓰면 됩니다.

기본 흐름:
1) GET /caregivers  → 보호자 목록 (데모에선 1명, 실제로는 회원가입 대체 화면에서 선택)
2) GET /caregivers/{id}/patients  → 그 보호자가 케어하는 환자 목록
3) 환자 하나를 고르면 그 patient_id로 /monitoring/today?patient_id=... 호출
"""
from __future__ import annotations
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from database import get_session
from models import Caregiver, CaregiverPatient, MedicationLog, MedicationSchedule, Patient

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# ══════════════════════════════════════════
# 환자 (Patient) CRUD
# ══════════════════════════════════════════
class PatientCreate(BaseModel):
    name: str
    note: str | None = None


class PatientUpdate(BaseModel):
    name: str | None = None
    note: str | None = None


@router.post("/patients", response_model=Patient)
def create_patient(payload: PatientCreate, session: Session = Depends(get_session)):
    patient = Patient(**payload.model_dump())
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.get("/patients", response_model=list[Patient])
def list_patients(session: Session = Depends(get_session)):
    return session.exec(select(Patient)).all()


@router.patch("/patients/{patient_id}", response_model=Patient)
def update_patient(patient_id: int, payload: PatientUpdate, session: Session = Depends(get_session)):
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: int, session: Session = Depends(get_session)):
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")
    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.patient_id == patient_id)
    ).all()
    for link in links:
        session.delete(link)
    session.delete(patient)
    session.commit()
    return {"deleted": patient_id}


# ══════════════════════════════════════════
# 보호자·요양보호사 (Caregiver) + 환자 연결
# ══════════════════════════════════════════
class CaregiverCreate(BaseModel):
    name: str
    relation_type: str = "guardian"  # guardian / caregiver / life_support_worker / social_worker


class CaregiverPublic(BaseModel):
    """hashed_password는 API 응답에 노출하지 않기 위한 응답 전용 모델"""
    id: int
    name: str
    relation_type: str
    created_at: datetime


@router.post("/caregivers", response_model=CaregiverPublic)
def create_caregiver(payload: CaregiverCreate, session: Session = Depends(get_session)):
    caregiver = Caregiver(**payload.model_dump())
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


@router.get("/caregivers", response_model=list[CaregiverPublic])
def list_caregivers(session: Session = Depends(get_session)):
    return session.exec(select(Caregiver)).all()


@router.get("/caregivers/{caregiver_id}/patients", response_model=list[Patient])
def list_patients_of_caregiver(caregiver_id: int, session: Session = Depends(get_session)):
    """핵심 기능: 이 보호자가 케어하는 환자 전체 목록 (여러 명 가능)"""
    caregiver = session.get(Caregiver, caregiver_id)
    if not caregiver:
        raise HTTPException(404, "해당 보호자를 찾을 수 없어요")

    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.caregiver_id == caregiver_id)
    ).all()
    patient_ids = [link.patient_id for link in links]
    if not patient_ids:
        return []
    return session.exec(select(Patient).where(Patient.id.in_(patient_ids))).all()


@router.get("/patients/{patient_id}/caregivers", response_model=list[CaregiverPublic])
def list_caregivers_of_patient(patient_id: int, session: Session = Depends(get_session)):
    """[7/8 추가] 반대 방향 조회 — 이 환자를 케어하는 보호자 전체 목록 (Connect.tsx '연결된 사람' 표에 사용)"""
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.patient_id == patient_id)
    ).all()
    caregiver_ids = [link.caregiver_id for link in links]
    if not caregiver_ids:
        return []
    return session.exec(select(Caregiver).where(Caregiver.id.in_(caregiver_ids))).all()


@router.post("/caregivers/{caregiver_id}/patients/{patient_id}")
def link_caregiver_to_patient(
    caregiver_id: int, patient_id: int, session: Session = Depends(get_session)
):
    """보호자-환자 연결 추가 (한 환자를 여러 보호자가 같이 볼 때도 이걸로 추가 연결)"""
    if not session.get(Caregiver, caregiver_id):
        raise HTTPException(404, "해당 보호자를 찾을 수 없어요")
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    existing = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if existing:
        return {"already_linked": True}

    session.add(CaregiverPatient(caregiver_id=caregiver_id, patient_id=patient_id))
    session.commit()
    return {"linked": True, "caregiver_id": caregiver_id, "patient_id": patient_id}


@router.delete("/caregivers/{caregiver_id}/patients/{patient_id}")
def unlink_caregiver_from_patient(
    caregiver_id: int, patient_id: int, session: Session = Depends(get_session)
):
    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if not link:
        raise HTTPException(404, "연결된 내역이 없어요")
    session.delete(link)
    session.commit()
    return {"unlinked": True}


# ══════════════════════════════════════════
# 복약 일정 (MedicationSchedule) CRUD — patient_id 필수로 변경
# ══════════════════════════════════════════
class ScheduleCreate(BaseModel):
    patient_id: int
    drug_name: str
    time_slot: str  # "아침" / "점심" / "저녁" 등 자유 텍스트
    memo: str | None = None


class ScheduleUpdate(BaseModel):
    drug_name: str | None = None
    time_slot: str | None = None
    memo: str | None = None
    active: bool | None = None


class CheckIn(BaseModel):
    status: str  # "taken" | "skipped" (Dashboard.tsx IntakeStatus와 동일)


@router.post("/schedules", response_model=MedicationSchedule)
def create_schedule(payload: ScheduleCreate, session: Session = Depends(get_session)):
    if not session.get(Patient, payload.patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")
    schedule = MedicationSchedule(**payload.model_dump())
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.get("/schedules", response_model=list[MedicationSchedule])
def list_schedules(
    patient_id: int | None = None, active_only: bool = True, session: Session = Depends(get_session)
):
    query = select(MedicationSchedule)
    if patient_id is not None:
        query = query.where(MedicationSchedule.patient_id == patient_id)
    if active_only:
        query = query.where(MedicationSchedule.active == True)  # noqa: E712
    return session.exec(query).all()


@router.patch("/schedules/{schedule_id}", response_model=MedicationSchedule)
def update_schedule(
    schedule_id: int, payload: ScheduleUpdate, session: Session = Depends(get_session)
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, session: Session = Depends(get_session)):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")
    logs = session.exec(
        select(MedicationLog).where(MedicationLog.schedule_id == schedule_id)
    ).all()
    for log in logs:
        session.delete(log)
    session.delete(schedule)
    session.commit()
    return {"deleted": schedule_id}


# ── 오늘 복약 체크 (Dashboard.tsx의 updateStatus에 대응) ──
@router.post("/schedules/{schedule_id}/check")
def check_intake(schedule_id: int, payload: CheckIn, session: Session = Depends(get_session)):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")

    today_str = date.today().isoformat()
    existing = session.exec(
        select(MedicationLog)
        .where(MedicationLog.schedule_id == schedule_id)
        .where(func.date(MedicationLog.checked_at) == today_str)
    ).first()

    if existing:
        existing.status = payload.status
        existing.checked_at = datetime.now()
        session.add(existing)
    else:
        session.add(MedicationLog(schedule_id=schedule_id, status=payload.status))

    session.commit()
    return {"schedule_id": schedule_id, "status": payload.status}


# ── [7/6 추가] 오늘자 체크 취소 → pending으로 되돌리기 (Dashboard.tsx "아직이요" 버튼용) ──
@router.delete("/schedules/{schedule_id}/check")
def clear_intake(schedule_id: int, session: Session = Depends(get_session)):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")

    today_str = date.today().isoformat()
    existing = session.exec(
        select(MedicationLog)
        .where(MedicationLog.schedule_id == schedule_id)
        .where(func.date(MedicationLog.checked_at) == today_str)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()

    return {"schedule_id": schedule_id, "status": "pending"}


# ── Dashboard.tsx가 그대로 쓸 수 있는 오늘자 통합 조회 [7/6: patient_id 필수로 변경] ──
@router.get("/today")
def get_today(patient_id: int, session: Session = Depends(get_session)):
    """
    반환 형태 (Dashboard.tsx의 Medication[] 그대로):
    [{ "id": "1", "name": "암로디핀 5mg", "time": "아침", "note": "", "status": "pending" }]
    오늘 체크 기록이 없으면 status는 자동으로 "pending"

    ⚠️ patient_id는 필수 쿼리 파라미터입니다. 로그인이 없으므로 프론트에서
    "환자 선택" 단계(GET /caregivers/{id}/patients 결과 중 선택) 이후 값을 들고 호출해야 함.
    데모 시드 데이터의 기본 환자는 patient_id=1.
    """
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    today_str = date.today().isoformat()
    schedules = session.exec(
        select(MedicationSchedule)
        .where(MedicationSchedule.patient_id == patient_id)
        .where(MedicationSchedule.active == True)  # noqa: E712
    ).all()

    result = []
    for s in schedules:
        log = session.exec(
            select(MedicationLog)
            .where(MedicationLog.schedule_id == s.id)
            .where(func.date(MedicationLog.checked_at) == today_str)
        ).first()
        result.append(
            {
                "id": str(s.id),
                "name": s.drug_name,
                "time": s.time_slot,
                "note": s.memo or "",
                "status": log.status if log else "pending",
            }
        )
    return result
