"""
auth_router.py — 보호자·요양보호사 회원가입/로그인 (담당: 박소정)

[7/6 추가] app/ 예시 프로젝트의 JWT 로그인 방식을 이 SQLite 백엔드로 옮겨왔습니다.
환자(Patient)는 로그인하지 않고, Caregiver만 계정을 가집니다.
"""
from __future__ import annotations
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from database import get_session
from models import Caregiver

router = APIRouter(prefix="/auth", tags=["Auth"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    relation_type: str = "guardian"  # guardian / caregiver / life_support_worker / social_worker


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(Caregiver).where(Caregiver.email == payload.email)).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 이메일입니다.")

    caregiver = Caregiver(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        relation_type=payload.relation_type,
    )
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return {"id": caregiver.id, "email": caregiver.email, "name": caregiver.name}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)):
    caregiver = session.exec(select(Caregiver).where(Caregiver.email == payload.email)).first()
    if not caregiver or not verify_password(payload.password, caregiver.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일 또는 비밀번호가 올바르지 않습니다.")

    access_token = create_access_token(caregiver.id)
    refresh_token = create_refresh_token(caregiver.id)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return LoginResponse(access_token=access_token)


@router.get("/token/refresh", response_model=LoginResponse)
def refresh_token(refresh_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    """login에서 set_cookie로 심어둔 refresh_token 쿠키를 읽어서 새 access_token을 발급."""
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token이 없습니다.")
    try:
        caregiver_id = decode_token(refresh_token, expected_type="refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않거나 만료된 refresh token입니다.")

    if not session.get(Caregiver, caregiver_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증에 실패했습니다.")
    return LoginResponse(access_token=create_access_token(caregiver_id))
