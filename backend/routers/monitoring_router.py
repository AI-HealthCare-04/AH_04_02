"""
monitoring_router.py ? ??: ??? (?? ??? ?? ??)

[7/6 ??] ?? ?? ?? ? ? ???? ?? ??? ??? ? ???
patients / caregivers / caregiver_patients(???)? ???.

[7/10~7/13] issue #21(??) ? ??? ?? ??(Login.tsx/PatientManagement.tsx/
MonitoringDashboard.tsx/MyPage.tsx)??? ?? ?????? `Depends(get_current_caregiver)` +
`require_patient_access`? ??? ?? ?? ?????.

Dashboard.tsx/Schedule.tsx/Notification.tsx/Records.tsx/Connect.tsx?? "??? ???"?
"?? ?? ???"? ?? ???API? ???? ?? `Depends(get_current_actor)` +
`require_actor_patient_access`? ????? ? ??? ??? ??? ??? ????,
?? ?? ??? ?? ???? ????? (issue #28: ?? ??? ?? ?? ?????
??? ??? SignUp.tsx? ?? ?????).

?? ??:
1) POST /auth/login ? access_token ?? (?????? ? ?)
2) GET /caregivers/{id}/patients  ? ? ???? ???? ?? ?? (caregiver_id? ??? ?? ?? ??)
3) ?? ??? ??? ? patient_id? /monitoring/today?patient_id=... ??
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from core.audit import record_audit_log
from core.auth import hash_password
from core.database import get_session
from core.dependencies import (
    Actor,
    get_current_actor,
    get_current_caregiver,
    require_actor_patient_access,
    require_patient_access,
)
from core.relation_notices import create_relation_notice
from core.schedule_alerts import effective_alert_caregiver_ids, linked_caregiver_ids
from core.security import hash_phone, normalize_email
from fastapi import APIRouter, Depends, HTTPException
from models import (
    Caregiver,
    CaregiverPatient,
    MedicalRecord,
    MedicationLog,
    MedicationRecord,
    MedicationSchedule,
    NotificationLog,
    OcrResult,
    Patient,
    ScheduleCaregiverAlert,
)
from pydantic import BaseModel
from sqlmodel import Session, func, select

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# ??????????????????????????????????????????
# ?? (Patient) CRUD
# ??????????????????????????????????????????
class PatientCreate(BaseModel):
    name: str
    note: str | None = None
    phone: str | None = None  # [7/8 ??] ????(SignUp.tsx)
    email: str | None = None  # [7/8 ??] ???? "???"
    birth_date: str | None = None  # [7/8 ??]
    # [2026-07-22 ??] ?? ?? ???(Figma ??)? "??" ??? ? ?? ?? select?
    # "male"/"female" ? ? ??? ???(??? ?? ??? ? ???? ??).
    gender: Literal["male", "female"] | None = None
    password: str | None = None  # [7/8 ??] ???? ??? ?? ?? ??? ?? ??
    push_enabled: bool = True
    sms_enabled: bool = False
    email_opt_in: bool = False


class PatientUpdate(BaseModel):
    name: str | None = None
    note: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None
    gender: Literal["male", "female"] | None = None
    # [2026-07-22 ??] "? ??"(MyInfo.tsx)?? ???? ? ?? ?? ?? ??? ?? ??
    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    email_opt_in: bool | None = None


class PatientPublic(BaseModel):
    """hashed_password? API ??? ???? ?? ?? ?? ?? ?? (CaregiverPublic? ??? ??)"""
    id: int
    name: str
    note: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    push_enabled: bool = True
    sms_enabled: bool = False
    email_opt_in: bool = False
    created_at: datetime
    breakfast_time: str | None = None
    breakfast_regular: bool | None = None
    lunch_time: str | None = None
    lunch_regular: bool | None = None
    dinner_time: str | None = None
    dinner_regular: bool | None = None
    # [2026-07-22 ??] ?? ?? ???(PatientManagement.tsx)? "???"/"??" ??? ?
    # ?? ???????? ?? ? ?? ???(None/"none")?? ??. ?? ??? ??
    # ??? ??? ?? ??? GET /caregivers/{id}/patients??? ???.
    diagnoses: str | None = None
    medication_status: Literal["active", "paused", "none"] = "none"
    # [2026-07-23 ??] ?? ?? ??? ? ??? "?? ??" ????? ? ?? ??
    # ??? ???? GET /caregivers/{id}/patients??? ???.
    today_status: Literal["ok", "missed"] = "ok"
    # [2026-07-30 ??] "?? ??"? ??? "? ????? ?? ?? ??" ?
    # (CaregiverPatient.notifications_enabled) ? ?? ?? ??? ????
    # GET /caregivers/{id}/patients??? ?? ?? ???.
    notifications_enabled: bool = True


class MealTimesUpdate(BaseModel):
    breakfast_time: str | None = None
    breakfast_regular: bool | None = None
    lunch_time: str | None = None
    lunch_regular: bool | None = None
    dinner_time: str | None = None
    dinner_regular: bool | None = None


def _register_patient(payload: PatientCreate, session: Session) -> Patient:
    """?? Patient ?? ?? ? create_patient ?????? ?????? ?? ??
    (care_router.accept_invitation) ???? ????? ?? ??."""
    # [2026-07-14] ??? ?? ??/????? ??? ?? ??? ?? ???? ???
    # ???? ? ?? ??? ??? ? ?? ?? ?? ?????.
    email = normalize_email(payload.email) if payload.email else None
    # [2026-07-14] Patient.email? ?? ??? ??? ???, DB? raw IntegrityError
    # ?? ????? ??? 409? ?? ?? ?? ??? ?? ??.
    if email and session.exec(select(Patient).where(Patient.email == email)).first():
        raise HTTPException(409, "?? ???? ??????.")

    # [2026-07-22 ??] phone_hash? email? ?? ??? ??? ???, ??? ?????
    # ???? ??? ??? ?? ??? ???? ? auth_router._find_by_identifier?
    # phone_hash? ??? ? `.first()`? ?? ???, ??? ??? ?? ?(?? ?
    # ?? ?? ?? ???) ?? ???? ?? ??? ??? ????? ? ???
    # ??? ??? ????(SignUp.tsx "?? ??? ?????"). email? ????
    # ?? ??? ???.
    if payload.phone and session.exec(select(Patient).where(Patient.phone_hash == hash_phone(payload.phone))).first():
        raise HTTPException(409, "?? ???? ???????.")

    # [7/9] name/phone? Patient? ????(??? setter)? ??? kwarg? ? ?? ?
    # ??? ??? ?? ??? .name/.phone? ???? ?????? ????.
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


@router.post("/patients", response_model=PatientPublic)
def create_patient(payload: PatientCreate, session: Session = Depends(get_session)):
    return _register_patient(payload, session)


@router.get("/patients/check-duplicate")
def check_patient_duplicate(
    email: str | None = None,
    phone: str | None = None,
    session: Session = Depends(get_session),
):
    """[2026-07-23 ??] ????(SignUp.tsx)?? ???/????? ???? ?? ???
    ??? ?(onBlur) ?? ?? ??? ???? ?? ??? ????? ? ??? ???
    ?? _register_patient? ??? ?? ?? ??? ?????."""
    email_taken = False
    if email:
        normalized = normalize_email(email)
        email_taken = session.exec(select(Patient).where(Patient.email == normalized)).first() is not None
    phone_taken = False
    if phone:
        phone_taken = session.exec(
            select(Patient).where(Patient.phone_hash == hash_phone(phone))
        ).first() is not None
    return {"email_taken": email_taken, "phone_taken": phone_taken}


@router.get("/patients", response_model=list[PatientPublic])
def list_patients(actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)):
    """[7/13] MyPage.tsx? "??"? ?? ?? ?? ? ?? ??? ??? ??? ??
    ??? ??? (?? ?? ????? ?? ??, ???? ???? ?? ??)."""
    role, subject = actor
    if role == "patient":
        return [subject]
    links = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == subject.id)
        .where(CaregiverPatient.status != "revoked")
    ).all()
    patient_ids = [link.patient_id for link in links]
    if not patient_ids:
        return []
    return session.exec(select(Patient).where(Patient.id.in_(patient_ids))).all()


@router.patch("/patients/{patient_id}", response_model=PatientPublic)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[2026-07-22 ??] ???? ??? ?? ??? "? ??"(MyInfo.tsx)?? ??
    ??? ?? ? ??? ?? actor ?? ??? ???(???? ??? ????,
    ?? ???? ?? ???? ?? ? require_actor_patient_access)."""
    require_actor_patient_access(patient_id, actor, session)
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "?? ??? ?? ? ???")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"]:
        email = normalize_email(updates["email"])
        existing = session.exec(select(Patient).where(Patient.email == email)).first()
        if existing and existing.id != patient_id:
            raise HTTPException(409, "?? ???? ??????.")
        updates["email"] = email
    elif "email" in updates:
        # [2026-07-23 ??, ?? ?? ??] ? ???? ??? ???? email?
        # unique=True? ?? ??? ? ???? ?? ?? unique ?? ??? ?? ?
        # "??"? None?? ????? ????(?? ??? ??? None??? ??).
        updates["email"] = None
    if "phone" in updates and updates["phone"]:
        existing = session.exec(
            select(Patient).where(Patient.phone_hash == hash_phone(updates["phone"]))
        ).first()
        if existing and existing.id != patient_id:
            raise HTTPException(409, "?? ???? ???????.")

    before = {key: getattr(patient, key, None) for key in updates}
    for key, value in updates.items():
        setattr(patient, key, value)
    session.add(patient)
    record_audit_log(session, "patients", patient_id, actor, before, updates)
    session.commit()
    session.refresh(patient)
    return patient


