"""
dependencies.py — 로그인한 사용자(보호자/환자)를 구하는 공용 의존성 (담당: 박소정, 환자 로그인 확장: 김영혜)

라우터에서 이렇게 씁니다:
    current_caregiver: Caregiver = Depends(get_current_caregiver)
    current_patient: Patient = Depends(get_current_patient)  # [7/9 추가]
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from core.auth import decode_token
from core.database import get_session
from models import Caregiver, CaregiverPatient, Patient

security = HTTPBearer()


def get_current_caregiver(
    credential: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> Caregiver:
    try:
        subject_id, role = decode_token(credential.credentials, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")
    if role != "caregiver":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="보호자 계정 토큰이 아닙니다.")

    caregiver = session.get(Caregiver, subject_id)
    if not caregiver:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했습니다.")
    return caregiver


def get_current_patient(
    credential: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> Patient:
    """[7/9 추가] 환자 본인 로그인용 — get_current_caregiver와 동일한 패턴."""
    try:
        subject_id, role = decode_token(credential.credentials, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")
    if role != "patient":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="환자 계정 토큰이 아닙니다.")

    patient = session.get(Patient, subject_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했습니다.")
    return patient


def require_patient_access(patient_id: int, caregiver: Caregiver, session: Session) -> None:
    """[7/10 추가] caregiver가 이 patient_id를 실제로 케어하는지 확인 — issue #21.
    monitoring_router.py/care_router.py의 모든 patient_id 기반 엔드포인트에서 공용으로 씀."""
    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver.id)
        .where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 환자에 대한 권한이 없습니다.")


Actor = tuple[str, "Caregiver | Patient"]


def get_current_actor(
    credential: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> Actor:
    """[7/13 추가] 보호자·환자 둘 다 로그인할 수 있는 공유 화면(Dashboard/Schedule/
    Notification/Records/Connect)용 — 토큰의 role을 보고 알맞은 테이블에서 찾아
    (role, 본인 레코드)를 반환한다. issue #21 나머지 범위, issue #28의 환자 본인
    로그인과 짝을 이룸."""
    try:
        subject_id, role = decode_token(credential.credentials, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")

    model = Caregiver if role == "caregiver" else Patient
    actor = session.get(model, subject_id)
    if not actor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했습니다.")
    return role, actor


def require_actor_patient_access(patient_id: int, actor: Actor, session: Session) -> None:
    """get_current_actor로 얻은 (role, 본인) 조합이 이 patient_id에 접근할 권한이 있는지 확인.
    환자 본인이면 자기 자신인지, 보호자면 연결된 환자인지 검사."""
    role, subject = actor
    if role == "patient":
        if subject.id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인 데이터만 볼 수 있어요.")
        return
    require_patient_access(patient_id, subject, session)
