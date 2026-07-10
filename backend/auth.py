"""
auth.py — 비밀번호 해시 + JWT 발급/검증 (담당: 박소정, 환자 로그인 확장: 김영혜)

[7/6 추가] app/ 예시 프로젝트(FastAPI+Tortoise 버전)에 있던 로그인 방식을
이 SQLite 백엔드에 맞게 옮겨왔습니다.

[7/9] 환자(Patient)도 로그인 대상으로 바뀌어서, 토큰에 "누구의(subject_id) 어떤
역할(role: caregiver/patient)"인지를 함께 담는다 — Caregiver.id와 Patient.id는
서로 다른 테이블의 PK라 값이 겹칠 수 있으므로, role 없이 subject_id만으로는
어느 테이블에서 찾아야 하는지 알 수 없다.

⚠️ SECRET_KEY는 데모용 기본값입니다. 실제 배포 전에는 반드시 .env 등으로 바꾸세요.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deploy")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_MINUTES = 14 * 24 * 60  # 14일

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject_id: int, role: str, token_type: str, expires_delta: timedelta) -> str:
    payload = {
        "subject_id": subject_id,
        "role": role,  # "caregiver" | "patient"
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject_id: int, role: str) -> str:
    return _create_token(subject_id, role, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject_id: int, role: str) -> str:
    return _create_token(subject_id, role, "refresh", timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES))


def decode_token(token: str, expected_type: str) -> tuple[int, str]:
    """토큰을 검증하고 (subject_id, role)을 반환. 실패하면 jwt.PyJWTError 계열 예외를 던짐."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")
    return payload["subject_id"], payload["role"]