@router.put("/patients/{patient_id}/meal-times", response_model=PatientPublic)
def update_meal_times(
    patient_id: int,
    payload: MealTimesUpdate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[2026-07-16 ??] ???? ?? ???? ??(MealTimeCheck.tsx) ???.
    ?? ?? ??? ??(?? ??) ????? caregiver ??? ??? actor ?? ??? ??
    (update_patient?? caregiver ???? ?? ?? ????? ??? ? ??)."""
    require_actor_patient_access(patient_id, actor, session)
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "?? ??? ?? ? ???")
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
        raise HTTPException(404, "?? ??? ?? ? ???")
    links = session.exec(
        select(CaregiverPatient).where(CaregiverPatient.patient_id == patient_id)
    ).all()
    for link in links:
        session.delete(link)
    session.delete(patient)
    session.commit()
    return {"deleted": patient_id}


# ??????????????????????????????????????????
# ????????? (Caregiver) + ?? ??
# ??????????????????????????????????????????
class CaregiverCreate(BaseModel):
    name: str
    # [2026-07-16 ??] ?? ?? ??(frontend/src/pages/SignUp.tsx)? ??? ??
    # guardian(??)? organization(?????) ????. ?? ???
    # care_router.InvitationCreate?? Connect.tsx? 4? ???
    # (guardian/caregiver/life_support_worker/social_worker)? ??? ????.
    # DB ??? VARCHAR? ?? ??? ??/?? ?? ??? ????? ?? ????? ???.
    relation_type: Literal["guardian", "organization"] = "guardian"
    phone: str | None = None  # [7/8 ??] ???? ???
    email: str | None = None  # [7/8 ??] ???? "???"(??) / "??? ???"(??)
    birth_date: str | None = None  # [7/8 ??]
    password: str | None = None  # [7/8 ??] ???? ??? ?? ?? ??? ?? ??
    push_enabled: bool = True  # [7/8 ??] ???? "Push ?? ??" (??)
    sms_enabled: bool = False  # [7/8 ??] ???? "??(SMS) ?? ??" (??)
    email_opt_in: bool = False  # [7/8 ??] ???? "??? ?? ??" (??)
    # [7/8 ??] relation_type == "organization"? ?? ???? ???
    org_name: str | None = None
    org_type: str | None = None
    business_reg_no: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None


class CaregiverPublic(BaseModel):
    """hashed_password? API ??? ???? ?? ?? ?? ?? ??"""
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
    # [2026-07-14] Patient? ???? ??? ??? + ?? ????(??? 409) ??.
    # Caregiver.email? ???? DB ??? ??? ????, ??? ?? ????
    # "Test@x.com"? "test@x.com"? ?? ??? ?? ??? ?????? ? ???.
    # [2026-07-23 ??] phone_hash? ??? ??? email? ??? ??? ???
    # relation_type??? ??? ???(?? phone_hash ?? ??).
    email = normalize_email(payload.email) if payload.email else None
    if (
        email
        and session.exec(
            select(Caregiver)
            .where(Caregiver.email == email)
            .where(Caregiver.relation_type == payload.relation_type)
        ).first()
    ):
        raise HTTPException(409, "?? ???? ??????.")

    # [2026-07-22 ??] Patient._register_patient? ??? ?? ? phone_hash ???
    # ??? ?? ?? ???? ??? ??? ????, ??? ? `.first()`? ??
    # ???? ?? ??? ??? ??? ???? ?? ?? ???? ????.
    # [2026-07-22 ??] ?, ?? ??? ???(??)??? ??? ??(????? ?)
    # ??? ? ??, ?? ?? ??? ??? ?? ? ??(??? ????? ???
    # ??, ??? ?????? ?? ? ? ?? ?? ?? ??) ? ??? ?????
    # ??? ??? ??? relation_type(?? ??)??? ??? ???. Patient?
    # ??? ????? ??? ?? ???? ????.
    if (
        payload.phone
        and session.exec(
            select(Caregiver)
            .where(Caregiver.phone_hash == hash_phone(payload.phone))
            .where(Caregiver.relation_type == payload.relation_type)
        ).first()
    ):
        raise HTTPException(409, "?? ???? ???????.")

    # [7/9] name/phone? Caregiver? ????(??? setter)? ??? kwarg? ? ?? ?
    # ??? ??? ?? ??? .name/.phone? ???? ?????? ????.
    data = payload.model_dump(exclude={"password", "name", "phone", "email"})
    caregiver = Caregiver(
        **data,
        email=email,
        hashed_password=hash_password(payload.password) if payload.password else None,
    )
    caregiver.name = (
        payload.manager_name.strip()
        if payload.relation_type == "organization" and payload.manager_name and payload.manager_name.strip()
        else payload.name
    )
    caregiver.phone = payload.phone
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


@router.get("/caregivers/check-duplicate")
def check_caregiver_duplicate(
    relation_type: Literal["guardian", "organization"],
    email: str | None = None,
    phone: str | None = None,
    session: Session = Depends(get_session),
):
    """[2026-07-23 ??] check_patient_duplicate? ??? ?? ? create_caregiver? ??
    ?? ??(???????? ?? relation_type??? ??)? ??? ?????."""
    email_taken = False
    if email:
        normalized = normalize_email(email)
        email_taken = (
            session.exec(
                select(Caregiver)
                .where(Caregiver.email == normalized)
                .where(Caregiver.relation_type == relation_type)
            ).first()
            is not None
        )
    phone_taken = False
    if phone:
        phone_taken = (
            session.exec(
                select(Caregiver)
                .where(Caregiver.phone_hash == hash_phone(phone))
                .where(Caregiver.relation_type == relation_type)
            ).first()
            is not None
        )
    return {"email_taken": email_taken, "phone_taken": phone_taken}


@router.get("/caregivers", response_model=list[CaregiverPublic])
def list_caregivers(caregiver: Caregiver = Depends(get_current_caregiver)):
    """[7/10] ?? ??? ??? ??? ???? ??? ?? (MyPage.tsx? ?? ?????? ?, issue #21)."""
    return [caregiver]


class CaregiverUpdate(BaseModel):
    """[2026-07-22 ??] "? ??"(MyInfo.tsx)?? ???? ? ?? ??? ?? ?
    relation_type/password? ??? ? ???(??? ?? ?? ??? ??? ?? ??,
    ??? ?? ?? ???? ??? ??? ??)."""
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None
    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    email_opt_in: bool | None = None
    org_name: str | None = None
    org_type: str | None = None
    business_reg_no: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None


@router.patch("/caregivers/{caregiver_id}", response_model=CaregiverPublic)
def update_caregiver(
    caregiver_id: int,
    payload: CaregiverUpdate,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    if caregiver.id != caregiver_id:
        raise HTTPException(403, "?? ??? ??? ? ???.")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"]:
        email = normalize_email(updates["email"])
        existing = session.exec(
            select(Caregiver)
            .where(Caregiver.email == email)
            .where(Caregiver.relation_type == caregiver.relation_type)
        ).first()
        if existing and existing.id != caregiver_id:
            raise HTTPException(409, "?? ???? ??????.")
        updates["email"] = email
    elif "email" in updates:
        # [2026-07-23 ??, ?? ?? ??] update_patient? ??? ?? ? email?
        # unique=True? ? ???? ??? ???? ?? ??? ??? ? ????.
        updates["email"] = None
    if "phone" in updates and updates["phone"]:
        existing = session.exec(
            select(Caregiver)
            .where(Caregiver.phone_hash == hash_phone(updates["phone"]))
            .where(Caregiver.relation_type == caregiver.relation_type)
        ).first()
        if existing and existing.id != caregiver_id:
            raise HTTPException(409, "?? ???? ???????.")

    for key, value in updates.items():
        setattr(caregiver, key, value)
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


def _bulk_patient_diagnoses(session: Session, patient_ids: list[int]) -> dict[int, str | None]:
    """?? ?? ??? "???" ??? ? diagnosis? MedicalRecord(??? 1?)? ???
    OcrResult(? 1?? 1?)? ?? ? ????(soft-delete ??)? ?? ???? ????
    ?? ?? ?? ???? ?? "?"? ?????. ??? ?? ?? ??.

    [perf, N+1 ??] patient_id?? ?? ???? ? patient_ids ??? ?? ? ??
    bulk-select??? ??? ? ??? ?? patient_id?? ???? ?? ??? ???
    "?? ?? ?? + ?? ??" ??? ??? ????."""
    if not patient_ids:
        return {}
    rows = session.exec(
        select(MedicalRecord.patient_id, OcrResult.diagnosis)
        .join(MedicalRecord, OcrResult.record_id == MedicalRecord.id)
        .where(MedicalRecord.patient_id.in_(patient_ids))
        .where(MedicalRecord.deleted_at.is_(None))
        .where(OcrResult.diagnosis != "")
    ).all()
    diagnoses_by_patient: dict[int, list[str]] = {}
    for patient_id, diagnosis in rows:
        diagnoses_by_patient.setdefault(patient_id, []).append(diagnosis)
    return {
        patient_id: "?".join(dict.fromkeys(diagnoses))
        for patient_id, diagnoses in diagnoses_by_patient.items()
    }


def _bulk_patient_medication_and_today_status(
    session: Session, patient_ids: list[int]
) -> tuple[dict[int, Literal["active", "paused", "none"]], dict[int, Literal["ok", "missed"]]]:
    """?? ?? ??? "??"/"?? ??" ??? ? ??? ?? ?? ? ?
    (_patient_medication_status/_patient_today_status)??? ? ? MedicationSchedule?
    ?????, patient_ids ??? ?? ???? ? ?? bulk-select?? ?? ????.

    [perf, N+1 ??] ??? ???? "??" 1?? + "?? ??" ?? 2??(?? ??
    ?? + missed ??)? ???. ?? ??? bulk-select 1? + missed ?? bulk-select
    1?(?? ??? ??? ??? ? ?? ??? ??)?? ????.

    - ??: ?? ??? ???? ??? "active", ??? ??? ?? ?????
      "paused", ?? ??? "none".
    - ?? ??: ?? ??(NotificationLog kind="missed") ?? ??? ???? ???
      "missed", ??? "ok"(?? ??? ?? ?? ??? "ok").
    """
    medication_status: dict[int, Literal["active", "paused", "none"]] = {}
    today_status: dict[int, Literal["ok", "missed"]] = {}
    if not patient_ids:
        return medication_status, today_status

    schedule_rows = session.exec(
        select(MedicationSchedule.id, MedicationSchedule.patient_id, MedicationSchedule.active).where(
            MedicationSchedule.patient_id.in_(patient_ids)
        )
    ).all()

    actives_by_patient: dict[int, list[bool]] = {}
    active_schedule_ids_by_patient: dict[int, list[int]] = {}
    for schedule_id, patient_id, active in schedule_rows:
        actives_by_patient.setdefault(patient_id, []).append(active)
        if active:
            active_schedule_ids_by_patient.setdefault(patient_id, []).append(schedule_id)

    medication_status = {
        patient_id: ("active" if any(actives) else "paused") for patient_id, actives in actives_by_patient.items()
    }

    all_active_schedule_ids = [
        schedule_id for ids in active_schedule_ids_by_patient.values() for schedule_id in ids
    ]
    missed_schedule_ids: set[int] = set()
    if all_active_schedule_ids:
        today_str = date.today().isoformat()
        missed_schedule_ids = set(
            session.exec(
                select(NotificationLog.schedule_id)
                .where(NotificationLog.kind == "missed")
                .where(NotificationLog.due_date == today_str)
                .where(NotificationLog.schedule_id.in_(all_active_schedule_ids))
            ).all()
        )

    for patient_id in patient_ids:
        active_ids = active_schedule_ids_by_patient.get(patient_id, [])
        if not active_ids:
            today_status[patient_id] = "ok"
        else:
            today_status[patient_id] = (
                "missed" if any(sid in missed_schedule_ids for sid in active_ids) else "ok"
            )

    return medication_status, today_status


@router.get("/caregivers/{caregiver_id}/patients", response_model=list[PatientPublic])
def list_patients_of_caregiver(
    caregiver_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """?? ??: ? ???? ???? ?? ?? ?? (?? ? ??)

    [2026-07-22 ??] ?? ?? ???(Figma ??)? ????????? ???? ??,
    ORM ??? ??? ???? ?? PatientPublic?? ??? ? ??? ?? ?? ???.

    [perf, N+1 ??] ???? ?????????????? ?? ???? ? ?? K? ???
    ?? ? ?? bulk-select??? ??? ? ?? ?? K? ??? ???? ?? ????."""
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "?? ???? ?? ??? ? ? ???")

    links = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.status != "revoked")
    ).all()
    patient_ids = [link.patient_id for link in links]
    if not patient_ids:
        return []
    links_by_patient = {link.patient_id: link for link in links}
    patients = session.exec(select(Patient).where(Patient.id.in_(patient_ids))).all()

    diagnoses_by_patient = _bulk_patient_diagnoses(session, patient_ids)
    medication_status_by_patient, today_status_by_patient = _bulk_patient_medication_and_today_status(
        session, patient_ids
    )

    result = []
    for patient in patients:
        try:
            # [2026-07-30 ??] PII_ENCRYPTION_KEY? ?? ??? ???(?? ?? ??
            # ? ?) ??? ??? ??? ?? ??? name/phone ???(InvalidToken)?
            # ??? ??? ? ????? ?? ?? ??? 500?? ??? ? ? ??
            # ??? ???? ???? ?? ????.
            public = PatientPublic.model_validate(patient, from_attributes=True)
        except Exception:  # noqa: BLE001
            continue
        result.append(
            public.model_copy(
                update={
                    "diagnoses": diagnoses_by_patient.get(patient.id),
                    "medication_status": medication_status_by_patient.get(patient.id, "none"),
                    "today_status": today_status_by_patient.get(patient.id, "ok"),
                    "notifications_enabled": links_by_patient[patient.id].notifications_enabled,
                }
            )
        )
    return result


class CaregiverPatientNotificationsUpdate(BaseModel):
    enabled: bool


@router.patch("/caregivers/{caregiver_id}/patients/{patient_id}/notifications")
def update_caregiver_patient_notifications(
    caregiver_id: int,
    patient_id: int,
    payload: CaregiverPatientNotificationsUpdate,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """[2026-07-30 ??] ?? ??? ???? ??????? "? ?? ??? ? ???
    ? ?? ??"? ??? ?? ? ? ?? ? NotificationSetting(?? ??, ?? ????
    ???? ?)? ?? ?? (? ???, ? ??) ?? ??? ???."""
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "?? ???? ?? ??? ?? ? ???")

    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
        .where(CaregiverPatient.status != "revoked")
    ).first()
    if not link:
        raise HTTPException(404, "??? ??? ????")

    link.notifications_enabled = payload.enabled
    session.add(link)
    session.commit()
    return {"notifications_enabled": link.notifications_enabled}


