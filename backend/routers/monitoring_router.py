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
    # [2026-07-22 추가] 환자 관리 테이블(Figma 목업)의 "성별" 컬럼용 — 가입 화면 select가
    # "male"/"female" 둘 중 하나만 보낸다(모르면 그냥 비워둠 — 지어내지 않음).
    gender: Literal["male", "female"] | None = None
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
    gender: Literal["male", "female"] | None = None
    # [2026-07-22 추가] "내 정보"(MyInfo.tsx)에서 회원가입 때 받은 알림 수신 설정도 같이 수정
    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    email_opt_in: bool | None = None


class PatientPublic(BaseModel):
    """hashed_password는 API 응답에 노출하지 않기 위한 응답 전용 모델 (CaregiverPublic과 동일한 원칙)"""
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
    # [2026-07-22 추가] 환자 관리 테이블(PatientManagement.tsx)의 "진단명"/"상태" 컬럼용 —
    # 다른 엔드포인트에서는 계산 안 하고 기본값(None/"none")으로 둔다. 계산 비용이 있는
    # 값이라 실제로 표로 보여줄 GET /caregivers/{id}/patients에서만 채운다.
    diagnoses: str | None = None
    medication_status: Literal["active", "paused", "none"] = "none"
    # [2026-07-23 추가] 환자 관리 테이블 맨 오른쪽 "오늘 상태" 동그라미용 — 다른 계산
    # 필드와 동일하게 GET /caregivers/{id}/patients에서만 채운다.
    today_status: Literal["ok", "missed"] = "ok"


class MealTimesUpdate(BaseModel):
    breakfast_time: str | None = None
    breakfast_regular: bool | None = None
    lunch_time: str | None = None
    lunch_regular: bool | None = None
    dinner_time: str | None = None
    dinner_regular: bool | None = None


def _register_patient(payload: PatientCreate, session: Session) -> Patient:
    """실제 Patient 계정 생성 — create_patient 엔드포인트와 보호자→환자 초대 수락
    (care_router.accept_invitation) 양쪽에서 재사용하는 공용 로직."""
    # [2026-07-14] 이메일 앞뒤 공백/대소문자가 섞이면 같은 사람이 다른 계정으로 취급돼
    # 로그인이 안 되는 문제가 있었다 — 저장 전에 항상 정규화한다.
    email = normalize_email(payload.email) if payload.email else None
    # [2026-07-14] Patient.email엔 이제 유니크 제약이 있지만, DB의 raw IntegrityError
    # 대신 사용자에게 명확한 409를 주기 위해 사전 검사도 함께 한다.
    if email and session.exec(select(Patient).where(Patient.email == email)).first():
        raise HTTPException(409, "이미 사용중인 이메일입니다.")

    # [2026-07-22 추가] phone_hash엔 email과 달리 유니크 제약이 없어서, 중복된 전화번호로
    # 가입해도 여기선 막히지 않고 조용히 저장됐다 — auth_router._find_by_identifier가
    # phone_hash로 조회할 때 `.first()`를 쓰기 때문에, 나중에 로그인 시도 시(특히 이
    # 가입 직후 자동 로그인) 먼저 만들어진 다른 계정이 걸려서 비밀번호가 안 맞다고
    # 나오는 버그로 이어졌다(SignUp.tsx "가입 처리에 실패했어요"). email과 동일하게
    # 가입 시점에 막는다.
    if payload.phone and session.exec(select(Patient).where(Patient.phone_hash == hash_phone(payload.phone))).first():
        raise HTTPException(409, "이미 사용중인 전화번호입니다.")

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


@router.post("/patients", response_model=PatientPublic)
def create_patient(payload: PatientCreate, session: Session = Depends(get_session)):
    return _register_patient(payload, session)


