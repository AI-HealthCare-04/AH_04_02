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
from core.auth import (
    REFRESH_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from core.database import get_session
from core.dependencies import Actor, get_current_actor
from core.email import send_password_reset_email
from core.security import generate_reset_code, hash_phone, hash_reset_code, normalize_email
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from models import Caregiver, PasswordResetCode, Patient, PrivacyPurgeAudit, RefreshToken
from pydantic import BaseModel
from sqlalchemy import update
from sqlmodel import Session, select

router = APIRouter(prefix="/auth", tags=["Auth"])

logger = logging.getLogger(__name__)

# [2026-07-15 추가, REQ-039] 5회 연속 실패 시 잠금. 임시번호는 10분 유효.
MAX_FAILED_LOGIN_ATTEMPTS = 5
RESET_CODE_EXPIRE_MINUTES = 10
# [2026-07-15 추가, PR #48 팀원 리뷰 반영] 잠금이 영구적이면 (1) 자력 복구 수단이 없는
# 전화번호 전용 계정이 영영 못 들어오고, (2) identifier만 아는 공격자가 비인증 상태로
# 아무 계정이나 잠가버리는 DoS가 가능하다 — N분 뒤 자동 해제해 두 문제를 완화한다.
LOCKOUT_DURATION_MINUTES = 30
# [2026-07-15 추가, PR #48 팀원 리뷰 반영] 재발급 시 이전 미사용 코드를 무효화하므로
# 한 계정당 항상 유효 코드가 최대 1개만 존재한다 — 이 쿨다운은 순전히 재요청 남발/이메일
# 스팸 방지용(브루트포스 방어는 아래 MAX_RESET_CODE_VERIFY_ATTEMPTS가 담당).
RESET_CODE_REQUEST_COOLDOWN_SECONDS = 60
# [2026-07-15 추가, 자체 검증(security-reviewer) 라운드 1 지적 반영] 위 쿨다운은 "아직
# 살아있는 코드가 있을 때"만 막는다 — 공격자가 매번 verify를 5번 틀려서(MAX_RESET_CODE_
# VERIFY_ATTEMPTS) 코드를 스스로 무효화시키면 existing 쿼리가 빈 결과를 반환해 쿨다운을
# 우회하고 새 코드를 계속 발급/발송받을 수 있었다 — 코드 상태와 무관하게 "이 계정에
# 최근 N분간 발급된 코드 수" 자체를 세는 진짜 요청 횟수 제한을 추가한다.
MAX_RESET_CODE_REQUESTS_PER_WINDOW = 3
RESET_CODE_REQUEST_WINDOW_MINUTES = 10
# [2026-07-15 추가, PR #48 팀원 리뷰 반영] verify 시도 횟수 제한 없이는 6자리 코드를
# 자동화된 요청으로 브루트포스할 수 있었다 — 이 횟수를 넘으면 코드를 강제 무효화한다.
MAX_RESET_CODE_VERIFY_ATTEMPTS = 5
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
    # [2026-07-22 추가] role == "caregiver"일 때만 의미있음("guardian"/"organization") — 프론트의
    # 계정 전환 목록이 "환자 본인/보호자/기관" 표시에 쓴다.
    relation_type: str | None = None
    # [2026-07-22 추가] "저장된 계정" 전환 기능 전용 — access_token(60분)이 만료돼도 이 값으로
    # 새 access_token을 스스로 받아올 수 있게 계정별로 저장해둔다. 재사용 방지로 매번 새로
    # 발급되므로(POST /auth/token/refresh), 쓸 때마다 이 값도 같이 새로 저장해야 한다.
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    # [2026-07-22 추가] 계정 전환 기능은 계정마다 refresh_token이 달라서 브라우저 쿠키
    # 하나(로그인 하나만 담을 수 있음)로는 표현이 안 된다 — 명시적으로 넘기면 그걸 쓰고,
    # 없으면 기존처럼 쿠키를 쓴다(일반 로그인 흐름과 호환).
    refresh_token: str | None = None


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


def _find_by_identifiers(session: Session, model, identifier: str) -> list:
    """identifier가 이메일 형식이면 email로, 아니면 전화번호로 보고 phone_hash로 조회 —
    일치하는 계정을 전부 반환한다.

    [2026-07-14] 이메일은 대소문자·좌우공백 차이(모바일 자동대문자화 등)로 가입 때와
    다르게 입력돼도 같은 계정으로 찾아야 한다. 가입 시(monitoring_router.py)부터
    normalize_email()로 정규화해서 저장하므로, 조회할 때도 같은 정규화 함수로 비교한다
    — DB의 `func.lower()` 비교는 가입 시 저장값 자체가 정규화돼 있지 않으면 여전히
    " Test@x.com "과 "test@x.com"이 별개 계정으로 남는 문제를 못 막아서 채택하지 않았다.

    [2026-07-22 추가] 전화번호는 이메일과 달리 테이블 전체가 아니라 관계(역할)당 유니크로
    바뀌었다 — 같은 사람이 환자 본인/보호자/기관 계정을 각각 하나씩 같은 전화번호로 가질 수
    있다(monitoring_router.py). 그래서 phone_hash 조회는 이제 여러 계정을 반환할 수 있고,
    login()은 비밀번호가 맞는 계정을 찾을 때까지 이 목록을 순회한다.
    """
    if "@" in identifier:
        return list(session.exec(select(model).where(model.email == normalize_email(identifier))).all())
    return list(session.exec(select(model).where(model.phone_hash == hash_phone(identifier))).all())


def _find_by_identifier(session: Session, model, identifier: str):
    """단일 계정만 다루는 기존 호출부(비밀번호 재설정/탈퇴 취소)용 — 여러 계정이 걸려도
    첫 번째만 본다. 이 세 곳까지 멀티 계정 대응하는 건 지금 범위 밖(TODO)."""
    return next(iter(_find_by_identifiers(session, model, identifier)), None)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)):
    """[7/9] 보호자/환자 양쪽 다 로그인 가능. 이메일 또는 전화번호로 식별.

    [2026-07-14] 실패 원인(계정 없음 vs 비밀번호 틀림)은 서버 로그에만 구분해서 남기고,
    클라이언트에는 어느 쪽인지 알 수 없는 통합 메시지만 준다(계정 존재 여부 추측 방지).

    [2026-07-15 추가, REQ-039] 계정 잠금 — 이 함수가 다루는 것은 caregiver/patient
    양쪽 다 같은 원칙이라 공용 헬퍼(_authenticate)로 뺐다.

    [2026-07-22 추가] 전화번호가 이제 관계(역할)당 유니크라 한 사람이 환자 본인/보호자/
    기관 계정을 같은 전화번호로 여러 개 가질 수 있다 — 후보 전부를 비밀번호가 맞는 계정을
    찾을 때까지 순회한다(첫 번째만 보면 다른 역할 계정에 걸려 정작 본인 계정 로그인이
    실패하는 버그가 남).
    """
    caregivers = _find_by_identifiers(session, Caregiver, payload.identifier)
    for caregiver in caregivers:
        if _authenticate(session, "caregiver", caregiver, payload.password) is not None:
            return _issue_login_response(
                response, caregiver.id, "caregiver", caregiver.name, session, relation_type=caregiver.relation_type
            )

    patients = _find_by_identifiers(session, Patient, payload.identifier)
    for patient in patients:
        if _authenticate(session, "patient", patient, payload.password) is not None:
            return _issue_login_response(response, patient.id, "patient", patient.name, session)

    if not caregivers and not patients:
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
        if datetime.now() - account.locked_at >= timedelta(minutes=LOCKOUT_DURATION_MINUTES):
            logger.info("account auto-unlocked: %s_id=%s (lockout duration elapsed)", subject_type, account.id)
            account.locked_at = None
            account.failed_login_attempts = 0
            session.add(account)
            session.commit()
        else:
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
    경우 사용자는 잠금 자동 해제(LOCKOUT_DURATION_MINUTES)를 기다리거나 팀에 문의해야 한다.

    [2026-07-15 추가, PR #48 팀원 리뷰 반영 — CRITICAL] 이전에는 호출할 때마다 코드를
    무조건 새로 추가만 해서, 동시에 여러 개의 유효한 코드가 쌓일 수 있었다(브루트포스
    성공 확률이 쌓인 코드 수만큼 올라감 — /password-reset/request는 비인증으로 반복
    호출 가능). 이제는 (1) 기존 미사용 코드가 있으면 새로 발급하기 전에 무효화해서
    항상 최대 1개의 유효 코드만 존재하게 하고, (2) 방금(쿨다운 이내) 발급한 게 아직
    살아있으면 재발급 자체를 건너뛴다(이메일 스팸/DB 남발 방지 — 어차피 새 코드를
    만들면 헌 코드는 무효화되므로 스팸 방지 외에 보안상 의미는 없다).

    [2026-07-15 추가, 자체 검증 라운드 1 지적 반영] 위 (1)(2)만으로는 공격자가
    verify를 일부러 5번 틀려 코드를 스스로 무효화시킨 뒤 다시 request를 호출하는 식으로
    쿨다운을 반복 우회해 사실상 무제한으로 새 코드/이메일을 받아갈 수 있었다 — 코드
    상태와 무관하게 "최근 RESET_CODE_REQUEST_WINDOW_MINUTES분 안에 이 계정으로 발급된
    코드 수" 자체를 세어 MAX_RESET_CODE_REQUESTS_PER_WINDOW를 넘으면 무효화 여부와
    상관없이 발급을 거부한다(진짜 요청 횟수 제한)."""
    now = datetime.now()
    window_start = now - timedelta(minutes=RESET_CODE_REQUEST_WINDOW_MINUTES)
    recent_request_count = len(
        session.exec(
            select(PasswordResetCode)
            .where(PasswordResetCode.subject_type == subject_type)
            .where(PasswordResetCode.subject_id == account.id)
            .where(PasswordResetCode.created_at >= window_start)
        ).all()
    )
    if recent_request_count >= MAX_RESET_CODE_REQUESTS_PER_WINDOW:
        logger.info(
            "reset code request rate-limited: %s_id=%s (%d requests in last %d min)",
            subject_type, account.id, recent_request_count, RESET_CODE_REQUEST_WINDOW_MINUTES,
        )
        return

    existing = session.exec(
        select(PasswordResetCode)
        .where(PasswordResetCode.subject_type == subject_type)
        .where(PasswordResetCode.subject_id == account.id)
        .where(PasswordResetCode.used_at.is_(None))
        .order_by(PasswordResetCode.created_at.desc())
    ).first()
    if existing and existing.expires_at > now and (now - existing.created_at) < timedelta(
        seconds=RESET_CODE_REQUEST_COOLDOWN_SECONDS
    ):
        return
    if existing:
        existing.used_at = now
        session.add(existing)

    code = generate_reset_code()
    reset_code = PasswordResetCode(
        subject_type=subject_type,
        subject_id=account.id,
        code_hash=hash_reset_code(code),
        expires_at=now + timedelta(minutes=RESET_CODE_EXPIRE_MINUTES),
    )
    session.add(reset_code)
    session.commit()

    if account.email:
        send_password_reset_email(account.email, code)
    else:
        logger.warning(
            "%s_id=%s has no email on file — reset code generated but not sent", subject_type, account.id
        )


def _issue_login_response(
    response: Response, subject_id: int, role: str, name: str, session: Session, relation_type: str | None = None
) -> LoginResponse:
    """[2026-07-15] refresh 토큰 발급마다 jti를 RefreshToken 테이블에 기록 — /token/refresh가
    회전(재발급) 시 이 jti를 revoke해서 재사용을 막는다(REQ-001)."""
    access_token = create_access_token(subject_id, role)
    refresh_token_value, jti = create_refresh_token(subject_id, role)
    session.add(RefreshToken(
        jti=jti,
        subject_id=subject_id,
        role=role,
        expires_at=datetime.now() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
    ))
    session.commit()
    response.set_cookie(key="refresh_token", value=refresh_token_value, httponly=True)
    return LoginResponse(
        access_token=access_token,
        caregiver_id=subject_id,
        name=name,
        role=role,
        relation_type=relation_type,
        refresh_token=refresh_token_value,
    )


@router.post("/token/refresh", response_model=LoginResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    response: Response,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    session: Session = Depends(get_session),
):
    """login에서 심어둔 refresh_token(쿠키 또는 계정 전환 기능이 명시적으로 넘긴 값)을
    검증하고, 새 access_token과 함께 새 refresh_token도 발급한다(rotation) — 이전 jti는
    revoke 처리해 재사용을 막는다.
    [2026-07-15] 예전엔 access_token만 새로 발급하고 같은 refresh_token을 계속 재사용해서,
    탈취된 refresh_token이 만료(14일) 전까지 계속 유효했다(REQ-001).
    [2026-07-22 수정] GET에서 POST로 변경 — 계정 전환 기능은 요청 바디로 refresh_token을
    명시적으로 넘겨야 해서(쿠키 하나로는 계정별 값을 구분 못 함) 더 이상 GET만으로는 부족했다."""
    token = payload.refresh_token or refresh_token_cookie
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token이 없습니다.")
    try:
        subject_id, role, jti = decode_refresh_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않거나 만료된 refresh token입니다.")

    # [수정] 예전엔 session.get()으로 읽어서 revoked 여부를 확인한 다음 따로 True로
    # 갱신하는 2단계였는데, 같은 refresh_token으로 동시에 두 요청이 들어오면 둘 다
    # revoked=False를 읽고 둘 다 회전에 성공하는 레이스가 있었다(순차적인 재사용 차단
    # 자체는 되지만 동시 요청에는 취약). UPDATE ... WHERE revoked=false를 원자적으로
    # 실행해서, 이 요청이 실제로 false -> true로 바꾼 행이 있는지(rowcount)로 판단한다.
    result = session.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti)
        .where(RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    if result.rowcount == 0:
        session.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이미 사용되었거나 무효화된 refresh token입니다.")
    session.commit()

    model = Caregiver if role == "caregiver" else Patient
    subject = session.get(model, subject_id)
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증에 실패했습니다.")
    # [2026-07-15 추가, PR #48 팀원 리뷰 반영 — HIGH] 탈퇴 후에도 refresh_token으로 새
    # access_token을 계속 발급받을 수 있었다 — get_current_actor 등과 동일하게 여기서도 막는다.
    if subject.deactivated_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "탈퇴 처리된 계정입니다.")

    relation_type = subject.relation_type if role == "caregiver" else None
    return _issue_login_response(response, subject_id, role, subject.name, session, relation_type=relation_type)


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
    """임시번호를 확인하고, 맞으면 confirm 전용 reset_token을 발급한다.

    [2026-07-15 추가, PR #48 팀원 리뷰 반영 — CRITICAL] 이전에는 시도 횟수 제한이 전혀
    없어서 6자리 코드를 자동화된 요청으로 브루트포스할 수 있었다(10분 만료 안에 최대
    100만 가지). 이제 계정당 활성 코드 하나를 기준으로 시도 횟수를 세고,
    MAX_RESET_CODE_VERIFY_ATTEMPTS를 넘으면 그 코드를 무효화한다(다시 요청해야 함)."""
    account = _find_by_identifier(session, Caregiver, payload.identifier)
    subject_type = "caregiver"
    if not account:
        account = _find_by_identifier(session, Patient, payload.identifier)
        subject_type = "patient"

    generic_error = HTTPException(status.HTTP_400_BAD_REQUEST, "인증코드가 올바르지 않거나 만료되었습니다.")
    if not account:
        raise generic_error

    now = datetime.now()
    active_code = session.exec(
        select(PasswordResetCode)
        .where(PasswordResetCode.subject_type == subject_type)
        .where(PasswordResetCode.subject_id == account.id)
        .where(PasswordResetCode.used_at.is_(None))
        .where(PasswordResetCode.expires_at > now)
        .order_by(PasswordResetCode.created_at.desc())
    ).first()
    if not active_code:
        raise generic_error

    if active_code.attempts >= MAX_RESET_CODE_VERIFY_ATTEMPTS:
        active_code.used_at = now  # 시도 횟수 초과 — 코드를 무효화(브루트포스 중단, 새로 요청해야 함)
        session.add(active_code)
        session.commit()
        raise generic_error

    active_code.attempts += 1
    session.add(active_code)
    session.commit()

    if active_code.code_hash != hash_reset_code(payload.code):
        raise generic_error

    active_code.used_at = now
    session.add(active_code)
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