@router.get("/patients/{patient_id}/caregivers", response_model=list[CaregiverPublic])
def list_caregivers_of_patient(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """[7/8 ??] ?? ?? ?? ? ? ??? ???? ??? ?? ?? (Connect.tsx '??? ??' ?? ??)."""
    require_actor_patient_access(patient_id, actor, session)

    links = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.patient_id == patient_id)
        .where(CaregiverPatient.status != "revoked")
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
    """???-?? ?? ??.

    [7/13] ?? ??? ?? ??? ??? ???? ???? ???? ? patient_id?
    ???? ??? ?? ??? ????, ? ?????? "?? ???? ?????"?
    ???? "? ??? ??? ??? ??? ???"? ???? ???, ??? ???? ?
    ?? ??? ??? ?? ??? ?? ??? ? ??? ????????? ??? ? ?
    ???(issue #21 ?? ?? ??? ????? ??). ?? ?? ???? ??? ???
    ??? ????? ??? ?? ?? ?? accept_invitation()? ??? ??.
    """
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "?? ????? ??? ??? ? ???")
    if not session.get(Patient, patient_id):
        raise HTTPException(404, "?? ??? ?? ? ???")

    existing = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if existing:
        if existing.status == "revoked":
            # [2026-07-23 ??] ??? ??? ???? ? ?? ? ??? ?? ??????.
            existing.status = "active"
            existing.revoked_at = None
            existing.revocation_requested_by = None
            existing.requested_by_role = None
            existing.revocation_reason = None
            existing.revocation_requested_at = None
            session.add(existing)
            session.commit()
            return {"linked": True, "caregiver_id": caregiver_id, "patient_id": patient_id}
        return {"already_linked": True}

    has_any_caregiver = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.patient_id == patient_id)
        .where(CaregiverPatient.status != "revoked")
    ).first()
    if has_any_caregiver:
        raise HTTPException(403, "?? ?? ???? ??? ????. ?? ??? ?? ??? ???? ????.")

    session.add(CaregiverPatient(caregiver_id=caregiver_id, patient_id=patient_id))
    session.commit()
    return {"linked": True, "caregiver_id": caregiver_id, "patient_id": patient_id}