@router.get("/patients/check-duplicate")
def check_patient_duplicate(
    email: str | None = None,
    phone: str | None = None,
    session: Session = Depends(get_session),
):
    """[2026-07-23 추가] 회원가입(SignUp.tsx)에서 이메일/전화번호를 입력하고 다른 필드로
    넘어갈 때(onBlur) 바로 중복 여부를 알려주기 위한 조회용 엔드포인트 — 계정을 만들지
    않고 _register_patient와 동일한 중복 판정 규칙만 재사용한다."""
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
    """[7/13] MyPage.tsx가 "본인"을 찾는 데만 쓴다 — 전체 목록이 아니라 토큰의 본인
    범위로 좁힌다 (환자 본인 로그인이면 자기 자신, 보호자면 케어하는 환자 전체)."""
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
    """[2026-07-22 수정] 보호자뿐 아니라 환자 본인도 "내 정보"(MyInfo.tsx)에서 자기
    정보를 고칠 수 있어야 해서 actor 기반 인가로 바꿨다(보호자면 연결된 환자인지,
    환자 본인이면 자기 자신인지 확인 — require_actor_patient_access)."""
    require_actor_patient_access(patient_id, actor, session)
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"]:
        email = normalize_email(updates["email"])
        existing = session.exec(select(Patient).where(Patient.email == email)).first()
        if existing and existing.id != patient_id:
            raise HTTPException(409, "이미 사용중인 이메일입니다.")
        updates["email"] = email
    elif "email" in updates:
        # [2026-07-23 수정, 팀원 리뷰 반영] 빈 문자열을 그대로 저장하면 email이
        # unique=True라 다른 계정도 빈 문자열로 지운 경우 unique 제약 충돌이 난다 —
        # "삭제"는 None으로 정규화해야 안전하다(여러 계정이 동시에 None이어도 무관).
        updates["email"] = None
    if "phone" in updates and updates["phone"]:
        existing = session.exec(
            select(Patient).where(Patient.phone_hash == hash_phone(updates["phone"]))
        ).first()
        if existing and existing.id != patient_id:
            raise HTTPException(409, "이미 사용중인 전화번호입니다.")

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
    """[2026-07-16 추가] 회원가입 직후 자가진단 설문(MealTimeCheck.tsx) 저장용.
    환자 본인 로그인 직후(가입 흐름) 호출되므로 caregiver 전용이 아니라 actor 기반 인가를 쓴다
    (update_patient처럼 caregiver 전용이면 환자 본인 토큰으로는 호출할 수 없다)."""
    require_actor_patient_access(patient_id, actor, session)
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
    # [2026-07-16 추가] 직접 가입 화면(frontend/src/pages/SignUp.tsx)이 보내는 값은
    # guardian(개인)과 organization(단체·기관) 둘뿐이다. 초대 흐름은
    # care_router.InvitationCreate에서 Connect.tsx의 4개 관계값
    # (guardian/caregiver/life_support_worker/social_worker)을 별도로 검증한다.
    # DB 컬럼은 VARCHAR라 검증 없이는 오타/임의 값이 그대로 저장되므로 입력 스키마에서 막는다.
    relation_type: Literal["guardian", "organization"] = "guardian"
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
    # [2026-07-23 수정] phone_hash와 동일한 이유로 email도 테이블 전체가 아니라
    # relation_type끼리만 중복을 막는다(아래 phone_hash 주석 참고).
    email = normalize_email(payload.email) if payload.email else None
    if (
        email
        and session.exec(
            select(Caregiver)
            .where(Caregiver.email == email)
            .where(Caregiver.relation_type == payload.relation_type)
        ).first()
    ):
        raise HTTPException(409, "이미 사용중인 이메일입니다.")

    # [2026-07-22 추가] Patient._register_patient와 동일한 이유 — phone_hash 유니크
    # 제약이 없어 중복 전화번호 가입이 조용히 허용됐고, 로그인 시 `.first()`가 먼저
    # 만들어진 다른 보호자 계정을 집어서 회원가입 직후 자동 로그인이 실패했다.
    # [2026-07-22 수정] 단, 같은 사람이 보호자(가족)이면서 동시에 기관(요양보호사 등)
    # 소속일 수 있고, 환자 본인 계정도 별도로 가질 수 있다(부모님 보호자이자 본인은
    # 환자, 게다가 요양보호사로 근무 — 세 역할 모두 흔한 조합) — 그래서 전화번호는
    # 테이블 전체가 아니라 relation_type(같은 역할)끼리만 중복을 막는다. Patient는
    # 역할이 하나뿐이라 테이블 전체 유니크로 충분하다.
    if (
        payload.phone
        and session.exec(
            select(Caregiver)
            .where(Caregiver.phone_hash == hash_phone(payload.phone))
            .where(Caregiver.relation_type == payload.relation_type)
        ).first()
    ):
        raise HTTPException(409, "이미 사용중인 전화번호입니다.")

    # [7/9] name/phone은 Caregiver의 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 —
    # 나머지 필드로 먼저 만들고 .name/.phone에 대입해서 암호화·해시 처리한다.
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
    """[2026-07-23 추가] check_patient_duplicate와 동일한 목적 — create_caregiver의 중복
    판정 규칙(이메일·전화번호 모두 relation_type끼리만 비교)을 그대로 재사용한다."""
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
    """[7/10] 전체 보호자 목록이 아니라 로그인한 본인만 반환 (MyPage.tsx가 본인 조회용으로만 씀, issue #21)."""
    return [caregiver]


