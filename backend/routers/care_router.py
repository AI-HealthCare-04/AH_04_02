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
from typing import Literal

from core.database import get_session
from core.dependencies import (
    Actor,
    get_current_actor,
    get_current_caregiver,
    get_current_caregiver_optional,
    require_actor_patient_access,
)
from core.security import hash_phone, hash_token, normalize_phone
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

from routers.monitoring_router import PatientCreate, _register_patient

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


@router.get("/assessments/latest", response_model=CareLevelAssessment | None)
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
    patient_id: int | None = None  # patient 방향은 수락 전까지 환자 계정이 없어 항상 None
    relation_type: Literal["patient", "guardian", "caregiver", "life_support_worker", "social_worker"]
    invited_phone: str | None = None
    inviter_caregiver_id: int | None = None


class InvitationAccept(BaseModel):
    # relation_type != "patient" (환자→보호자 초대) 수락용 — 수락자가 보호자 본인
    caregiver_name: str | None = None
    caregiver_id: int | None = None  # 기존 보호자면 전달, 신규면 None
    phone: str | None = None  # [2026-07-15] invited_phone이 지정된 초대는 이 값과 일치해야 수락 가능(REQ-003)
    # relation_type == "patient" (보호자→환자 초대) 수락용 — 수락자가 실제 환자 계정을 만든다
    patient_name: str | None = None
    patient_email: str | None = None
    patient_password: str | None = None
    patient_phone: str | None = None


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
    """초대 생성.

    - relation_type="patient": 보호자/지원인력 → 아직 계정이 없는 환자 초대
    - 그 외 relation_type: 환자 → 보호자/지원인력 초대
    """
    if payload.relation_type == "patient":
        if payload.inviter_caregiver_id is None:
            raise HTTPException(400, "초대하는 보호자 정보가 필요해요.")
        role, subject = actor
        if role != "caregiver" or subject.id != payload.inviter_caregiver_id:
            raise HTTPException(403, "본인 계정으로만 환자를 초대할 수 있어요.")
        patient_id = None
        inviter_caregiver_id = payload.inviter_caregiver_id
    else:
        if payload.patient_id is None:
            raise HTTPException(400, "환자 정보가 필요해요.")
        require_actor_patient_access(payload.patient_id, actor, session)
        patient_id = payload.patient_id
        inviter_caregiver_id = None

    token = secrets.token_urlsafe(8)
    invitation = Invitation(
        patient_id=patient_id,
        relation_type=payload.relation_type,
        inviter_caregiver_id=inviter_caregiver_id,
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

    patient = session.get(Patient, invitation.patient_id) if invitation.patient_id else None
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
        # [2026-07-22 추가] InviteAccept.tsx가 "초대 만료" 표시에 씀 (Figma 목업 참고)
        "expires_at": invitation.expires_at,
    }


