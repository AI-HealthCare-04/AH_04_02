"""
monitoring_router.py — 담당: 박소정 (멘토 최우선 지정 기능)

[7/6 변경] 환자 구분 추가 — 한 보호자가 여러 환자를 케어할 수 있도록
patients / caregivers / caregiver_patients(다대다)를 도입함.

[7/10~7/13] issue #21(인가) — 보호자 전용 화면(Login.tsx/PatientManagement.tsx/
MonitoringDashboard.tsx/MyPage.tsx)에서만 쓰는 엔드포인트는 `Depends(get_current_caregiver)` +
`require_patient_access`로 보호자 본인 것만 허용합니다.

Dashboard.tsx/Schedule.tsx/Notification.tsx/Records.tsx/Connect.tsx처럼 "보호자 로그인"과
"환자 본인 로그인"이 같은 화면·API를 공유하는 곳은 `Depends(get_current_actor)` +
`require_actor_patient_access`로 보호합니다 — 토큰이 보호자 것이면 연결된 환자인지,
환자 본인 것이면 자기 자신인지 확인합니다 (issue #28: 환자 본인도 가입 직후 로그인해서
토큰을 받도록 SignUp.tsx를 먼저 고쳤습니다).

기본 흐름:
1) POST /auth/login → access_token 발급 (보호자·환자 둘 다)
2) GET /caregivers/{id}/patients  → 그 보호자가 케어하는 환자 목록 (caregiver_id는 토큰의 본인 것만 허용)
3) 환자 하나를 고르면 그 patient_id로 /monitoring/today?patient_id=... 호출
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from core.auth import hash_password
from core.database import get_session
from core.dependencies import (
    Actor,
    get_current_actor,
    get_current_caregiver,
    require_actor_patient_access,
    require_patient_access,
)
from core.security import normalize_email
from fastapi import APIRouter, Depends, HTTPException
from models import (
    Caregiver,
    CaregiverPatient,
    MedicalRecord,
    MedicationLog,
    MedicationSchedule,
    OcrResult,
    Patient,
)
from pydantic import BaseModel
from sqlmodel import Session, func, select

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# ══════════════════════════════════════════
# 환자 (Patient) CRUD
# ══════════════════════════════════════════
class PatientCreate(BaseModel):
    name: str
    note: str | None = None
    phone: str | None = None  # [7/8 추가] 회원가입(SignUp.tsx)
    email: str | None = None  # [7/8 추가] 회원가입 "아이디"
    birth_date: str | None = None  # [7/8 추가]
    password: str | None = None  # [7/8 추가] 평문으로 받아서 저장 전에 반드시 해시 처리
    push_enabled: bool = True
    sms_enabled: bool = False
    email_opt_in: bool = False


class PatientUpdate(BaseModel):
    name: str | None = None
    note: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None


class PatientPublic(BaseModel):
    """hashed_password는 API 응답에 노출하지 않기 위한 응답 전용 모델 (CaregiverPublic과 동일한 원칙)"""
    id: int
    name: str
    note: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None
    push_enabled: bool = True
    sms_enabled: bool = False
    email_opt_in: bool = False
    created_at: datetime


@router.post("/patients", response_model=PatientPublic)
def create_patient(payload: PatientCreate, session: Session = Depends(get_session)):
    # [2026-07-14] 이메일 앞뒤 공백/대소문자가 섞이면 같은 사람이 다른 계정으로 취급돼
    # 로그인이 안 되는 문제가 있었다 — 저장 전에 항상 정규화한다.
    email = normalize_email(payload.email) if payload.email else None
    # [2026-07-14] Patient.email엔 이제 유니크 제약이 있지만, DB의 raw IntegrityError
    # 대신 사용자에게 명확한 409를 주기 위해 사전 검사도 함께 한다.
    if email and session.exec(select(Patient).where(Patient.email == email)).first():
        raise HTTPException(409, "이미 사용중인 이메일입니다.")

    # [7/9] name/phone은 Patient의 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 —
    # 나머지 필드로 먼저 만들고 .name/.phone에 대입해서 암호화·해시 처리한다.
    data = payload.model_dump(exclude={"password", "name", "phone", "email"})
    patient = Patient(
        **data,
        email=email,
        hashed_password=hash_password(payload.password) if payload.password else None,
    )
    patient.name = payload.name
    patient.phone = payload.phone
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.get("/patients", response_model=list[PatientPublic])
def list_patients(actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)):
    """[7/13] MyPage.tsx가 "본인"을 찾는 데만 쓴다 — 전체 목록이 아니라 토큰의 본인
    범위로 좁힌다 (환자 본인 로그인이면 자기 자신, 보호자면 케어하는 환자 전체)."""
    role, subject = actor
    if role == "patient":
        return [subject]
    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.caregiver_id == subject.id)
    ).all()
    patient_ids = [link.patient_id for link in links]
    if not patient_ids:
        return []
    return session.exec(select(Patient).where(Patient.id.in_(patient_ids))).all()


@router.patch("/patients/{patient_id}", response_model=PatientPublic)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    require_patient_access(patient_id, caregiver, session)
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
def delete_patient(
    patient_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    require_patient_access(patient_id, caregiver, session)
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
    relation_type: str = "guardian"  # guardian / caregiver / life_support_worker / social_worker / organization
    phone: str | None = None  # [7/8 추가] 회원가입 연락처
    email: str | None = None  # [7/8 추가] 회원가입 "아이디"(개인) / "담당자 이메일"(단체)
    birth_date: str | None = None  # [7/8 추가]
    password: str | None = None  # [7/8 추가] 평문으로 받아서 저장 전에 반드시 해시 처리
    push_enabled: bool = True  # [7/8 추가] 회원가입 "Push 알림 허용" (필수)
    sms_enabled: bool = False  # [7/8 추가] 회원가입 "문자(SMS) 수신 허용" (선택)
    email_opt_in: bool = False  # [7/8 추가] 회원가입 "이메일 수신 허용" (선택)
    # [7/8 추가] relation_type == "organization"일 때만 의미있는 필드들
    org_name: str | None = None
    org_type: str | None = None
    business_reg_no: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None


class CaregiverPublic(BaseModel):
    """hashed_password는 API 응답에 노출하지 않기 위한 응답 전용 모델"""
    id: int
    name: str
    relation_type: str
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None
    push_enabled: bool = True
    sms_enabled: bool = False
    email_opt_in: bool = False
    org_name: str | None = None
    org_type: str | None = None
    business_reg_no: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None
    created_at: datetime


@router.post("/caregivers", response_model=CaregiverPublic)
def create_caregiver(payload: CaregiverCreate, session: Session = Depends(get_session)):
    # [2026-07-14] Patient와 동일하게 이메일 정규화 + 사전 중복검사(친절한 409) 적용.
    # Caregiver.email은 원래부터 DB 유니크 제약이 있었지만, 정규화 없이 비교하면
    # "Test@x.com"과 "test@x.com"을 다른 값으로 보고 제약을 통과시켜버릴 수 있었다.
    email = normalize_email(payload.email) if payload.email else None
    if email and session.exec(select(Caregiver).where(Caregiver.email == email)).first():
        raise HTTPException(409, "이미 사용중인 이메일입니다.")

    # [7/9] name/phone은 Caregiver의 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 —
    # 나머지 필드로 먼저 만들고 .name/.phone에 대입해서 암호화·해시 처리한다.
    data = payload.model_dump(exclude={"password", "name", "phone", "email"})
    caregiver = Caregiver(
        **data,
        email=email,
        hashed_password=hash_password(payload.password) if payload.password else None,
    )
    caregiver.name = payload.name
    caregiver.phone = payload.phone
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


@router.get("/caregivers", response_model=list[CaregiverPublic])
def list_caregivers(caregiver: Caregiver = Depends(get_current_caregiver)):
    """[7/10] 전체 보호자 목록이 아니라 로그인한 본인만 반환 (MyPage.tsx가 본인 조회용으로만 씀, issue #21)."""
    return [caregiver]


@router.get("/caregivers/{caregiver_id}/patients", response_model=list[PatientPublic])
def list_patients_of_caregiver(
    caregiver_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """핵심 기능: 이 보호자가 케어하는 환자 전체 목록 (여러 명 가능)"""
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "다른 보호자의 환자 목록은 볼 수 없어요")

    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.caregiver_id == caregiver_id)
    ).all()
    patient_ids = [link.patient_id for link in links]
    if not patient_ids:
        return []
    return session.exec(select(Patient).where(Patient.id.in_(patient_ids))).all()


@router.get("/patients/{patient_id}/caregivers", response_model=list[CaregiverPublic])
def list_caregivers_of_patient(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """[7/8 추가] 반대 방향 조회 — 이 환자를 케어하는 보호자 전체 목록 (Connect.tsx '연결된 사람' 표에 사용)."""
    require_actor_patient_access(patient_id, actor, session)

    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.patient_id == patient_id)
    ).all()
    caregiver_ids = [link.caregiver_id for link in links]
    if not caregiver_ids:
        return []
    return session.exec(select(Caregiver).where(Caregiver.id.in_(caregiver_ids))).all()


@router.post("/caregivers/{caregiver_id}/patients/{patient_id}")
def link_caregiver_to_patient(
    caregiver_id: int,
    patient_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """보호자-환자 연결 추가.

    [7/13] 방금 본인이 만든 환자를 최초로 연결하는 용도로만 허용한다 — patient_id는
    자동증가 정수라 순차 추측이 가능한데, 이 엔드포인트가 "본인 계정으로 연결하는지"만
    확인하고 "이 환자에 접근할 권한이 애초에 있는지"는 확인하지 않으면, 누구나 회원가입 후
    다른 사람의 환자에 자기 자신을 자가 연결해 그 환자의 처방전·복약기록을 그대로 볼 수
    있었다(issue #21 인가 로직 전체를 무력화하는 구멍). 이미 다른 보호자가 연결된 환자에
    추가로 연결하려면 반드시 초대 토큰 기반 accept_invitation()을 거쳐야 한다.
    """
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "본인 계정으로만 환자를 연결할 수 있어요")
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    existing = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if existing:
        return {"already_linked": True}

    has_any_caregiver = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if has_any_caregiver:
        raise HTTPException(403, "이미 다른 보호자가 연결된 환자예요. 추가 연결은 초대 링크를 통해서만 가능해요.")

    session.add(CaregiverPatient(caregiver_id=caregiver_id, patient_id=patient_id))
    session.commit()
    return {"linked": True, "caregiver_id": caregiver_id, "patient_id": patient_id}