@router.delete("/caregivers/{caregiver_id}/patients/{patient_id}")
def unlink_caregiver_from_patient(
    caregiver_id: int,
    patient_id: int,
    reason: str | None = None,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """Connect.tsx/PatientManagement.tsx ? ??? ????? ?? ????? ? ??? ??? ? ??.

    [2026-07-23 ??] ??(organization) ??? ??? ?? ?? ?? ?? ??? ? ???????
    ??? ???? ??? ???? ??? ?? ?? ????? ?? ?? ? ?? ??, ??(??
    ?? ?? ???)? ???? ??? ???(POST /trust/relations/{trust_id}/revocation-approval).
    ?? ??? ??? ???? ??? ??? ???? ??? ??? ???, ?? ??? ???
    ?? 14? ?? ??? ??? ??? ??? ??? ? ??(approve_revocation? ???? ??).
    ?? ?????? ??? ?? ?? ??? ???? ?? ????.

    [2026-07-23 ??] ?? ?? ?? status? ??? ??? ??? ??? ? ? ?? ?? ????
    ?? ??? ?? ??? ???, ?? ??(?? ?? ? ????)? ????."""
    role, subject = actor
    if (role == "caregiver" and subject.id != caregiver_id) or (role == "patient" and subject.id != patient_id):
        raise HTTPException(403, "? ??? ??? ??? ???")
    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
        .where(CaregiverPatient.status != "revoked")
    ).first()
    if not link:
        raise HTTPException(404, "??? ??? ???")
    if link.status == "revocation_pending":
        raise HTTPException(409, "?? ?? ?? ?? ?? ?????")

    is_institution = role == "caregiver" and getattr(subject, "relation_type", None) == "organization"
    if is_institution:
        if not reason or not reason.strip():
            raise HTTPException(400, "??? ?? ??? ??? ???.")
        link.status = "revocation_pending"
        link.revocation_requested_by = subject.id
        link.requested_by_role = role
        link.revocation_reason = reason.strip()
        link.revocation_requested_at = datetime.now()
        session.add(link)
        session.commit()
        return {"unlinked": False, "status": "revocation_pending"}

    link.status = "revoked"
    link.revoked_at = datetime.now()
    session.add(link)

    # [2026-07-24 ??] ?? ??(??? ?? ??? ??? ?? ??)? ???? ????
    # ?? ??? ??? ? ??? ?? ??? "???"(??? ?? ??? ?? ?)?? ???.
    if role == "caregiver":
        patient = session.get(Patient, patient_id)
        if patient:
            create_relation_notice(
                session,
                recipient_role="patient",
                recipient_id=patient.id,
                patient_id=patient.id,
                patient_name=patient.name,
                counterpart_name=subject.name,
                event="unlinked",
            )
    else:
        caregiver = session.get(Caregiver, caregiver_id)
        patient = session.get(Patient, patient_id)
        if caregiver and patient:
            create_relation_notice(
                session,
                recipient_role="caregiver",
                recipient_id=caregiver.id,
                patient_id=patient_id,
                patient_name=patient.name,
                counterpart_name=subject.name,
                event="unlinked",
            )

    session.commit()
    return {"unlinked": True, "status": "revoked"}


# ??????????????????????????????????????????
# ?? ?? (MedicationSchedule) CRUD ? patient_id ??? ??
# ??????????????????????????????????????????
class ScheduleCreate(BaseModel):
    patient_id: int
    drug_name: str
    time_slot: str  # [7/8 ??] "08:00" ?? ?? ?? ???
    dose_timing: str | None = None  # [7/8 ??] ?? / ?? ?? / ?? ?? / ?? ?? / ?? ?? / ?? ??
    caregiver_alert: bool = True  # [7/8 ??]
    memo: str | None = None
    # [2026-07-24 ??] ? ?? ??? ?? caregiver id ?? ? Schedule.tsx? "?? ??
    # ??" ?????? ?? ???. None(? ??)??? ? ???([])? "?? ????
    # ??? ??? ? ??" ??? ??? ?(??? caregiver ??)?? ????
    # (effective_alert_caregiver_ids ??) ? "????? ????? ? ???"? ?????
    # caregiver_alert=False? ?? ??? ??(Schedule.tsx? ????? ?? ????
    # caregiver_alert? ?? False? ???).
    alert_caregiver_ids: list[int] | None = None


class ScheduleUpdate(BaseModel):
    drug_name: str | None = None
    time_slot: str | None = None
    dose_timing: str | None = None
    caregiver_alert: bool | None = None
    memo: str | None = None
    active: bool | None = None
    alert_caregiver_ids: list[int] | None = None


class CheckIn(BaseModel):
    status: str  # "taken" | "skipped" (Dashboard.tsx IntakeStatus? ??)


class SchedulePublic(BaseModel):
    """[2026-07-24 ??] MedicationSchedule ??? ???? ? ? ??? ?? alert_caregiver_ids
    (??? ? ??? ??? ?? caregiver id ??)? ?? ???? ? PatientPublic?
    diagnoses/medication_status? ???? ??? ?? ??? ??."""

    id: int
    patient_id: int
    drug_name: str
    time_slot: str
    dose_timing: str | None = None
    caregiver_alert: bool
    memo: str | None = None
    active: bool
    created_at: datetime
    patient_medication_id: int | None = None
    meal_relation: str | None = None
    instructions: str | None = None
    timezone: str | None = None
    days_of_week: str | None = None
    record_id: int | None = None
    alert_caregiver_ids: list[int] = []


def _to_schedule_public(schedule: MedicationSchedule, session: Session) -> SchedulePublic:
    return SchedulePublic(
        **schedule.model_dump(),
        alert_caregiver_ids=effective_alert_caregiver_ids(schedule, session),
    )