@router.post("/invitations/{token}/accept")
def accept_invitation(
    token: str,
    payload: InvitationAccept,
    session: Session = Depends(get_session),
    actor: Caregiver | None = Depends(get_current_caregiver_optional),
):
    """[2026-07-22 수정 — HIGH, 팀원 리뷰(fkmc10101-hub) 지적 반영] 이 엔드포인트는 계정이
    없는 사람도 써야 해서(인증 없이 새 보호자 계정을 만드는 경로) 여전히 로그인을 강제하지
    않는다 — 다만 `payload.caregiver_id`(기존 로그인 계정으로 그대로 수락)를 아무 검증 없이
    믿으면, 초대 토큰만 가진 누구나 임의의 caregiver_id를 넣어 그 계정을 남의 환자에
    연결시킬 수 있었다(실제로 재현 — 인증 전혀 없이 성공). 이제 `caregiver_id`가 오면
    `get_current_caregiver_optional`로 실제 로그인된 그 계정인지 검증하고, 아니면 거부한다."""
    # [알려진 한계] 이 pending 체크와 아래 최종 commit 사이에 행 잠금이 없어, 같은 토큰으로
    # 동시에 두 번 수락 요청이 오면(예: 링크를 두 기기에서 거의 동시에 열기) 둘 다 이 체크를
    # 통과해 patient 분기에서 계정이 2개 생길 수 있다 — 이 앱 규모(소규모 팀, 낮은 동시성)에선
    # 발생 확률이 낮아 SELECT ... FOR UPDATE 도입은 보류, 재발 시 재검토.
    invitation = _get_invitation_by_token(session, token)
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")

    # [2026-07-15] 초대가 특정 전화번호를 지정했다면, 수락자가 그 번호의 소유자인지 확인
    # (REQ-003) — 안 그러면 초대 URL만 탈취해도 본인 인증 없이 관계가 생긴다. relation_type
    # 종류와 무관하게 모든 수락 경로에 공통으로 적용해야 한다(2026-07-20 수정 — patient 분기가
    # 이 체크보다 먼저 return해서 우회되고 있었음).
    if invitation.invited_phone:
        provided_phone = payload.patient_phone if invitation.relation_type == "patient" else payload.phone
        if not provided_phone or normalize_phone(provided_phone) != normalize_phone(invitation.invited_phone):
            raise HTTPException(403, "초대받은 전화번호와 일치하지 않아요.")

    if invitation.relation_type == "patient":
        # 보호자→환자 초대 수락 = 환자 본인이 실제 로그인 가능한 계정을 만든다.
        if not payload.patient_name:
            raise HTTPException(400, "환자 이름을 입력해 주세요.")
        new_patient = _register_patient(
            PatientCreate(
                name=payload.patient_name,
                email=payload.patient_email,
                password=payload.patient_password,
                phone=payload.patient_phone,
            ),
            session,
        )
        invitation.patient_id = new_patient.id
        if invitation.inviter_caregiver_id:
            session.add(
                CaregiverPatient(
                    caregiver_id=invitation.inviter_caregiver_id, patient_id=new_patient.id
                )
            )
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now()
        session.add(invitation)
        session.commit()
        return {"patient_id": new_patient.id, "status": "accepted"}

    if payload.caregiver_id:
        # [2026-07-22 수정 — HIGH] payload.caregiver_id를 그대로 신뢰하지 않는다 — 실제로
        # 로그인된 보호자(actor)가 그 id 본인일 때만 허용한다.
        if actor is None or actor.id != payload.caregiver_id:
            raise HTTPException(403, "본인 계정으로 로그인한 상태에서만 기존 계정으로 수락할 수 있어요.")
        caregiver = actor
    else:
        # [7/9] name은 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 — 생성 후 대입.
        # [7/13] commit 대신 flush — caregiver.id만 미리 확정하고, 아래 CaregiverPatient
        # 연결·invitation 상태 변경과 한 트랜잭션으로 묶어 마지막에 한 번에 커밋한다.
        # (이전엔 여기서 바로 commit해서, 이 직후 장애가 나면 CaregiverPatient 연결도
        # 없고 invitation도 pending인 채로 Caregiver row만 영구히 남는 문제가 있었음)
        if not payload.caregiver_name:
            raise HTTPException(400, "본인 이름을 입력해 주세요.")
        caregiver = Caregiver(relation_type=invitation.relation_type)
        caregiver.name = payload.caregiver_name
        session.add(caregiver)
        session.flush()
        session.refresh(caregiver)

    _link_caregiver_to_invitation(session, invitation, caregiver)
    return {"caregiver_id": caregiver.id, "patient_id": invitation.patient_id, "status": "accepted"}


def _link_caregiver_to_invitation(session: Session, invitation: Invitation, caregiver: Caregiver) -> None:
    """환자→보호자 초대 수락 공통 로직 — 토큰 기반 accept_invitation과 로그인 기반
    accept_invitation_as_caregiver(아래) 양쪽에서 재사용한다."""
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


@router.post("/invitations/{token}/reject")
def reject_invitation(token: str, session: Session = Depends(get_session)):
    invitation = _get_invitation_by_token(session, token)
    invitation.status = "rejected"
    session.add(invitation)
    session.commit()
    return {"status": "rejected"}


