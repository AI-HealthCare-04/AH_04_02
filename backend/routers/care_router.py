"""
care_router.py — 담당: 박소정 [7/7 신규]

Figma에만 있고 백엔드가 없던 3개 기능을 여기 모았습니다:
1. 자가진단 결과 저장 (Check.tsx / AssessmentPage)
2. 보호자 초대 시스템 — 토큰 발급 → 수락/거절 (CaregiverPage / InvitePage)
3. 알림 설정 저장 (NotificationPage)

로그인이 없어서 "누가 초대를 보냈는지"는 optional로만 기록하고,
수락 시점에 caregiver_id를 body로 받아 연결합니다 (기존 보호자 선택 방식과 동일 패턴).
"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
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
def create_assessment(payload: AssessmentCreate, session: Session = Depends(get_session)):
    if not session.get(Patient, payload.patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

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


@router.get("/assessments/latest", response_model=CareLevelAssessment | None)
def get_latest_assessment(patient_id: int, session: Session = Depends(get_session)):
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
def create_invitation(payload: InvitationCreate, session: Session = Depends(get_session)):
    if not session.get(Patient, payload.patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

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
        caregiver = Caregiver(name=payload.caregiver_name, relation_type=invitation.relation_type)
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
def list_invitations(patient_id: int, session: Session = Depends(get_session)):
    """CaregiverPage — 환자의 초대 발송 이력 (대기중/승인됨 목록)"""
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
def get_notification_settings(patient_id: int, session: Session = Depends(get_session)):
    setting = session.get(NotificationSetting, patient_id)
    if not setting:
        if not session.get(Patient, patient_id):
            raise HTTPException(404, "해당 환자를 찾을 수 없어요")
        # 없으면 기본값으로 하나 만들어서 반환 (첫 방문 시)
        setting = NotificationSetting(patient_id=patient_id)
        session.add(setting)
        session.commit()
        session.refresh(setting)
    return setting


@router.put("/notification-settings", response_model=NotificationSetting)
def update_notification_settings(
    patient_id: int, payload: NotificationUpdate, session: Session = Depends(get_session)
):
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
