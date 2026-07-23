"""
dependencies.py — 로그인한 사용자(보호자/환자)를 구하는 공용 의존성 (담당: 박소정, 환자 로그인 확장: 김영혜)

라우터에서 이렇게 씁니다:
    current_caregiver: Caregiver = Depends(get_current_caregiver)
    current_patient: Patient = Depends(get_current_patient)  # [7/9 추가]
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import Caregiver, CaregiverPatient, Patient
from sqlmodel import Session, select

from core.auth import decode_token
from core.database import get_session

security = HTTPBearer()
# [2026-07-22 추가, 팀원 리뷰 반영 — HIGH] auto_error=False — Authorization 헤더가 아예
# 없어도 401을 던지지 않고 credential만 None으로 넘긴다. care_router.py의
# POST /invitations/{token}/accept처럼 "완전 비인증도 허용하되, 로그인된 상태면 그 계정을
# 검증에 쓰는" 선택적 인증이 필요한 공개 엔드포인트 전용.
_optional_security = HTTPBearer(auto_error=False)


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
    # [2026-07-15 추가, PR #48 팀원 리뷰 반영 — HIGH] deactivated_at 체크가 login()에만
    # 있어서, 탈퇴(POST /auth/withdraw) 후에도 이미 발급된 access_token은 만료 전까지
    # 계속 통했다 — 매 요청마다 DB에서 다시 확인하는 이 지점에서 막아야 실제로 끊긴다.
    if caregiver.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="탈퇴 처리된 계정입니다.")
    return caregiver


def get_current_caregiver_optional(
    credential: HTTPAuthorizationCredentials | None = Depends(_optional_security),
    session: Session = Depends(get_session),
) -> Caregiver | None:
    """[2026-07-22 추가, 팀원 리뷰 반영 — HIGH] get_current_caregiver의 "선택적" 버전 —
    Authorization 헤더가 없으면 조용히 None을 반환한다(완전 비인증 흐름을 막지 않기 위함).
    토큰이 무효/만료됐으면 여전히 401을 던진다.

    [2026-07-23 수정] role이 "caregiver"가 아닐 때도 이전엔 401을 던졌는데,
    accept_invitation()이 이제 get_current_patient_optional도 같은 요청에 같이 걸어둔다
    (수락자가 보호자일지 환자일지 미리 알 수 없어서) — 환자 토큰으로 요청하면 role
    불일치로 매번 401이 나서 patient_id 검증 로직에 도달하기도 전에 요청이 막혔다. 이제는
    조용히 None을 반환하고, payload.caregiver_id 검증(아래 accept_invitation)이 actor가
    None이면 403으로 거부하므로 보안 목적은 동일하게 유지된다."""
    if credential is None:
        return None
    try:
        subject_id, role = decode_token(credential.credentials, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")
    if role != "caregiver":
        return None

    caregiver = session.get(Caregiver, subject_id)
    if not caregiver:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했습니다.")
    if caregiver.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="탈퇴 처리된 계정입니다.")
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
    if patient.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="탈퇴 처리된 계정입니다.")
    return patient


def get_current_patient_optional(
    credential: HTTPAuthorizationCredentials | None = Depends(_optional_security),
    session: Session = Depends(get_session),
) -> Patient | None:
    """get_current_caregiver_optional의 환자 버전 — care_router.accept_invitation()이
    "보호자→환자 초대"를 이미 로그인된 기존 환자 계정으로 바로 수락할 때, payload.patient_id를
    실제 로그인된 그 계정인지 검증하는 용도로 쓴다.

    [주의] get_current_caregiver_optional과 달리 role이 안 맞으면 401을 던지지 않고 조용히
    None을 반환한다 — accept_invitation()이 이 함수와 get_current_caregiver_optional을 같은
    요청에 동시에 걸어두므로(수락자가 보호자일지 환자일지 미리 알 수 없음), 로그인된 보호자
    토큰으로 요청하면 이 함수 입장에선 "역할이 다른 유효한 토큰"이라 매번 401을 던져
    caregiver_id 검증 로직까지 도달하기 전에 요청 전체가 막혀버린다. 대신 아래 accept_invitation
    쪽에서 `patient_id`가 왔는데 patient_actor가 None이면 403으로 거부하므로 보안 목적은
    동일하게 달성된다."""
    if credential is None:
        return None
    try:
        subject_id, role = decode_token(credential.credentials, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않거나 만료된 토큰입니다.")
    if role != "patient":
        return None

    patient = session.get(Patient, subject_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증에 실패했습니다.")
    if patient.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="탈퇴 처리된 계정입니다.")
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
    if actor.deactivated_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="탈퇴 처리된 계정입니다.")
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