class CaregiverUpdate(BaseModel):
    """[2026-07-22 추가] "내 정보"(MyInfo.tsx)에서 회원가입 때 받은 정보를 수정 —
    relation_type/password는 여기서 안 바꾼다(전자는 계정 성격 자체를 바꾸는 별개 작업,
    후자는 이미 있는 비밀번호 재설정 흐름을 쓴다)."""
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
        raise HTTPException(403, "본인 정보만 수정할 수 있어요.")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"]:
        email = normalize_email(updates["email"])
        existing = session.exec(
            select(Caregiver)
            .where(Caregiver.email == email)
            .where(Caregiver.relation_type == caregiver.relation_type)
        ).first()
        if existing and existing.id != caregiver_id:
            raise HTTPException(409, "이미 사용중인 이메일입니다.")
        updates["email"] = email
    elif "email" in updates:
        # [2026-07-23 수정, 팀원 리뷰 반영] update_patient와 동일한 이유 — email이
        # unique=True라 빈 문자열을 그대로 저장하면 여러 계정이 지웠을 때 충돌한다.
        updates["email"] = None
    if "phone" in updates and updates["phone"]:
        existing = session.exec(
            select(Caregiver)
            .where(Caregiver.phone_hash == hash_phone(updates["phone"]))
            .where(Caregiver.relation_type == caregiver.relation_type)
        ).first()
        if existing and existing.id != caregiver_id:
            raise HTTPException(409, "이미 사용중인 전화번호입니다.")

    for key, value in updates.items():
        setattr(caregiver, key, value)
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


def _patient_diagnoses(session: Session, patient_id: int) -> str | None:
    """환자 관리 테이블 "진단명" 컬럼용 — diagnosis는 MedicalRecord(처방전 1건)가 아니라
    OcrResult(약 1개당 1행)에 있다 — 등록내역(soft-delete 제외)에 딸린 결과들의 진단명을
    중복 없이 등장 순서대로 모아 "·"로 이어붙인다. 실제로 값이 있는 것만."""
    rows = session.exec(
        select(OcrResult.diagnosis)
        .join(MedicalRecord, OcrResult.record_id == MedicalRecord.id)
        .where(MedicalRecord.patient_id == patient_id)
        .where(MedicalRecord.deleted_at.is_(None))
        .where(OcrResult.diagnosis != "")
    ).all()
    distinct = list(dict.fromkeys(rows))
    return "·".join(distinct) if distinct else None


def _patient_medication_status(session: Session, patient_id: int) -> Literal["active", "paused", "none"]:
    """환자 관리 테이블 "상태" 컬럼용 — 활성 복약 일정이 하나라도 있으면 복약중, 일정
    자체는 있는데 전부 비활성이면 중단, 아예 없으면 none(표에서 "-"로 표시)."""
    schedules = session.exec(
        select(MedicationSchedule.active).where(MedicationSchedule.patient_id == patient_id)
    ).all()
    if not schedules:
        return "none"
    return "active" if any(schedules) else "paused"


def _patient_today_status(session: Session, patient_id: int) -> Literal["ok", "missed"]:
    """환자 관리 테이블 "오늘 상태" 동그라미용 — 여러 환자를 관리할 때 오늘 누가 약을
    놓쳤는지 한눈에 보기 위함(list_logs가 캘린더/최근기록에 쓰는 것과 동일한 NotificationLog
    kind="missed" 병합 방식을 재사용). 오늘 놓친 일정이 하나라도 있으면 missed(빨강),
    없으면 ok(초록) — 활성 일정이 아예 없는 환자도 ok로 둔다(놓칠 일정 자체가 없으므로)."""
    active_schedule_ids = session.exec(
        select(MedicationSchedule.id)
        .where(MedicationSchedule.patient_id == patient_id)
        .where(MedicationSchedule.active == True)  # noqa: E712
    ).all()
    if not active_schedule_ids:
        return "ok"
    today_str = date.today().isoformat()
    missed = session.exec(
        select(NotificationLog)
        .where(NotificationLog.kind == "missed")
        .where(NotificationLog.due_date == today_str)
        .where(NotificationLog.schedule_id.in_(active_schedule_ids))
    ).first()
    return "missed" if missed else "ok"


@router.get("/caregivers/{caregiver_id}/patients", response_model=list[PatientPublic])
def list_patients_of_caregiver(
    caregiver_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """핵심 기능: 이 보호자가 케어하는 환자 전체 목록 (여러 명 가능)

    [2026-07-22 수정] 환자 관리 테이블(Figma 목업)이 진단명·복약상태도 보여줘야 해서,
    ORM 객체를 그대로 반환하는 대신 PatientPublic으로 변환한 뒤 계산한 값을 채워 넣는다."""
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "다른 보호자의 환자 목록은 볼 수 없어요")

    links = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.status != "revoked")
    ).all()
    patient_ids = [link.patient_id for link in links]
    if not patient_ids:
        return []
    patients = session.exec(select(Patient).where(Patient.id.in_(patient_ids))).all()
    result = []
    for patient in patients:
        public = PatientPublic.model_validate(patient, from_attributes=True)
        result.append(
            public.model_copy(
                update={
                    "diagnoses": _patient_diagnoses(session, patient.id),
                    "medication_status": _patient_medication_status(session, patient.id),
                    "today_status": _patient_today_status(session, patient.id),
                }
            )
        )
    return result