@router.delete("/invitations/{invitation_id}")
def delete_pending_invitation(
    invitation_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """보낸 대기중 초대 삭제.

    초대 링크를 이미 전달했을 수 있으므로 행을 지우지 않고 cancelled로 바꿔 토큰 수락도 막는다.
    """
    invitation = session.get(Invitation, invitation_id)
    if not invitation:
        raise HTTPException(404, "초대를 찾을 수 없어요")
    if invitation.status == "pending" and invitation.is_expired:
        invitation.status = "expired"
        session.add(invitation)
        session.commit()
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")

    if invitation.relation_type == "patient":
        role, subject = actor
        if role != "caregiver" or subject.id != invitation.inviter_caregiver_id:
            raise HTTPException(403, "본인이 보낸 초대만 삭제할 수 있어요")
    else:
        if invitation.patient_id is None:
            raise HTTPException(400, "환자 정보가 없는 초대예요")
        require_actor_patient_access(invitation.patient_id, actor, session)

    invitation.status = "cancelled"
    session.add(invitation)
    session.commit()
    return {"deleted": invitation_id, "status": "cancelled"}


@router.get("/caregivers/{caregiver_id}/pending-invitations")
def list_pending_invitations_for_caregiver(
    caregiver_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """[2026-07-22 추가] "받은 초대" — 환자가 이 보호자/기관의 전화번호를 지정해서 초대를
    보내면(invited_phone), 링크를 열지 않고도 로그인만 하면 여기서 바로 볼 수 있다.
    invited_phone_hash로 매칭하므로 가입 시 등록한 전화번호와 초대에 적힌 전화번호가
    정확히 같아야 뜬다 — 전화번호를 지정하지 않은(누구나 열 수 있는 공유용) 초대는
    애초에 "누구에게 온" 초대인지 알 수 없어 여기 안 뜨고, 링크로만 수락 가능하다.
    """
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "본인 계정의 초대만 볼 수 있어요")
    if not caregiver.phone:
        return []

    invitations = session.exec(
        select(Invitation)
        .where(Invitation.invited_phone_hash == hash_phone(caregiver.phone))
        .where(Invitation.relation_type != "patient")
        .where(Invitation.status == "pending")
        .order_by(Invitation.created_at.desc())
    ).all()

    result = []
    for inv in invitations:
        if inv.is_expired:
            inv.status = "expired"
            session.add(inv)
            continue
        patient = session.get(Patient, inv.patient_id) if inv.patient_id else None
        result.append(
            {
                "id": inv.id,
                "relation_type": inv.relation_type,
                "patient_name": patient.name if patient else "알 수 없음",
                "created_at": inv.created_at,
                "expires_at": inv.expires_at,
            }
        )
    session.commit()
    return result


def _require_own_matching_invitation(invitation_id: int, caregiver: Caregiver, session: Session) -> Invitation:
    """받은 초대함(위 목록)에서 토큰 없이 수락/거절할 때 공용 검증 — 초대가 실제로 이
    보호자에게 온 것인지(전화번호 일치) 확인한다. 목록에 뜬 것만 골라 액션을 호출하는
    게 정상 흐름이지만, id를 직접 조작해서 다른 사람 초대를 건드리는 걸 막기 위한 서버측
    재검증(REQ-003과 동일한 보장을 토큰 없이 재현)이다."""
    invitation = session.get(Invitation, invitation_id)
    if not invitation:
        raise HTTPException(404, "초대를 찾을 수 없어요")
    if invitation.status == "pending" and invitation.is_expired:
        invitation.status = "expired"
        session.add(invitation)
        session.commit()
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")
    if invitation.relation_type == "patient":
        raise HTTPException(400, "이 방식으로는 환자 초대를 수락할 수 없어요")
    if (
        not caregiver.phone
        or not invitation.invited_phone
        or normalize_phone(caregiver.phone) != normalize_phone(invitation.invited_phone)
    ):
        raise HTTPException(403, "본인에게 온 초대가 아니에요")
    return invitation


@router.post("/invitations/{invitation_id}/accept-as-caregiver")
def accept_invitation_as_caregiver(
    invitation_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """[2026-07-22 추가] 링크 없이 "받은 초대" 목록에서 바로 수락 — 이미 로그인해 있는
    계정을 그대로 사용한다(토큰 기반 accept_invitation처럼 새 보호자 계정을 만들지 않음)."""
    invitation = _require_own_matching_invitation(invitation_id, caregiver, session)
    _link_caregiver_to_invitation(session, invitation, caregiver)
    return {"caregiver_id": caregiver.id, "patient_id": invitation.patient_id, "status": "accepted"}


@router.post("/invitations/{invitation_id}/reject-as-caregiver")
def reject_invitation_as_caregiver(
    invitation_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """[2026-07-22 추가] accept_invitation_as_caregiver와 동일한 방식의 거절."""
    invitation = _require_own_matching_invitation(invitation_id, caregiver, session)
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
# 3. 돌봄관계 해제 (Trust Relation Dissolution, REQ-004)
# ══════════════════════════════════════════
class TrustRevocationResult(BaseModel):
    trust_id: int
    patient_id: int
    caregiver_id: int
    status: str
    revoked_at: datetime | None = None
    revocation_requested_by: int | None = None
    should_alert_now: bool = False  # REQ-007a: 즉시 해제 후 마지막 연결이면 True


@router.delete("/trust/relations/{trust_id}", response_model=TrustRevocationResult)
def dissolve_trust_relation(
    trust_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[REQ-004] 보호자-환자 돌봄관계 해제 요청.

    care_level=independent/guardian_check → 즉시 revoked.
    care_level=third_party_needed → 제3자 승인 필요, revocation_pending으로 전환.
    평가 이력이 없으면 independent로 간주해 즉시 해제한다."""
    link = session.get(CaregiverPatient, trust_id)
    if not link:
        raise HTTPException(404, "존재하지 않는 연결이에요")

    require_actor_patient_access(link.patient_id, actor, session)

    if link.status != "active":
        raise HTTPException(409, f"이미 {link.status} 상태인 연결이에요")

    assessment = session.exec(
        select(CareLevelAssessment)
        .where(CareLevelAssessment.patient_id == link.patient_id)
        .order_by(CareLevelAssessment.evaluated_at.desc())
    ).first()

    care_level = assessment.care_level if assessment else "independent"
    role, subject = actor

    if care_level in ("independent", "guardian_check"):
        link.status = "revoked"
        link.revoked_at = datetime.now()
    else:  # third_party_needed — 요청자 role·id를 항상 기록 (환자/보호자 무관)
        link.status = "revocation_pending"
        link.revocation_requested_by = subject.id
        link.requested_by_role = role  # "caregiver" | "patient"

    session.add(link)
    session.commit()
    session.refresh(link)

    # 즉시 해제(revoked)일 때만 마지막 연결 여부 확인 — pending은 아직 active 유지
    should_alert = False
    if link.status == "revoked":
        remaining_active = session.exec(
            select(CaregiverPatient)
            .where(CaregiverPatient.patient_id == link.patient_id)
            .where(CaregiverPatient.status == "active")
        ).all()
        patient = session.get(Patient, link.patient_id)
        should_alert = (not remaining_active) and bool(patient) and _should_alert_now(patient)

    return TrustRevocationResult(
        trust_id=link.id,
        patient_id=link.patient_id,
        caregiver_id=link.caregiver_id,
        status=link.status,
        revoked_at=link.revoked_at,
        revocation_requested_by=link.revocation_requested_by,
        should_alert_now=should_alert,
    )


class RevocationApprovalRequest(BaseModel):
    approve: bool


class RevocationApprovalResult(BaseModel):
    trust_id: int
    patient_id: int
    caregiver_id: int
    status: str
    revoked_at: datetime | None = None
    should_alert_now: bool = False


def _should_alert_now(patient: Patient) -> bool:
    """REQ-007a: dismissed_at이 None이거나 30일이 지났으면 안내를 표시해야 한다."""
    if patient.caregiver_alert_dismissed_at is None:
        return True
    return patient.caregiver_alert_dismissed_at + timedelta(days=30) < datetime.now()


@router.post("/trust/relations/{trust_id}/revocation-approval", response_model=RevocationApprovalResult)
def approve_revocation(
    trust_id: int,
    payload: RevocationApprovalRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[REQ-004] third_party_needed 환자의 해제 승인/거부.

    approve=True  → status='revoked', revoked_at 기록.
                    남은 active 연결이 0명이면 should_alert_now=True 반환(REQ-007a).
    approve=False → status='active'로 복원(해제 거부)."""
    link = session.get(CaregiverPatient, trust_id)
    if not link:
        raise HTTPException(404, "존재하지 않는 연결이에요")

    require_actor_patient_access(link.patient_id, actor, session)

    if link.status != "revocation_pending":
        raise HTTPException(409, f"승인 대상이 아닌 연결이에요 (현재 상태: {link.status})")

    role, subject = actor
    # 요청자 본인은 role과 무관하게 승인 불가 (caregiver가 요청해도, patient가 요청해도)
    if link.revocation_requested_by == subject.id and link.requested_by_role == role:
        raise HTTPException(403, "본인이 요청한 해제는 본인이 승인할 수 없어요")

    if payload.approve:
        link.status = "revoked"
        link.revoked_at = datetime.now()
        # autoflush가 link 변경을 DB에 반영한 뒤 조회하므로 현재 link는 포함되지 않음
        remaining_active = session.exec(
            select(CaregiverPatient)
            .where(CaregiverPatient.patient_id == link.patient_id)
            .where(CaregiverPatient.status == "active")
        ).all()
    else:
        link.status = "active"
        link.revocation_requested_by = None
        link.requested_by_role = None
        remaining_active = [True]  # 복원됐으므로 최소 1개 active

    session.add(link)
    session.commit()
    session.refresh(link)

    patient = session.get(Patient, link.patient_id)
    should_alert = (not remaining_active) and bool(patient) and _should_alert_now(patient)

    return RevocationApprovalResult(
        trust_id=link.id,
        patient_id=link.patient_id,
        caregiver_id=link.caregiver_id,
        status=link.status,
        revoked_at=link.revoked_at,
        should_alert_now=should_alert,
    )


class DismissAlertResult(BaseModel):
    patient_id: int
    caregiver_alert_dismissed_at: datetime
    next_alert_at: datetime  # dismissed_at + 30일


@router.post("/trust/relations/{trust_id}/dismiss-alert", response_model=DismissAlertResult)
def dismiss_caregiver_alert(
    trust_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[REQ-007a] 보호자 연결 권유 안내 닫기 — 30일간 재표시 억제.

    사용자가 "닫기"를 누르면 Patient.caregiver_alert_dismissed_at을 현재 시각으로 갱신한다.
    _should_alert_now()는 dismissed_at + 30일이 지나야 다시 True를 반환한다."""
    link = session.get(CaregiverPatient, trust_id)
    if not link:
        raise HTTPException(404, "존재하지 않는 연결이에요")

    require_actor_patient_access(link.patient_id, actor, session)

    patient = session.get(Patient, link.patient_id)
    if not patient:
        raise HTTPException(404, "환자 정보를 찾을 수 없어요")

    patient.caregiver_alert_dismissed_at = datetime.now()
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dismissed_at = patient.caregiver_alert_dismissed_at
    return DismissAlertResult(
        patient_id=patient.id,
        caregiver_alert_dismissed_at=dismissed_at,
        next_alert_at=dismissed_at + timedelta(days=30),
    )


# ══════════════════════════════════════════
# 4. 알림 설정 (NotificationSetting)
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
