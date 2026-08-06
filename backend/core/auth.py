"""
auth.py — 비밀번호 해시 + JWT 발급/검증 (담당: 박소정, 환자 로그인 확장: 김영혜)

[7/6 추가] app/ 예시 프로젝트(FastAPI+Tortoise 버전)에 있던 로그인 방식을
이 SQLite 백엔드에 맞게 옮겨왔습니다.

[7/9] 환자(Patient)도 로그인 대상으로 바뀌어서, 토큰에 "누구의(subject_id) 어떤
역할(role: caregiver/patient)"인지를 함께 담는다 — Caregiver.id와 Patient.id는
서로 다른 테이블의 PK라 값이 겹칠 수 있으므로, role 없이 subject_id만으로는
어느 테이블에서 찾아야 하는지 알 수 없다.

[2026-07-15] SECRET_KEY는 로컬/테스트에서만 데모용 기본값을 쓴다 — development/production은
DATABASE_URL과 동일하게, 값이 없으면 서버 기동 자체를 거부한다(소스에 그대로 적힌 기본값으로
JWT를 서명하는 사고를 막기 위함).
"""
import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from core.database import APP_ENV

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if APP_ENV in ("development", "production"):
        raise RuntimeError(
            f"APP_ENV={APP_ENV}인데 SECRET_KEY가 설정되지 않았습니다. "
            "JWT 서명에 쓰이는 값이라 반드시 강력한 랜덤 값으로 지정해야 합니다."
        )
    SECRET_KEY = "change-this-secret-key-before-deploy"  # local/test 전용 기본값
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_MINUTES = 14 * 24 * 60  # 14일
# [2026-07-15 추가, REQ-039] 임시번호 검증 성공 후 발급되는 전용 토큰 — 이 토큰으로는
# "새 비밀번호 설정"(POST /auth/password-reset/confirm) 외에는 아무것도 못 하게
# get_current_actor 등 일반 인증 의존성이 이 type을 거부해야 한다(로그인 완전 우회 방지).
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 10

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
        "exp": datetime.now(UTC) + expires_delta,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject_id: int, role: str) -> str:
    return _create_token(subject_id, role, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject_id: int, role: str) -> tuple[str, str]:
    """[2026-07-15 추가] JWT 자체엔 무효화 개념이 없어서, 발급마다 고유 jti를 심어 반환한다 —
    호출부가 이 jti를 RefreshToken 테이블에 저장해두고, 회전(재발급) 시 이전 jti를 revoke하는
    방식으로 "탈취된 토큰이 만료 전까지 계속 유효한" 문제를 막는다. 반환값: (JWT 문자열, jti)."""
    jti = uuid.uuid4().hex
    payload = {
        "subject_id": subject_id,
        "role": role,
        "type": "refresh",
        "jti": jti,
        "exp": datetime.now(UTC) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti


def create_password_reset_token(subject_id: int, role: str) -> str:
    """[2026-07-15 추가, REQ-039] 임시번호 검증 성공 후 발급 — expected_type="access"를
    요구하는 get_current_actor 등 기존 인증 의존성으로는 절대 통과할 수 없다."""
    return _create_token(subject_id, role, "password_reset", timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES))


def decode_token(token: str, expected_type: str) -> tuple[int, str]:
    """토큰을 검증하고 (subject_id, role)을 반환. 실패하면 jwt.PyJWTError 계열 예외를 던짐."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")
    return payload["subject_id"], payload["role"]


def decode_refresh_token(token: str) -> tuple[int, str, str]:
    """decode_token과 같지만 jti(회전·재사용 탐지용 고유 id)까지 반환 — /auth/token/refresh 전용."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError(f"Expected token type 'refresh', got '{payload.get('type')}'")
    jti = payload.get("jti")
    if not jti:
        raise jwt.InvalidTokenError("jti가 없는 refresh token입니다.")
    return payload["subject_id"], payload["role"], jti