@router.get("/patients/{patient_id}/caregivers", response_model=list[CaregiverPublic])
def list_caregivers_of_patient(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """[7/8 추가] 반대 방향 조회 — 이 환자를 케어하는 보호자 전체 목록 (Connect.tsx '연결된 사람' 표에 사용)."""
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
        if existing.status == "revoked":
            # [2026-07-23 추가] 과거에 해제된 연결이면 새 행을 또 만들지 않고 재활성화한다.
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
        raise HTTPException(403, "이미 다른 보호자가 연결된 환자예요. 추가 연결은 초대 링크를 통해서만 가능해요.")

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
    """Connect.tsx/PatientManagement.tsx — 보호자 본인이거나 환자 본인이어야 그 연결을 해제할 수 있다.

    [2026-07-23 수정] 기관(organization) 계정이 연결을 끊을 때는 즉시 끊지 않는다 — 환자·보호자가
    스스로 관리하기 어려운 상황에서 기관이 사유 없이 일방적으로 손을 떼는 걸 막기 위해, 상대(환자
    또는 다른 보호자)가 승인해야 실제로 끊긴다(POST /trust/relations/{trust_id}/revocation-approval).
    대신 정당한 사유로 끊으려는 기관이 상대의 무응답에 무기한 묶이지 않도록, 사유 입력을 필수로
    하고 14일 안에 응답이 없으면 요청자 스스로 확정할 수 있다(approve_revocation의 타임아웃 처리).
    개인 보호자·환자 본인이 끊을 때는 기존과 동일하게 즉시 처리한다.

    [2026-07-23 수정] 하드 삭제 대신 status를 남기는 소프트 삭제로 바꿨다 — 이 앱의 다른 모델들과
    같은 소프트 삭제 관례를 따르고, 감사 이력(누가 언제 왜 끊었는지)을 보존한다."""
    role, subject = actor
    if (role == "caregiver" and subject.id != caregiver_id) or (role == "patient" and subject.id != patient_id):
        raise HTTPException(403, "이 연결을 해제할 권한이 없어요")
    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
        .where(CaregiverPatient.status != "revoked")
    ).first()
    if not link:
        raise HTTPException(404, "연결된 내역이 없어요")
    if link.status == "revocation_pending":
        raise HTTPException(409, "이미 해제 승인 대기 중인 연결이에요")

    is_institution = role == "caregiver" and getattr(subject, "relation_type", None) == "organization"
    if is_institution:
        if not reason or not reason.strip():
            raise HTTPException(400, "연결을 끊는 사유를 입력해 주세요.")
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
    session.commit()
    return {"unlinked": True, "status": "revoked"}


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
    updates = payload.model_dump(exclude_unset=True)
    before = {key: getattr(schedule, key, None) for key in updates}
    for key, value in updates.items():
        setattr(schedule, key, value)
    session.add(schedule)
    record_audit_log(session, "medication_schedules", schedule_id, actor, before, updates)
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
    records = session.exec(
        select(MedicationRecord).where(MedicationRecord.schedule_id == schedule_id)
    ).all()
    for record in records:
        session.delete(record)
    # [2026-07-22 수정] notification_logs.schedule_id가 이 스케줄을 참조하고 있으면(알림이
    # 한 번이라도 발송/판정된 적 있으면) FK 제약 위반으로 500이 났다 — 기록도 함께 지운다.
    # MedicationSchedule<->NotificationLog 사이엔 ORM relationship이 없어 SQLAlchemy가
    # 삭제 순서를 FK 기준으로 자동 정렬해주지 않는다 — flush로 먼저 실행되게 강제한다.
    logs = session.exec(
        select(NotificationLog).where(NotificationLog.schedule_id == schedule_id)
    ).all()
    for log in logs:
        session.delete(log)
    # [2026-07-23 수정, 팀원 리뷰 반영] medication_logs → medication_records 이관(849bd15b19a5)
    # 이후로 새로 쓰이진 않지만 테이블 자체는 남아있고 schedule_id가 여전히 FK라, 이관
    # 이전부터 있던 오래된 일정을 지우면 여기서 FK 위반이 났다.
    legacy_logs = session.exec(
        select(MedicationLog).where(MedicationLog.schedule_id == schedule_id)
    ).all()
    for legacy_log in legacy_logs:
        session.delete(legacy_log)
    session.flush()
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
        select(MedicationRecord)
        .where(MedicationRecord.schedule_id == schedule_id)
        .where(MedicationRecord.status.in_(["taken", "skipped"]))
        .where(func.date(MedicationRecord.taken_at) == today_str)
    ).first()

    # [2026-07-20 보안수정] "누가 체크했는지"는 요청 바디가 아니라 인증된 actor에서만
    # 가져온다 — payload로 임의의 confirmed_by_caregiver_id를 받으면 이 환자와 무관한
    # 보호자의 신원(이름 등 PII)이 이 환자의 복약 로그에 확인자로 표시될 수 있었다.
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
        select(MedicationRecord)
        .where(MedicationRecord.schedule_id == schedule_id)
        .where(MedicationRecord.status.in_(["taken", "skipped"]))
        .where(func.date(MedicationRecord.taken_at) == today_str)
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
    (별도 집계 테이블 없이 MedicationRecord를 그대로 조회하는 방식 — schedule_v6 단순화 원칙과 동일)

    [2026-07-20 REQ-037 Phase2] 체크인 기록을 MedicationRecord로 일원화했다. status가 5종
    (scheduled/taken/missed/skipped/duplicate_suspected)이라, 사용자가 실제로 체크한
    taken/skipped만 명시적으로 필터링해서 응답에 노출한다(프론트 MedicationLogEntry.status는
    taken/skipped/missed만 안다 — missed는 아래 NotificationLog 병합으로 합성됨).
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
                caregiver_names.get(r.confirmed_by_caregiver_id, "보호자")
                if r.confirmed_by_type == "caregiver"
                else "본인"
            ),
        }
        for r in records
    ]

    # [2026-07-19 추가, REQ-037 Phase1] core/scheduler.py가 정시를 놓친 걸 감지하면
    # MedicationRecord가 아니라 NotificationLog(kind="missed")에 기록한다(레거시 스키마를
    # 안 건드리는 read-side 병합 — models.py NotificationLog 주석 참고). 실제 체크 기록이
    # 이미 있는 (schedule_id, 날짜)는 그 체크가 우선이므로 missed로 겹쳐 넣지 않는다.
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
            "confirmed_by_name": "자동 감지",
        }
        for notif in missed_notifs
        if (notif.schedule_id, notif.due_date) not in real_checked_dates
    )
    entries.sort(key=lambda e: e["checked_at"], reverse=True)
    return entries


