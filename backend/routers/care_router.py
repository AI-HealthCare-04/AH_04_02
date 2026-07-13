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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from dependencies import Actor, get_current_actor, require_actor_patient_access
from models import (
    CareLevelAssessment,
    Caregiver,
    CaregiverPatient,
    Invitation,
    NotificationSetting,
    Patient,
)

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
    relation_type: str = "guardian"
    invited_phone: str | None = None
    inviter_caregiver_id: int | None = None


class InvitationAccept(BaseModel):
    caregiver_name: str
    caregiver_id: int | None = None  # 기존 보호자면 전달, 신규면 None


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
        invited_phone=payload.invited_phone,
        inviter_caregiver_id=payload.inviter_caregiver_id,
        token=token,
    )
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return {"token": token, "invite_url": f"/invite/{token}"}


@router.get("/invitations/{token}")
def get_invitation(token: str, session: Session = Depends(get_session)):
    """InvitePage — 초대 링크 열었을 때 보여줄 정보"""
    invitation = session.exec(select(Invitation).where(Invitation.token == token)).first()
    if not invitation:
        raise HTTPException(404, "유효하지 않은 초대예요")

    patient = session.get(Patient, invitation.patient_id)
    inviter = (
        session.get(Caregiver, invitation.inviter_caregiver_id)
        if invitation.inviter_caregiver_id
        else None
    )

    return {
        "token": invitation.token,
        "status": invitation.status,
        "relation_type": invitation.relation_type,
        "patient_name": patient.name if patient else "알 수 없음",
        "inviter_name": inviter.name if inviter else None,
    }


@router.post("/invitations/{token}/accept")
def accept_invitation(token: str, payload: InvitationAccept, session: Session = Depends(get_session)):
    invitation = session.exec(select(Invitation).where(Invitation.token == token)).first()
    if not invitation:
        raise HTTPException(404, "유효하지 않은 초대예요")
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")

    if payload.caregiver_id:
        caregiver = session.get(Caregiver, payload.caregiver_id)
        if not caregiver:
            raise HTTPException(404, "해당 보호자를 찾을 수 없어요")
    else:
        # [7/9] name은 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 — 생성 후 대입.
        caregiver = Caregiver(relation_type=invitation.relation_type)
        caregiver.name = payload.caregiver_name
        session.add(caregiver)
        session.commit()
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
    invitation = session.exec(select(Invitation).where(Invitation.token == token)).first()
    if not invitation:
        raise HTTPException(404, "유효하지 않은 초대예요")
    invitation.status = "rejected"
    session.add(invitation)
    session.commit()
    return {"status": "rejected"}


@router.get("/patients/{patient_id}/invitations")
def list_invitations(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """CaregiverPage — 환자의 초대 발송 이력 (대기중/승인됨 목록)"""
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


@router.get("/notification-settings", response_model=NotificationSetting)
def get_notification_settings(
    patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    require_actor_patient_access(patient_id, actor, session)
    setting = session.get(NotificationSetting, patient_id)
    if not setting:
        if not session.get(Patient, patient_id):
            raise HTTPException(404, "해당 환자를 찾을 수 없어요")
        # [순현님 수정 반영, 역할분담 26번] GET은 조회 전용 — 저장하지 않고 기본값만 반환.
        # 실제 저장은 PUT 호출 시 수행 (REST 컨벤션 위반 수정).
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
