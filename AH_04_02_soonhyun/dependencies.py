"""
dependencies.py — 로그인한 보호자를 구하는 공용 의존성 (담당: 박소정)

라우터에서 이렇게 씁니다:
    current_caregiver: Caregiver = Depends(get_current_caregiver)
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from auth import decode_token
from database import get_session
from models import Caregiver

security = HTTPBearer()


def get_current_caregiver(
    credential: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> Caregiver:
    try:
        caregiver_id = decode_token(credential.credentials, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")

    caregiver = session.get(Caregiver, caregiver_id)
    if not caregiver:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했습니다.")
    return caregiver