class NotificationLogEntry(BaseModel):
    """[2026-07-23 추가] 알림함 — 복약 알림/놓침 감지가 이미 NotificationLog에 쌓이고
    있는데, 이걸 웹에서 모아 볼 화면이 없었다(푸시만 전제한 설계). 웹만 켜둔 환자·보호자도
    지난 알림을 확인할 수 있게 그대로 노출한다."""
    id: int
    schedule_id: int
    drug_name: str
    time_slot: str
    due_date: str
    kind: Literal["reminder", "missed"]
    status: Literal["pending", "sent", "suppressed", "failed"]
    fired_at: datetime


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
            drug_name=schedules[log.schedule_id].drug_name if log.schedule_id in schedules else "삭제된 일정",
            time_slot=log.time_slot,
            due_date=log.due_date,
            kind=log.kind,
            status=log.status,
            fired_at=log.fired_at,
        )
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
        .order_by(MedicationSchedule.time_slot)  # [2026-07-21 추가] 프론트가 시간대별로 그룹핑해서 보여줌
    ).all()

    result = []
    for s in schedules:
        record = session.exec(
            select(MedicationRecord)
            .where(MedicationRecord.schedule_id == s.id)
            .where(MedicationRecord.status.in_(["taken", "skipped"]))
            .where(func.date(MedicationRecord.taken_at) == today_str)
        ).first()
        if record:
            status = record.status
        else:
            # [2026-07-19 추가, REQ-037 Phase1] 오늘자 체크가 없으면, 스케줄러가 이미
            # "놓침"으로 판정해뒀는지 NotificationLog에서 확인한다(MedicationRecord 스키마는
            # 안 건드리는 read-side 병합).
            missed = session.exec(
                select(NotificationLog)
                .where(NotificationLog.schedule_id == s.id)
                .where(NotificationLog.due_date == today_str)
                .where(NotificationLog.kind == "missed")
            ).first()
            status = "missed" if missed else "pending"
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
