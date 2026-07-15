"""
auth_router.py — 보호자·환자 로그인 (담당: 박소정, 환자 로그인 확장: 김영혜)

[7/6 추가] app/ 예시 프로젝트의 JWT 로그인 방식을 이 SQLite 백엔드로 옮겨왔습니다.

[7/9] 환자(Patient)도 이제 로그인 대상입니다. 회원가입(계정 생성)은
monitoring_router.py의 POST /monitoring/patients, /monitoring/caregivers가
이름/연락처/비밀번호를 다 받아 처리하므로 여기서 중복 만들지 않고, 로그인만
보호자/환자 양쪽을 지원하도록 확장합니다 — 이메일 또는 전화번호 중 하나로
로그인할 수 있습니다(이름은 로그인 식별자로 쓰지 않음).

[2026-07-14] 여기 있던 POST /auth/signup(보호자 전용 가입)은 monitoring_router.py의
POST /monitoring/caregivers와 완전히 중복되는 죽은 코드였다(프론트/테스트 어디서도
호출 안 함, 이 파일 자체 docstring에도 "여기서 중복 안 만든다"고 적혀 있었음) — 혼란
방지를 위해 제거. 가입은 항상 monitoring_router.py를 통해서만.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from core.auth import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from core.database import get_session
from core.dependencies import Actor, get_current_actor
from core.email import send_password_reset_email
from core.security import generate_reset_code, hash_phone, hash_reset_code, normalize_email
from models import Caregiver, Patient, PasswordResetCode, PrivacyPurgeAudit

router = APIRouter(prefix="/auth", tags=["Auth"])

logger = logging.getLogger(__name__)

# [2026-07-15 추가, REQ-039] 5회 연속 실패 시 잠금. 임시번호는 10분 유효.
MAX_FAILED_LOGIN_ATTEMPTS = 5
RESET_CODE_EXPIRE_MINUTES = 10
# [2026-07-15 추가, REQ-035] 탈퇴 후 유예기간 — 이 안에는 취소 가능, 지나면 purge 스크립트가 삭제.
WITHDRAWAL_GRACE_DAYS = 30


class LoginRequest(BaseModel):
    identifier: str  # 이메일 또는 전화번호
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    caregiver_id: int
    name: str
    role: str  # "caregiver" / "patient" — 프론트가 로그인 후 흐름(보호자용/환자 본인용)을 분기하는 데 씀


class PasswordResetRequestRequest(BaseModel):
    identifier: str  # 이메일 또는 전화번호 — 계정을 찾는 용도(코드는 항상 가입 이메일로만 발송)


class PasswordResetVerifyRequest(BaseModel):
    identifier: str
    code: str


class PasswordResetVerifyResponse(BaseModel):
    reset_token: str  # POST /auth/password-reset/confirm 전용 — 일반 서비스 접근 불가(access 아님)


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str
    new_password: str


class WithdrawRequest(BaseModel):
    password: str  # 확인 절차(REQ-035) — 현재 비밀번호 재입력으로 본인 확인


class WithdrawCancelRequest(BaseModel):
    identifier: str  # 탈퇴 후에는 로그인이 막히므로(access_token 없음) login()과 같은 방식으로 본인 확인
    password: str


def _find_by_identifier(session: Session, model, identifier: str):
    """identifier가 이메일 형식이면 email로, 아니면 전화번호로 보고 phone_hash로 조회.

    [2026-07-14] 이메일은 대소문자·좌우공백 차이(모바일 자동대문자화 등)로 가입 때와
    다르게 입력돼도 같은 계정으로 찾아야 한다. 가입 시(monitoring_router.py)부터
    normalize_email()로 정규화해서 저장하므로, 조회할 때도 같은 정규화 함수로 비교한다
    — DB의 `func.lower()` 비교는 가입 시 저장값 자체가 정규화돼 있지 않으면 여전히
    " Test@x.com "과 "test@x.com"이 별개 계정으로 남는 문제를 못 막아서 채택하지 않았다.
    """
    if "@" in identifier:
        return session.exec(select(model).where(model.email == normalize_email(identifier))).first()
    return session.exec(select(model).where(model.phone_hash == hash_phone(identifier))).first()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)):
    """[7/9] 보호자/환자 양쪽 다 로그인 가능. 이메일 또는 전화번호로 식별.

    [2026-07-14] 실패 원인(계정 없음 vs 비밀번호 틀림)은 서버 로그에만 구분해서 남기고,
    클라이언트에는 어느 쪽인지 알 수 없는 통합 메시지만 준다(계정 존재 여부 추측 방지).

    [2026-07-15 추가, REQ-039] 계정 잠금 — 이 함수가 다루는 것은 caregiver/patient
    양쪽 다 같은 원칙이라 공용 헬퍼(_authenticate)로 뺐다.
    """
    caregiver = _find_by_identifier(session, Caregiver, payload.identifier)
    if caregiver:
        result = _authenticate(session, "caregiver", caregiver, payload.password)
        if result is not None:
            return _issue_login_response(response, caregiver.id, "caregiver", caregiver.name)

    patient = _find_by_identifier(session, Patient, payload.identifier)
    if patient:
        result = _authenticate(session, "patient", patient, payload.password)
        if result is not None:
            return _issue_login_response(response, patient.id, "patient", patient.name)

    if not caregiver and not patient:
        logger.info("login failed: no caregiver/patient matches identifier")

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일/전화번호 또는 비밀번호가 올바르지 않습니다.")


def _authenticate(session: Session, subject_type: str, account, password: str) -> bool | None:
    """비밀번호를 확인하고 실패 횟수/잠금을 갱신한다. 성공하면 True, 실패하면 None을 반환
    (locked-and-still-wrong도 실패로 취급 — 호출부는 항상 같은 통합 에러 메시지를 던짐).

    [2026-07-15 추가, REQ-039] 이미 잠긴 계정은 비밀번호가 맞아도 거부하고(재설정으로만
    해제), 실패 횟수를 5회에서 더 늘리지 않는다(이미 임시번호를 보낸 상태 유지).

    [2026-07-15 추가, REQ-035] 탈퇴(비활성화)된 계정도 비밀번호가 맞아도 로그인 거부 —
    30일 유예기간 안에 되돌리려면 POST /auth/withdraw/cancel을 쓴다(로그인 자체가
    막혀 있으니 access_token이 아니라 identifier+password로 본인 확인하는 별도 경로).
    """
    if account.deactivated_at is not None:
        logger.info("login rejected: %s_id=%s account deactivated (pending deletion)", subject_type, account.id)
        return None

    if account.locked_at is not None:
        logger.info("login rejected: %s_id=%s account locked", subject_type, account.id)
        return None

    if not account.hashed_password or not verify_password(password, account.hashed_password):
        account.failed_login_attempts += 1
        if account.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            account.locked_at = datetime.now()
            session.add(account)
            session.commit()
            logger.info("account locked: %s_id=%s, sending reset code", subject_type, account.id)
            _issue_reset_code(session, subject_type, account)
        else:
            session.add(account)
            session.commit()
            logger.info(
                "login failed: %s_id=%s wrong password (%d/%d)",
                subject_type, account.id, account.failed_login_attempts, MAX_FAILED_LOGIN_ATTEMPTS,
            )
        return None

    if account.failed_login_attempts:
        account.failed_login_attempts = 0
        session.add(account)
        session.commit()
    return True


def _issue_reset_code(session: Session, subject_type: str, account) -> None:
    """임시번호를 생성·해시 저장하고 가입 이메일로 발송한다. account.email이 없으면
    (전화번호만으로 가입한 계정) 보낼 곳이 없으니 로그만 남기고 조용히 넘어간다 — 이
    경우 사용자는 팀에 직접 문의해야 한다(현재 SMS 발송 채널은 없음, 사용자 확인 사항)."""
    code = generate_reset_code()
    reset_code = PasswordResetCode(
        subject_type=subject_type,
        subject_id=account.id,
        code_hash=hash_reset_code(code),
        expires_at=datetime.now() + timedelta(minutes=RESET_CODE_EXPIRE_MINUTES),
    )
    session.add(reset_code)
    session.commit()

    if account.email:
        send_password_reset_email(account.email, code)
    else:
        logger.warning(
            "%s_id=%s has no email on file — reset code generated but not sent", subject_type, account.id
        )


def _issue_login_response(response: Response, subject_id: int, role: str, name: str) -> LoginResponse:
    access_token = create_access_token(subject_id, role)
    refresh_token = create_refresh_token(subject_id, role)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return LoginResponse(access_token=access_token, caregiver_id=subject_id, name=name, role=role)


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
    return LoginResponse(access_token=create_access_token(subject_id, role), caregiver_id=subject_id, name=subject.name, role=role)


# ── 비밀번호 재설정 [2026-07-15 추가, REQ-039] ──
# request(임시번호 발송) → verify(임시번호 확인, reset_token 발급) → confirm(새 비밀번호
# 설정, 잠금 해제) 3단계. 계정 잠금 시 자동으로도 request와 동일한 동작(_issue_reset_code)이
# 일어나므로, 사용자가 이메일을 못 받았거나 잠기기 전에 미리 재설정하고 싶을 때도 request를
# 그대로 쓸 수 있다.


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequestRequest, session: Session = Depends(get_session)):
    """임시번호 발송. 계정 존재 여부를 알려주지 않기 위해 찾았든 못 찾았든 같은 응답을 준다."""
    account = _find_by_identifier(session, Caregiver, payload.identifier)
    subject_type = "caregiver"
    if not account:
        account = _find_by_identifier(session, Patient, payload.identifier)
        subject_type = "patient"

    if account:
        _issue_reset_code(session, subject_type, account)

    return {"message": "계정이 존재하면 인증코드를 이메일로 보냈습니다."}


@router.post("/password-reset/verify", response_model=PasswordResetVerifyResponse)
def verify_password_reset(payload: PasswordResetVerifyRequest, session: Session = Depends(get_session)):
    """임시번호를 확인하고, 맞으면 confirm 전용 reset_token을 발급한다."""
    account = _find_by_identifier(session, Caregiver, payload.identifier)
    subject_type = "caregiver"
    if not account:
        account = _find_by_identifier(session, Patient, payload.identifier)
        subject_type = "patient"

    if not account:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "인증코드가 올바르지 않거나 만료되었습니다.")

    code_hash = hash_reset_code(payload.code)
    now = datetime.now()
    reset_code = session.exec(
        select(PasswordResetCode)
        .where(PasswordResetCode.subject_type == subject_type)
        .where(PasswordResetCode.subject_id == account.id)
        .where(PasswordResetCode.code_hash == code_hash)
        .where(PasswordResetCode.used_at.is_(None))
        .where(PasswordResetCode.expires_at > now)
        .order_by(PasswordResetCode.created_at.desc())
    ).first()
    if not reset_code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "인증코드가 올바르지 않거나 만료되었습니다.")

    reset_code.used_at = now
    session.add(reset_code)
    session.commit()

    return PasswordResetVerifyResponse(reset_token=create_password_reset_token(account.id, subject_type))


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirmRequest, session: Session = Depends(get_session)):
    """reset_token으로 새 비밀번호를 설정하고, 잠금과 실패 횟수를 초기화한다."""
    try:
        subject_id, role = decode_token(payload.reset_token, expected_type="password_reset")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않거나 만료된 재설정 토큰입니다.")

    model = Caregiver if role == "caregiver" else Patient
    account = session.get(model, subject_id)
    if not account:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증에 실패했습니다.")

    account.hashed_password = hash_password(payload.new_password)
    account.failed_login_attempts = 0
    account.locked_at = None
    session.add(account)
    session.commit()

    return {"message": "비밀번호가 재설정되었습니다. 새 비밀번호로 로그인해주세요."}


# ── 회원 탈퇴 [2026-07-15 추가, REQ-035] ──
# 요청은 현재 세션(access_token)으로, 취소는 로그인이 막힌 상태이므로 identifier+password로.


@router.post("/withdraw")
def withdraw(
    payload: WithdrawRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """탈퇴 요청 — 즉시 비활성화하고 30일 뒤 개인정보를 영구 삭제한다(purge_expired_accounts.py가
    scheduled_purge_at을 기준으로 실행). 확인 절차로 현재 비밀번호 재입력을 요구한다."""
    role, account = actor
    if not account.hashed_password or not verify_password(payload.password, account.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "비밀번호가 올바르지 않습니다.")
    if account.deactivated_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "이미 탈퇴 처리된 계정입니다.")

    now = datetime.now()
    scheduled_purge_at = now + timedelta(days=WITHDRAWAL_GRACE_DAYS)
    account.deactivated_at = now
    account.deletion_scheduled_at = scheduled_purge_at
    session.add(account)
    session.add(
        PrivacyPurgeAudit(
            subject_type=role,
            subject_id=account.id,
            deactivated_at=now,
            scheduled_purge_at=scheduled_purge_at,
        )
    )
    session.commit()

    return {
        "message": "탈퇴 처리되었습니다. 30일 이내에 취소하지 않으면 개인정보가 영구 삭제됩니다.",
        "deletion_scheduled_at": scheduled_purge_at.isoformat(),
    }


@router.post("/withdraw/cancel")
def cancel_withdrawal(payload: WithdrawCancelRequest, session: Session = Depends(get_session)):
    """탈퇴 취소(30일 유예기간 내). 탈퇴된 계정은 login()에서 거부되므로 access_token을 쓸 수
    없다 — login()과 동일하게 identifier+password로 본인 확인한다."""
    account = _find_by_identifier(session, Caregiver, payload.identifier)
    subject_type = "caregiver"
    if not account:
        account = _find_by_identifier(session, Patient, payload.identifier)
        subject_type = "patient"

    if not account or not account.hashed_password or not verify_password(payload.password, account.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일/전화번호 또는 비밀번호가 올바르지 않습니다.")
    if account.deactivated_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "탈퇴 처리된 계정이 아닙니다.")

    now = datetime.now()
    if account.deletion_scheduled_at and account.deletion_scheduled_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "삭제 예정 시각이 지나 더 이상 취소할 수 없습니다.")

    account.deactivated_at = None
    account.deletion_scheduled_at = None
    session.add(account)

    audit = session.exec(
        select(PrivacyPurgeAudit)
        .where(PrivacyPurgeAudit.subject_type == subject_type)
        .where(PrivacyPurgeAudit.subject_id == account.id)
        .where(PrivacyPurgeAudit.status == "pending")
        .order_by(PrivacyPurgeAudit.requested_at.desc())
    ).first()
    if audit:
        audit.status = "cancelled"
        session.add(audit)
    session.commit()

    return {"message": "탈퇴가 취소되었습니다."}