def _replace_schedule_caregiver_alerts(
    schedule_id: int, patient_id: int, caregiver_ids: list[int], session: Session
) -> None:
    """[2026-07-24 ??] ? ??? alert_caregiver_ids? ??? ???? ? ??? ??
    ??? ??(?? ??? ??? ? ??) caregiver_id? ?? ?? ?? ? ???,
    ??? ?? ??? caregiver ????? ?????."""
    linked = set(linked_caregiver_ids(patient_id, session))
    valid_ids = [cid for cid in dict.fromkeys(caregiver_ids) if cid in linked]
    existing = session.exec(
        select(ScheduleCaregiverAlert).where(ScheduleCaregiverAlert.schedule_id == schedule_id)
    ).all()
    for row in existing:
        session.delete(row)
    for caregiver_id in valid_ids:
        session.add(ScheduleCaregiverAlert(schedule_id=schedule_id, caregiver_id=caregiver_id))


@router.post("/schedules", response_model=SchedulePublic)
def create_schedule(
    payload: ScheduleCreate, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    require_actor_patient_access(payload.patient_id, actor, session)
    fields = payload.model_dump(exclude={"alert_caregiver_ids"})
    schedule = MedicationSchedule(**fields)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    if payload.alert_caregiver_ids is not None:
        _replace_schedule_caregiver_alerts(schedule.id, payload.patient_id, payload.alert_caregiver_ids, session)
        session.commit()
        # [??] commit()? ????? ??? ?? ?? ??? ????? ? ? refresh ??
        # model_dump()? ???? SQLAlchemy? lazy-load? ? ?? ? ?? ???(??? ??
        # ??, ?? update_schedule? ??? ??? alert_caregiver_ids ?? ? refresh??).
        session.refresh(schedule)
    return _to_schedule_public(schedule, session)


@router.get("/schedules", response_model=list[SchedulePublic])
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
    schedules = session.exec(query).all()
    return [_to_schedule_public(s, session) for s in schedules]


@router.patch("/schedules/{schedule_id}", response_model=SchedulePublic)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "?? ??? ?? ? ???")
    require_actor_patient_access(schedule.patient_id, actor, session)
    updates = payload.model_dump(exclude_unset=True, exclude={"alert_caregiver_ids"})
    before = {key: getattr(schedule, key, None) for key in updates}
    for key, value in updates.items():
        setattr(schedule, key, value)
    session.add(schedule)
    record_audit_log(session, "medication_schedules", schedule_id, actor, before, updates)
    session.commit()
    if payload.alert_caregiver_ids is not None:
        _replace_schedule_caregiver_alerts(schedule.id, schedule.patient_id, payload.alert_caregiver_ids, session)
        session.commit()
    session.refresh(schedule)
    return _to_schedule_public(schedule, session)