@router.delete("/caregivers/{caregiver_id}/patients/{patient_id}")
def unlink_caregiver_from_patient(
    caregiver_id: int,
    patient_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """Connect.tsx — 보호자 본인이거나 환자 본인이어야 그 연결을 해제할 수 있다."""
    role, subject = actor
    if (role == "caregiver" and subject.id != caregiver_id) or (role == "patient" and subject.id != patient_id):
        raise HTTPException(403, "이 연결을 해제할 권한이 없어요")
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
    time_slot: str  # [7/8 변경] "08:00" 같은 실제 시각 문자열
    dose_timing: str | None = None  # [7/8 추가] 공복 / 아침 식후 / 점심 식전 / 점심 식후 / 저녁 식전 / 저녁 식후
    caregiver_alert: bool = True  # [7/8 추가]
    memo: str | None = None


class ScheduleUpdate(BaseModel):
    drug_name: str | None = None
    time_slot: str | None = None
    dose_timing: str | None = None
    caregiver_alert: bool | None = None
    memo: str | None = None
    active: bool | None = None


class CheckIn(BaseModel):
    status: str  # "taken" | "skipped" (Dashboard.tsx IntakeStatus와 동일)
    # [7/9 추가] 보호자가 모니터링 화면에서 대신 체크할 때만 채워짐 — 환자 본인이 체크하면 None
    confirmed_by_caregiver_id: int | None = None


@router.post("/schedules", response_model=MedicationSchedule)
def create_schedule(
    payload: ScheduleCreate, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    require_actor_patient_access(payload.patient_id, actor, session)
    schedule = MedicationSchedule(**payload.model_dump())
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.get("/schedules", response_model=list[MedicationSchedule])
def list_schedules(
    patient_id: int,
    active_only: bool = True,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    query = select(MedicationSchedule).where(MedicationSchedule.patient_id == patient_id)
    if active_only:
        query = query.where(MedicationSchedule.active == True)  # noqa: E712
    return session.exec(query).all()


@router.patch("/schedules/{schedule_id}", response_model=MedicationSchedule)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")
    require_actor_patient_access(schedule.patient_id, actor, session)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.get("/patients/{patient_id}/known-drugs")
def list_known_drugs(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """
    [7/8 추가] '새 일정 추가' 모달의 "약물 선택" 드롭다운용 — 이 환자의 처방전에서
    실제로 OCR로 인식된 약 이름 + 이미 등록된 복약 일정의 약 이름을 합쳐 중복 제거해서 반환.
    가짜 약물 목록이 아니라 이 환자 데이터에 실제로 존재하는 약 이름만 내려줍니다.
    """
    require_actor_patient_access(patient_id, actor, session)
    record_ids = session.exec(
        select(MedicalRecord.id).where(MedicalRecord.patient_id == patient_id)
    ).all()
    ocr_names = (
        session.exec(
            select(OcrResult.drug_name).where(OcrResult.record_id.in_(record_ids))
        ).all()
        if record_ids
        else []
    )
    schedule_names = session.exec(
        select(MedicationSchedule.drug_name).where(MedicationSchedule.patient_id == patient_id)
    ).all()
    names = sorted({n.strip() for n in [*ocr_names, *schedule_names] if n and n.strip()})
    return names


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")
    require_actor_patient_access(schedule.patient_id, actor, session)
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
def check_intake(
    schedule_id: int,
    payload: CheckIn,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")
    require_actor_patient_access(schedule.patient_id, actor, session)

    today_str = date.today().isoformat()
    existing = session.exec(
        select(MedicationLog)
        .where(MedicationLog.schedule_id == schedule_id)
        .where(func.date(MedicationLog.checked_at) == today_str)
    ).first()

    confirmed_by_type = "caregiver" if payload.confirmed_by_caregiver_id else "patient"

    if existing:
        existing.status = payload.status
        existing.checked_at = datetime.now()
        existing.confirmed_by_type = confirmed_by_type
        existing.confirmed_by_caregiver_id = payload.confirmed_by_caregiver_id
        session.add(existing)
    else:
        session.add(
            MedicationLog(
                schedule_id=schedule_id,
                status=payload.status,
                confirmed_by_type=confirmed_by_type,
                confirmed_by_caregiver_id=payload.confirmed_by_caregiver_id,
            )
        )

    session.commit()
    return {"schedule_id": schedule_id, "status": payload.status}


# ── [7/6 추가] 오늘자 체크 취소 → pending으로 되돌리기 (Dashboard.tsx "아직이요" 버튼용) ──
@router.delete("/schedules/{schedule_id}/check")
def clear_intake(
    schedule_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "해당 일정을 찾을 수 없어요")
    require_actor_patient_access(schedule.patient_id, actor, session)

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


# ── [7/8 추가] 모니터링대시보드(보호자용) 캘린더·이행률 계산용 원본 로그 ──
@router.get("/logs")
def list_logs(
    patient_id: int,
    days: int = 30,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    최근 N일간의 복약 체크 기록을 스케줄명과 함께 반환합니다.
    프론트(모니터링대시보드)가 이 원본 로그로 캘린더 점 색상·주간 이행률·최근 기록 표를 직접 계산합니다.
    (별도 집계 테이블 없이 MedicationLog를 그대로 조회하는 방식 — schedule_v6 단순화 원칙과 동일)
    """
    require_actor_patient_access(patient_id, actor, session)

    schedules = session.exec(
        select(MedicationSchedule).where(MedicationSchedule.patient_id == patient_id)
    ).all()
    schedule_map = {s.id: s for s in schedules}
    if not schedule_map:
        return []

    since = datetime.now() - timedelta(days=days)
    logs = session.exec(
        select(MedicationLog)
        .where(MedicationLog.schedule_id.in_(list(schedule_map.keys())))
        .where(MedicationLog.checked_at >= since)
        .order_by(MedicationLog.checked_at.desc())
    ).all()

    caregiver_ids = {log.confirmed_by_caregiver_id for log in logs if log.confirmed_by_caregiver_id}
    caregiver_names = {
        c.id: c.name for c in session.exec(select(Caregiver).where(Caregiver.id.in_(caregiver_ids)))
    } if caregiver_ids else {}

    return [
        {
            "id": log.id,
            "schedule_id": log.schedule_id,
            "drug_name": schedule_map[log.schedule_id].drug_name,
            "time_slot": schedule_map[log.schedule_id].time_slot,
            "status": log.status,
            "checked_at": log.checked_at.isoformat(),
            "confirmed_by_type": log.confirmed_by_type,
            "confirmed_by_name": (
                caregiver_names.get(log.confirmed_by_caregiver_id, "보호자")
                if log.confirmed_by_type == "caregiver"
                else "본인"
            ),
        }
        for log in logs
    ]


# ── Dashboard.tsx가 그대로 쓸 수 있는 오늘자 통합 조회 [7/6: patient_id 필수로 변경] ──
@router.get("/today")
def get_today(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """
    반환 형태 (Dashboard.tsx의 Medication[] 그대로):
    [{ "id": "1", "name": "암로디핀 5mg", "time": "아침", "note": "", "status": "pending" }]
    오늘 체크 기록이 없으면 status는 자동으로 "pending"
    """
    require_actor_patient_access(patient_id, actor, session)

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
