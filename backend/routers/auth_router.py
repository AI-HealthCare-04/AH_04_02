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

from auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from database import get_session
from models import Caregiver, Patient
from security import hash_phone

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
        return _issue_login_response(response, caregiver.id, "caregiver", caregiver.name)

    patient = _find_by_identifier(session, Patient, payload.identifier)
    if patient and patient.hashed_password and verify_password(payload.password, patient.hashed_password):
        return _issue_login_response(response, patient.id, "patient", patient.name)

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일/전화번호 또는 비밀번호가 올바르지 않습니다.")


def _issue_login_response(response: Response, subject_id: int, role: str, name: str) -> LoginResponse:
    access_token = create_access_token(subject_id, role)
    refresh_token = create_refresh_token(subject_id, role)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return LoginResponse(access_token=access_token, caregiver_id=subject_id, name=name)


@router.get("/token/refresh", response_model=LoginResponse)
def refresh_token(refresh_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    """login에서 set_cookie로 심어둔 refresh_token 쿠키를 읽어서 새 access_token을 발급."""
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token이 없습니다.")
    try:
        subject_id, role = decode_token(refresh_token, expected_type="refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않거나 만료된 refresh token입니다.")

    model = Caregiver if role == "caregiver" else Patient
    subject = session.get(model, subject_id)
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증에 실패했습니다.")
    return LoginResponse(access_token=create_access_token(subject_id, role), caregiver_id=subject_id, name=subject.name)
