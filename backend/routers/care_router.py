"""
care_router.py — 담당: 박소정 [7/7 신규]

Figma에만 있고 백엔드가 없던 3개 기능을 여기 모았습니다:
1. 자가진단 결과 저장 (Check.tsx / AssessmentPage)
2. 보호자 초대 시스템 — 토큰 발급 → 수락/거절 (CaregiverPage / InvitePage)
3. 알림 설정 저장 (NotificationPage)

[7/13] issue #21(인가) — patient_id 기반 엔드포인트는 `Depends(get_current_actor)` +
`require_actor_patient_access`로 보호합니다(보호자면 연결된 환자인지, 환자 본인이면
자기 자신인지 확인). 초대 링크 열람/수락/거절(get/accept/reject)만 예외 — 계정이
없는 사람이 링크만 갖고 처리해야 하는 게 기능의 전제라 인증 없이 그대로 둡니다.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Literal, Optional

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from core.security import hash_token, normalize_phone
from fastapi import APIRouter, Depends, HTTPException
from models import (
    Caregiver,
    CaregiverPatient,
    CareLevelAssessment,
    Invitation,
    NotificationSetting,
    Patient,
)
from pydantic import BaseModel
from sqlmodel import Session, select

INVITATION_EXPIRE_DAYS = 7

router = APIRouter(tags=["Care"])


# ══════════════════════════════════════════
# 1. 자가진단 (Assessment)
# ══════════════════════════════════════════
class AssessmentCreate(BaseModel):
    patient_id: int
    cognitive_level: str = "normal"  # normal / mild / severe
    mobility_level: str = "normal"
    vision_level: str = "normal"
    medication_awareness: bool = True
    medication_willingness: bool = True


def _compute_care_level(payload: AssessmentCreate) -> tuple[str, str]:
    """AssessmentPage.tsx의 computeResult()와 동일한 판정 로직"""
    levels = [payload.cognitive_level, payload.mobility_level, payload.vision_level]
    severe = "severe" in levels
    mild = "mild" in levels

    if severe or not payload.medication_awareness or not payload.medication_willingness:
        reason = (
            "인지·거동·시력 중 하나 이상이 심각 단계입니다."
            if severe
            else "복약 의지 또는 인지 부재로 외부 지원이 필요합니다."
        )
        return "third_party_needed", reason
    if mild:
        return "guardian_check", "일부 기능이 경미하게 저하되어 있어 보호자의 정기적인 확인이 권장됩니다."
    return "independent", "모든 항목이 정상 범위이며 복약 의지도 충분합니다."


@router.post("/assessments", response_model=CareLevelAssessment)
def create_assessment(
    payload: AssessmentCreate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[7/13] Check.tsx는 환자 본인 가입 직후(SignUp.tsx가 이제 가입 성공 시 바로
    로그인해 토큰을 받음, issue #28) 호출되므로 이 시점부터 인증 가능."""
    require_actor_patient_access(payload.patient_id, actor, session)

    care_level, reason = _compute_care_level(payload)
    assessment = CareLevelAssessment(
        **payload.model_dump(),
        care_level=care_level,
        reason=reason,
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return assessment


@router.get("/assessments/latest", response_model=Optional[CareLevelAssessment])
def get_latest_assessment(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    require_actor_patient_access(patient_id, actor, session)
    return session.exec(
        select(CareLevelAssessment)
        .where(CareLevelAssessment.patient_id == patient_id)
        .order_by(CareLevelAssessment.evaluated_at.desc())
    ).first()


# ══════════════════════════════════════════
# 2. 보호자 초대 (Invitation)
# ══════════════════════════════════════════
class InvitationCreate(BaseModel):
    patient_id: int
    # Connect.tsx의 보호자 초대 UI에서 실제로 선택 가능한 4개 값만 허용한다.
    # 직접 가입(CaregiverCreate)은 guardian/organization 흐름이고, 초대는 현장 돌봄 관계라
    # caregiver/life_support_worker/social_worker까지 별도로 허용한다.
    relation_type: Literal["guardian", "caregiver", "life_support_worker", "social_worker"] = "guardian"
    invited_phone: str | None = None
    inviter_caregiver_id: int | None = None


class InvitationAccept(BaseModel):
    caregiver_name: str
    caregiver_id: int | None = None  # 기존 보호자면 전달, 신규면 None
    phone: str | None = None  # [2026-07-15] invited_phone이 지정된 초대는 이 값과 일치해야 수락 가능(REQ-003)


class InvitationPublic(BaseModel):
    """token_hash/invited_phone_encrypted는 API 응답에 노출하지 않기 위한 응답 전용 모델"""
    id: int
    patient_id: int
    inviter_caregiver_id: int | None = None
    relation_type: str
    invited_phone: str | None = None
    status: str
    created_at: datetime
    accepted_at: datetime | None = None
    expires_at: datetime | None = None


def _get_invitation_by_token(session: Session, token: str) -> Invitation:
    invitation = session.exec(select(Invitation).where(Invitation.token_hash == hash_token(token))).first()
    if not invitation:
        raise HTTPException(404, "유효하지 않은 초대예요")
    if invitation.status == "pending" and invitation.is_expired:
        invitation.status = "expired"
        session.add(invitation)
        session.commit()
    return invitation


@router.post("/invitations")
def create_invitation(
    payload: InvitationCreate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(payload.patient_id, actor, session)

    token = secrets.token_urlsafe(8)
    invitation = Invitation(
        patient_id=payload.patient_id,
        relation_type=payload.relation_type,
        inviter_caregiver_id=payload.inviter_caregiver_id,
        token_hash=hash_token(token),
        expires_at=datetime.now() + timedelta(days=INVITATION_EXPIRE_DAYS),
    )
    invitation.invited_phone = payload.invited_phone
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return {"token": token, "invite_url": f"/invite/{token}"}


@router.get("/invitations/{token}")
def get_invitation(token: str, session: Session = Depends(get_session)):
    """InvitePage — 초대 링크 열었을 때 보여줄 정보"""
    invitation = _get_invitation_by_token(session, token)

    patient = session.get(Patient, invitation.patient_id)
    inviter = (
        session.get(Caregiver, invitation.inviter_caregiver_id)
        if invitation.inviter_caregiver_id
        else None
    )

    return {
        "status": invitation.status,
        "relation_type": invitation.relation_type,
        "patient_name": patient.name if patient else "알 수 없음",
        "inviter_name": inviter.name if inviter else None,
        "phone_verification_required": bool(invitation.invited_phone),
    }


@router.post("/invitations/{token}/accept")
def accept_invitation(token: str, payload: InvitationAccept, session: Session = Depends(get_session)):
    invitation = _get_invitation_by_token(session, token)
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")

    # [2026-07-15] 초대가 특정 전화번호를 지정했다면, 수락자가 그 번호의 소유자인지 확인
    # (REQ-003) — 안 그러면 초대 URL만 탈취해도 본인 인증 없이 보호자-환자 관계가 생김.
    if invitation.invited_phone:
        if not payload.phone or normalize_phone(payload.phone) != normalize_phone(invitation.invited_phone):
            raise HTTPException(403, "초대받은 전화번호와 일치하지 않아요.")

    if payload.caregiver_id:
        caregiver = session.get(Caregiver, payload.caregiver_id)
        if not caregiver:
            raise HTTPException(404, "해당 보호자를 찾을 수 없어요")
    else:
        # [7/9] name은 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 — 생성 후 대입.
        # [7/13] commit 대신 flush — caregiver.id만 미리 확정하고, 아래 CaregiverPatient
        # 연결·invitation 상태 변경과 한 트랜잭션으로 묶어 마지막에 한 번에 커밋한다.
        # (이전엔 여기서 바로 commit해서, 이 직후 장애가 나면 CaregiverPatient 연결도
        # 없고 invitation도 pending인 채로 Caregiver row만 영구히 남는 문제가 있었음)
        caregiver = Caregiver(relation_type=invitation.relation_type)
        caregiver.name = payload.caregiver_name
        session.add(caregiver)
        session.flush()
        session.refresh(caregiver)

    existing_link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver.id)
        .where(CaregiverPatient.patient_id == invitation.patient_id)
    ).first()
    if not existing_link:
        session.add(CaregiverPatient(caregiver_id=caregiver.id, patient_id=invitation.patient_id))

    invitation.status = "accepted"
    invitation.accepted_at = datetime.now()
    session.add(invitation)
    session.commit()

    return {"caregiver_id": caregiver.id, "patient_id": invitation.patient_id, "status": "accepted"}


@router.post("/invitations/{token}/reject")
def reject_invitation(token: str, session: Session = Depends(get_session)):
    invitation = _get_invitation_by_token(session, token)
    invitation.status = "rejected"
    session.add(invitation)
    session.commit()
    return {"status": "rejected"}


@router.get("/patients/{patient_id}/invitations", response_model=list[InvitationPublic])
def list_invitations(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """CaregiverPage — 환자의 초대 발송 이력 (대기중/승인됨 목록)

    [2026-07-15] response_model=InvitationPublic으로 token_hash를 응답에서 제외 — 예전엔
    token 원문이 이 목록 응답에 그대로 노출돼 재사용될 수 있었다."""
    require_actor_patient_access(patient_id, actor, session)
    return session.exec(
        select(Invitation)
        .where(Invitation.patient_id == patient_id)
        .order_by(Invitation.created_at.desc())
    ).all()


# ══════════════════════════════════════════
# 3. 알림 설정 (NotificationSetting)
# ══════════════════════════════════════════
class NotificationUpdate(BaseModel):
    medication_reminder_enabled: bool | None = None
    care_alert_enabled: bool | None = None
    all_push_enabled: bool | None = None
    chatbot_name: str | None = None


@router.get("/notification-settings", response_model=NotificationSetting)
def get_notification_settings(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    require_actor_patient_access(patient_id, actor, session)
    setting = session.get(NotificationSetting, patient_id)
    if not setting:
        if not session.get(Patient, patient_id):
            raise HTTPException(404, "해당 환자를 찾을 수 없어요")
        # 저장하지 않고 기본값만 반환 — 실제 저장은 PUT 호출 시 수행
        return NotificationSetting(patient_id=patient_id)
    return setting


@router.put("/notification-settings", response_model=NotificationSetting)
def update_notification_settings(
    patient_id: int,
    payload: NotificationUpdate,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    require_actor_patient_access(patient_id, actor, session)
    setting = session.get(NotificationSetting, patient_id)
    if not setting:
        setting = NotificationSetting(patient_id=patient_id)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(setting, key, value)
    setting.updated_at = datetime.now()

    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting
