"""
auth_router.py — 보호자·환자 로그인, 보호자 회원가입 (담당: 박소정, 환자 로그인 확장: 김영혜)

[7/6 추가] app/ 예시 프로젝트의 JWT 로그인 방식을 이 SQLite 백엔드로 옮겨왔습니다.

[7/9] 환자(Patient)도 이제 로그인 대상입니다. 회원가입(계정 생성)은 이미
monitoring_router.py의 POST /monitoring/patients, /monitoring/caregivers가
이름/연락처/비밀번호를 다 받아 처리하므로 여기서 중복 만들지 않고, 로그인만
보호자/환자 양쪽을 지원하도록 확장합니다 — 이메일 또는 전화번호 중 하나로
로그인할 수 있습니다(이름은 로그인 식별자로 쓰지 않음).
"""
from __future__ import annotations
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, func, select

from datetime import datetime, timedelta

from core.auth import (
    REFRESH_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from core.database import get_session
from models import Caregiver, Patient, RefreshToken
from core.security import hash_phone

router = APIRouter(prefix="/auth", tags=["Auth"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    relation_type: str = "guardian"  # guardian / caregiver / life_support_worker / social_worker


class LoginRequest(BaseModel):
    identifier: str  # 이메일 또는 전화번호
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    caregiver_id: int
    name: str
    role: str  # "caregiver" / "patient" — 프론트가 로그인 후 흐름(보호자용/환자 본인용)을 분기하는 데 씀


def _find_by_identifier(session: Session, model, identifier: str):
    """identifier가 이메일 형식이면 email로, 아니면 전화번호로 보고 phone_hash로 조회.
    이메일은 대소문자·좌우공백 차이(모바일 자동대문자화 등)로 가입 때와 다르게
    입력돼도 같은 계정으로 찾도록 대소문자 무시 비교한다."""
    if "@" in identifier:
        norm = identifier.strip().lower()
        return session.exec(select(model).where(func.lower(model.email) == norm)).first()
    return session.exec(select(model).where(model.phone_hash == hash_phone(identifier))).first()


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(Caregiver).where(Caregiver.email == payload.email)).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 이메일입니다.")

    caregiver = Caregiver(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        relation_type=payload.relation_type,
    )
    caregiver.name = payload.name  # [7/9] setter가 암호화해서 name_encrypted에 저장
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return {"id": caregiver.id, "email": caregiver.email, "name": caregiver.name}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)):
    """[7/9] 보호자/환자 양쪽 다 로그인 가능. 이메일 또는 전화번호로 식별."""
    caregiver = _find_by_identifier(session, Caregiver, payload.identifier)
    if caregiver and caregiver.hashed_password and verify_password(payload.password, caregiver.hashed_password):
        return _issue_login_response(response, caregiver.id, "caregiver", caregiver.name, session)

    patient = _find_by_identifier(session, Patient, payload.identifier)
    if patient and patient.hashed_password and verify_password(payload.password, patient.hashed_password):
        return _issue_login_response(response, patient.id, "patient", patient.name, session)

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일/전화번호 또는 비밀번호가 올바르지 않습니다.")


def _issue_login_response(response: Response, subject_id: int, role: str, name: str, session: Session) -> LoginResponse:
    """[2026-07-15] refresh 토큰 발급마다 jti를 RefreshToken 테이블에 기록 — /token/refresh가
    회전(재발급) 시 이 jti를 revoke해서 재사용을 막는다(REQ-001)."""
    access_token = create_access_token(subject_id, role)
    refresh_token, jti = create_refresh_token(subject_id, role)
    session.add(RefreshToken(
        jti=jti,
        subject_id=subject_id,
        role=role,
        expires_at=datetime.now() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
    ))
    session.commit()
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return LoginResponse(access_token=access_token, caregiver_id=subject_id, name=name, role=role)


@router.get("/token/refresh", response_model=LoginResponse)
def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    """login에서 set_cookie로 심어둔 refresh_token 쿠키를 검증하고, 새 access_token과
    함께 새 refresh_token도 발급한다(rotation) — 이전 jti는 revoke 처리해 재사용을 막는다.
    [2026-07-15] 예전엔 access_token만 새로 발급하고 같은 refresh_token을 계속 재사용해서,
    탈취된 refresh_token이 만료(14일) 전까지 계속 유효했다(REQ-001)."""
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token이 없습니다.")
    try:
        subject_id, role, jti = decode_refresh_token(refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않거나 만료된 refresh token입니다.")

    stored = session.get(RefreshToken, jti)
    if not stored or stored.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이미 사용되었거나 무효화된 refresh token입니다.")

    model = Caregiver if role == "caregiver" else Patient
    subject = session.get(model, subject_id)
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증에 실패했습니다.")

    stored.revoked = True
    session.add(stored)
    session.commit()

    return _issue_login_response(response, subject_id, role, subject.name, session)
