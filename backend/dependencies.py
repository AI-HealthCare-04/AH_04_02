"""
dependencies.py — 로그인한 사용자(보호자/환자)를 구하는 공용 의존성 (담당: 박소정, 환자 로그인 확장: 김영혜)

라우터에서 이렇게 씁니다:
    current_caregiver: Caregiver = Depends(get_current_caregiver)
    current_patient: Patient = Depends(get_current_patient)  # [7/9 추가]
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from auth import decode_token
from database import get_session
from models import Caregiver, Patient

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