@router.get("/patients/{patient_id}/known-drugs")
def list_known_drugs(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """
    [7/8 ??] '? ?? ??' ??? "?? ??" ????? ? ? ??? ?????
    ??? OCR? ??? ? ?? + ?? ??? ?? ??? ? ??? ?? ?? ???? ??.
    ?? ?? ??? ??? ? ?? ???? ??? ???? ? ??? ?????.
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
        raise HTTPException(404, "?? ??? ?? ? ???")
    require_actor_patient_access(schedule.patient_id, actor, session)
    records = session.exec(
        select(MedicationRecord).where(MedicationRecord.schedule_id == schedule_id)
    ).all()
    for record in records:
        session.delete(record)
    # [2026-07-22 ??] notification_logs.schedule_id? ? ???? ???? ???(???
    # ? ???? ??/??? ? ???) FK ?? ???? 500? ?? ? ??? ?? ???.
    # MedicationSchedule<->NotificationLog ??? ORM relationship? ?? SQLAlchemy?
    # ?? ??? FK ???? ?? ????? ??? ? flush? ?? ???? ????.
    logs = session.exec(
        select(NotificationLog).where(NotificationLog.schedule_id == schedule_id)
    ).all()
    for log in logs:
        session.delete(log)
    # [2026-07-23 ??, ?? ?? ??] medication_logs ? medication_records ??(849bd15b19a5)
    # ??? ?? ??? ??? ??? ??? ???? schedule_id? ??? FK?, ??
    # ???? ?? ??? ??? ??? ??? FK ??? ??.
    legacy_logs = session.exec(
        select(MedicationLog).where(MedicationLog.schedule_id == schedule_id)
    ).all()
    for legacy_log in legacy_logs:
        session.delete(legacy_log)
    # [2026-07-24 ??, ?? ?? ??] schedule_caregiver_alerts.schedule_id? ?? FK
    # ??? ?? ?? ??? ?? ??? ?? ? ? ???(?? ?? ??? ??)??
    # caregiver_alert=True? ?? ???? ? ?? ?? ??, ???? ??? ???.
    alert_rows = session.exec(
        select(ScheduleCaregiverAlert).where(ScheduleCaregiverAlert.schedule_id == schedule_id)
    ).all()
    for alert_row in alert_rows:
        session.delete(alert_row)
    session.flush()
    session.delete(schedule)
    session.commit()
    return {"deleted": schedule_id}


# ?? ?? ?? ?? (Dashboard.tsx? updateStatus? ??) ??
@router.post("/schedules/{schedule_id}/check")
def check_intake(
    schedule_id: int,
    payload: CheckIn,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "?? ??? ?? ? ???")
    require_actor_patient_access(schedule.patient_id, actor, session)

    today_str = date.today().isoformat()
    existing = session.exec(
        select(MedicationRecord)
        .where(MedicationRecord.schedule_id == schedule_id)
        .where(MedicationRecord.status.in_(["taken", "skipped"]))
        .where(func.date(MedicationRecord.taken_at) == today_str)
    ).first()

    # [2026-07-20 ????] "?? ?????"? ?? ??? ??? ??? actor???
    # ???? ? payload? ??? confirmed_by_caregiver_id? ??? ? ??? ???
    # ???? ??(?? ? PII)? ? ??? ?? ??? ???? ??? ? ???.
    role, subject = actor
    confirmed_by_caregiver_id = subject.id if role == "caregiver" else None
    confirmed_by_type = "caregiver" if confirmed_by_caregiver_id else "patient"
    verification_method = "caregiver" if confirmed_by_caregiver_id else "self_report"
    now = datetime.now()

    if existing:
        existing.status = payload.status
        existing.taken_at = now
        existing.updated_at = now
        existing.verification_method = verification_method
        existing.confirmed_by_type = confirmed_by_type
        existing.confirmed_by_caregiver_id = confirmed_by_caregiver_id
        session.add(existing)
    else:
        session.add(
            MedicationRecord(
                schedule_id=schedule_id,
                status=payload.status,
                taken_at=now,
                verification_method=verification_method,
                confirmed_by_type=confirmed_by_type,
                confirmed_by_caregiver_id=confirmed_by_caregiver_id,
            )
        )

    session.commit()
    return {"schedule_id": schedule_id, "status": payload.status}


# ?? [7/6 ??] ??? ?? ?? ? pending?? ???? (Dashboard.tsx "????" ???) ??
@router.delete("/schedules/{schedule_id}/check")
def clear_intake(
    schedule_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    schedule = session.get(MedicationSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "?? ??? ?? ? ???")
    require_actor_patient_access(schedule.patient_id, actor, session)

    today_str = date.today().isoformat()
    existing = session.exec(
        select(MedicationRecord)
        .where(MedicationRecord.schedule_id == schedule_id)
        .where(MedicationRecord.status.in_(["taken", "skipped"]))
        .where(func.date(MedicationRecord.taken_at) == today_str)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()

    return {"schedule_id": schedule_id, "status": "pending"}


# ?? [7/8 ??] ????????(????) ??????? ??? ?? ?? ??
@router.get("/logs")
def list_logs(
    patient_id: int,
    days: int = 30,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    ?? N??? ?? ?? ??? ????? ?? ?????.
    ???(????????)? ? ?? ??? ??? ? ????? ?????? ?? ?? ?? ?????.
    (?? ?? ??? ?? MedicationRecord? ??? ???? ?? ? schedule_v6 ??? ??? ??)

    [2026-07-20 REQ-037 Phase2] ??? ??? MedicationRecord? ?????. status? 5?
    (scheduled/taken/missed/skipped/duplicate_suspected)??, ???? ??? ???
    taken/skipped? ????? ????? ??? ????(??? MedicationLogEntry.status?
    taken/skipped/missed? ?? ? missed? ?? NotificationLog ???? ???).
    """
    require_actor_patient_access(patient_id, actor, session)

    schedules = session.exec(
        select(MedicationSchedule).where(MedicationSchedule.patient_id == patient_id)
    ).all()
    schedule_map = {s.id: s for s in schedules}
    if not schedule_map:
        return []

    since = datetime.now() - timedelta(days=days)
    records = session.exec(
        select(MedicationRecord)
        .where(MedicationRecord.schedule_id.in_(list(schedule_map.keys())))
        .where(MedicationRecord.status.in_(["taken", "skipped"]))
        .where(MedicationRecord.taken_at >= since)
        .order_by(MedicationRecord.taken_at.desc())
    ).all()

    caregiver_ids = {r.confirmed_by_caregiver_id for r in records if r.confirmed_by_caregiver_id}
    caregiver_names = {
        c.id: c.name for c in session.exec(select(Caregiver).where(Caregiver.id.in_(caregiver_ids)))
    } if caregiver_ids else {}

    entries = [
        {
            "id": str(r.id),
            "schedule_id": r.schedule_id,
            "drug_name": schedule_map[r.schedule_id].drug_name,
            "time_slot": schedule_map[r.schedule_id].time_slot,
            "status": r.status,
            "checked_at": r.taken_at.isoformat(),
            "confirmed_by_type": r.confirmed_by_type,
            "confirmed_by_name": (
                caregiver_names.get(r.confirmed_by_caregiver_id, "???")
                if r.confirmed_by_type == "caregiver"
                else "??"
            ),
        }
        for r in records
    ]

    # [2026-07-19 ??, REQ-037 Phase1] core/scheduler.py? ??? ?? ? ????
    # MedicationRecord? ??? NotificationLog(kind="missed")? ????(??? ????
    # ? ???? read-side ?? ? models.py NotificationLog ?? ??). ?? ?? ???
    # ?? ?? (schedule_id, ??)? ? ??? ????? missed? ?? ?? ???.
    real_checked_dates = {(r.schedule_id, r.taken_at.date().isoformat()) for r in records}
    missed_notifs = session.exec(
        select(NotificationLog)
        .where(NotificationLog.kind == "missed")
        .where(NotificationLog.schedule_id.in_(list(schedule_map.keys())))
        .where(NotificationLog.fired_at >= since)
    ).all()
    entries.extend(
        {
            "id": f"missed:{notif.id}",
            "schedule_id": notif.schedule_id,
            "drug_name": schedule_map[notif.schedule_id].drug_name,
            "time_slot": notif.time_slot,
            "status": "missed",
            "checked_at": notif.fired_at.isoformat(),
            "confirmed_by_type": "system",
            "confirmed_by_name": "?? ??",
        }
        for notif in missed_notifs
        if (notif.schedule_id, notif.due_date) not in real_checked_dates
    )
    entries.sort(key=lambda e: e["checked_at"], reverse=True)
    return entries


class NotificationLogEntry(BaseModel):
    """[2026-07-23 ??] ??? ? ?? ??/?? ??? ?? NotificationLog? ???
    ???, ?? ??? ?? ? ??? ???(??? ??? ??). ?? ?? ???????
    ?? ??? ??? ? ?? ??? ????."""
    id: int
    schedule_id: int
    drug_name: str
    time_slot: str
    due_date: str
    kind: Literal["reminder", "missed"]
    status: Literal["pending", "sent", "suppressed", "failed"]
    fired_at: datetime
    # [2026-07-30 ??] NavBar ? ???? ? ?? ??? "? ?? ???? ??? ?
    # ??" ?? ??? ? ???? ??? ?? ?? ????. ??? ??? ??
    # acknowledged_at ??? ???? ??? ? ???? ???.
    acknowledged_at: datetime | None = None


class NotificationBulkDeleteRequest(BaseModel):
    notification_ids: list[int]


@router.get("/patients/{patient_id}/notifications", response_model=list[NotificationLogEntry])
def list_notifications(
    patient_id: int,
    days: int = 30,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    since = datetime.now() - timedelta(days=days)
    logs = session.exec(
        select(NotificationLog)
        .where(NotificationLog.patient_id == patient_id)
        .where(NotificationLog.deleted_at == None)  # noqa: E711
        .where(NotificationLog.fired_at >= since)
        .order_by(NotificationLog.fired_at.desc())
    ).all()
    if not logs:
        return []

    schedule_ids = {log.schedule_id for log in logs}
    schedules = {
        s.id: s for s in session.exec(select(MedicationSchedule).where(MedicationSchedule.id.in_(schedule_ids)))
    }
    return [
        NotificationLogEntry(
            id=log.id,
            schedule_id=log.schedule_id,
            drug_name=schedules[log.schedule_id].drug_name if log.schedule_id in schedules else "??? ??",
            time_slot=log.time_slot,
            due_date=log.due_date,
            kind=log.kind,
            status=log.status,
            fired_at=log.fired_at,
            acknowledged_at=log.acknowledged_at,
        )
        for log in logs
    ]


@router.post("/patients/{patient_id}/notifications/acknowledge")
def acknowledge_notifications(
    patient_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[2026-07-30 ??] ???(Notifications.tsx)? ?? ?? ??? ??? ?? ???
    ?? ? ?? ??? ??? "? ???? ?????"? ????(?? ??? ???
    ??? ??? ?? ?? ??), ? ??? ?? ? ?? ? ??? ? ?? ????."""
    require_actor_patient_access(patient_id, actor, session)
    unacknowledged = session.exec(
        select(NotificationLog)
        .where(NotificationLog.patient_id == patient_id)
        .where(NotificationLog.deleted_at == None)  # noqa: E711
        .where(NotificationLog.acknowledged_at == None)  # noqa: E711
    ).all()
    now = datetime.now()
    for log in unacknowledged:
        log.acknowledged_at = now
        session.add(log)
    session.commit()
    return {"acknowledged": len(unacknowledged)}


@router.delete("/patients/{patient_id}/notifications/{notification_id}")
def delete_notification(
    patient_id: int,
    notification_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """????? ?? ?? ? ?? ?? ????."""
    require_actor_patient_access(patient_id, actor, session)
    log = session.get(NotificationLog, notification_id)
    if not log or log.patient_id != patient_id:
        raise HTTPException(404, "??? ?? ? ???")
    if log.deleted_at is None:
        log.deleted_at = datetime.now()
        session.add(log)
    session.commit()
    return {"deleted": notification_id}


@router.post("/patients/{patient_id}/notifications/delete")
def delete_notifications(
    patient_id: int,
    payload: NotificationBulkDeleteRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """???? ??? ?? ??? ?? ??? ?? ??? ? ?? ????."""
    require_actor_patient_access(patient_id, actor, session)
    notification_ids = list(dict.fromkeys(payload.notification_ids))
    if not notification_ids:
        return {"deleted": 0}
    if len(notification_ids) > 500:
        raise HTTPException(422, "? ?? ?? 500?? ??? ??? ? ???.")

    logs = session.exec(
        select(NotificationLog)
        .where(NotificationLog.patient_id == patient_id)
        .where(NotificationLog.id.in_(notification_ids))
        .where(NotificationLog.deleted_at == None)  # noqa: E711
    ).all()
    now = datetime.now()
    for log in logs:
        log.deleted_at = now
        session.add(log)
    session.commit()
    return {"deleted": len(logs)}


@router.delete("/patients/{patient_id}/notifications")
def clear_acknowledged_notifications(
    patient_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """??? ?? ??? ???? ????. ?? ???? ?? ??? ????."""
    require_actor_patient_access(patient_id, actor, session)
    logs = session.exec(
        select(NotificationLog)
        .where(NotificationLog.patient_id == patient_id)
        .where(NotificationLog.deleted_at == None)  # noqa: E711
        .where(NotificationLog.acknowledged_at != None)  # noqa: E711
    ).all()
    now = datetime.now()
    for log in logs:
        log.deleted_at = now
        session.add(log)
    session.commit()
    return {"deleted": len(logs)}


# ?? Dashboard.tsx? ??? ? ? ?? ??? ?? ?? [7/6: patient_id ??? ??] ??
@router.get("/today")
def get_today(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """
    ?? ?? (Dashboard.tsx? Medication[] ???):
    [{ "id": "1", "name": "???? 5mg", "time": "??", "note": "", "status": "pending" }]
    ?? ?? ??? ??? status? ???? "pending"

    [perf, N+1 ??] schedule?? MedicationRecord/NotificationLog? ?? ???? ?
    list_notifications(? GET /patients/{id}/notifications)? ??? "ID ???
    bulk-select" ???? ????. schedule 10? ?? ?? ?: ?? 1(schedules) +
    ?? 2?10(record+missed) = ?? 21? ? ?? ? 1(schedules) + 1(records) +
    1(missed) = 3?? ??(??? ?? ???? ?? 3?).
    """
    require_actor_patient_access(patient_id, actor, session)

    today_str = date.today().isoformat()
    schedules = session.exec(
        select(MedicationSchedule)
        .where(MedicationSchedule.patient_id == patient_id)
        .where(MedicationSchedule.active == True)  # noqa: E712
        .order_by(MedicationSchedule.time_slot)  # [2026-07-21 ??] ???? ????? ????? ???
    ).all()
    if not schedules:
        return []

    schedule_ids = [s.id for s in schedules]

    records = session.exec(
        select(MedicationRecord)
        .where(MedicationRecord.schedule_id.in_(schedule_ids))
        .where(MedicationRecord.status.in_(["taken", "skipped"]))
        .where(func.date(MedicationRecord.taken_at) == today_str)
    ).all()
    # setdefault? ???? ?? ?? ?? ?? ? ??? ???? `.first()`? ??? ??
    # (recheck? ?? ?? ????? ???? ? ??? ?? ?? ????? ?? 1?).
    record_by_schedule: dict[int, MedicationRecord] = {}
    for r in records:
        record_by_schedule.setdefault(r.schedule_id, r)

    # [2026-07-19 ??, REQ-037 Phase1] ??? ??? ???, ????? ?? "??"??
    # ?????? NotificationLog?? ????(MedicationRecord ???? ? ????
    # read-side ??).
    missed_logs = session.exec(
        select(NotificationLog)
        .where(NotificationLog.schedule_id.in_(schedule_ids))
        .where(NotificationLog.due_date == today_str)
        .where(NotificationLog.kind == "missed")
    ).all()
    missed_schedule_ids = {log.schedule_id for log in missed_logs}

    result = []
    for s in schedules:
        record = record_by_schedule.get(s.id)
        if record:
            status = record.status
        else:
            status = "missed" if s.id in missed_schedule_ids else "pending"
        result.append(
            {
                "id": str(s.id),
                "name": s.drug_name,
                "time": s.time_slot,
                "note": s.memo or "",
                "status": status,
            }
        )
    return result
