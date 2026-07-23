"""
care_router.py — 담당: 박소정 [7/7 신규]

Figma에만 있고 백엔드가 없던 기능을 여기 모았습니다:
1. 보호자 초대 시스템 — 토큰 발급 → 수락/거절 (CaregiverPage / InvitePage)
2. 알림 설정 저장 (NotificationPage)

[2026-07-23 삭제] 자가진단 결과 저장(Check.tsx/AssessmentPage, care_level 판정)은 만드는
화면이 프론트 전체에 없어 항상 비어있던 죽은 기능이라 제거했다 — care_level에 의존하던
돌봄관계 해제 승인 흐름도 함께 정리(아래 "3. 돌봄관계 해제" 참고, 이제 기관 계정 여부로
승인 필요 여부를 판단한다).

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
    get_current_patient_optional,
    require_actor_patient_access,
)
from core.security import hash_phone, hash_token, normalize_phone
from fastapi import APIRouter, Depends, HTTPException
from models import (
    Caregiver,
    CaregiverPatient,
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
# 1. 보호자 초대 (Invitation)
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
    # [2026-07-23 추가] 수락자가 이미 로그인된 기존 환자 계정이면 이 값을 보내 새 계정을
    # 또 만들지 않고 그 계정을 그대로 연결한다(caregiver_id를 재사용하는 위 패턴과 동일).
    patient_id: int | None = None


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
    - 그 외 relation_type: 환자 → 보호자/지원인력 초대(환자 본인 또는 그 환자에 접근 권한이
      있는 보호자도 만들 수 있다 — require_actor_patient_access가 둘 다 허용).
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
    patient_actor: Patient | None = Depends(get_current_patient_optional),
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
        if invitation.relation_type == "patient" and payload.patient_id:
            provided_phone = patient_actor.phone if patient_actor else None
        else:
            provided_phone = payload.patient_phone if invitation.relation_type == "patient" else payload.phone
        if not provided_phone or normalize_phone(provided_phone) != normalize_phone(invitation.invited_phone):
            raise HTTPException(403, "초대받은 전화번호와 일치하지 않아요.")

    if invitation.relation_type == "patient":
        if payload.patient_id:
            # [2026-07-23 추가] 이미 로그인된 환자 계정으로 수락 — 새 계정을 만들지 않고
            # 그 계정을 그대로 이 초대를 보낸 보호자에게 연결한다. caregiver_id 재사용
            # 검증과 동일하게, 실제 로그인된 본인인지부터 확인한다.
            if patient_actor is None or patient_actor.id != payload.patient_id:
                raise HTTPException(403, "본인 계정으로 로그인한 상태에서만 기존 계정으로 수락할 수 있어요.")
            if invitation.inviter_caregiver_id:
                _reactivate_or_create_link(session, invitation.inviter_caregiver_id, patient_actor.id)
            invitation.patient_id = patient_actor.id
            invitation.status = "accepted"
            invitation.accepted_at = datetime.now()
            session.add(invitation)
            session.commit()
            return {"patient_id": patient_actor.id, "status": "accepted"}

        # 보호자→환자 초대 수락(신규) = 환자 본인이 실제 로그인 가능한 계정을 만든다.
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


def _reactivate_or_create_link(session: Session, caregiver_id: int, patient_id: int) -> None:
    """[2026-07-23 추가] 초대 수락으로 caregiver_id-patient_id 연결을 만들 때, 과거에 해제된
    (status="revoked") 연결이 이미 있으면 새 행을 또 만들지 않고 재활성화한다 — 안 그러면
    "이미 연결돼 있다"고 잘못 판단해 재연결이 조용히 스킵되거나, 같은 쌍에 중복 행이 쌓인다."""
    existing_link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == caregiver_id)
        .where(CaregiverPatient.patient_id == patient_id)
    ).first()
    if not existing_link:
        session.add(CaregiverPatient(caregiver_id=caregiver_id, patient_id=patient_id))
        return
    if existing_link.status == "revoked":
        existing_link.status = "active"
        existing_link.revoked_at = None
        existing_link.revocation_requested_by = None
        existing_link.requested_by_role = None
        existing_link.revocation_reason = None
        existing_link.revocation_requested_at = None
        session.add(existing_link)


def _link_caregiver_to_invitation(session: Session, invitation: Invitation, caregiver: Caregiver) -> None:
    """환자→보호자 초대 수락 공통 로직 — 토큰 기반 accept_invitation과 로그인 기반
    accept_invitation_as_caregiver(아래) 양쪽에서 재사용한다."""
    _reactivate_or_create_link(session, caregiver.id, invitation.patient_id)

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


def _hide_unowned_invitation() -> None:
    raise HTTPException(404, "초대를 찾을 수 없어요")


def _require_invitation_delete_owner(invitation: Invitation, actor: Actor, session: Session) -> None:
    """초대 삭제 권한 검증.

    상태 확인보다 먼저 호출해, 권한 없는 사용자가 초대 ID로 처리 상태를 유추하지 못하게 한다.
    """
    role, subject = actor
    if invitation.relation_type == "patient":
        if role != "caregiver" or subject.id != invitation.inviter_caregiver_id:
            _hide_unowned_invitation()
        return

    if invitation.patient_id is None:
        raise HTTPException(400, "환자 정보가 없는 초대예요")
    if role == "patient":
        if subject.id != invitation.patient_id:
            _hide_unowned_invitation()
        return

    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == subject.id)
        .where(CaregiverPatient.patient_id == invitation.patient_id)
        .where(CaregiverPatient.status != "revoked")
    ).first()
    if not link:
        _hide_unowned_invitation()


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
    _require_invitation_delete_owner(invitation, actor, session)

    if invitation.status == "pending" and invitation.is_expired:
        invitation.status = "expired"
        session.add(invitation)
        session.commit()
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")

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
    if invitation.relation_type == "patient":
        _hide_unowned_invitation()
    if not caregiver.phone_hash or invitation.invited_phone_hash != caregiver.phone_hash:
        _hide_unowned_invitation()
    if invitation.status == "pending" and invitation.is_expired:
        invitation.status = "expired"
        session.add(invitation)
        session.commit()
    if invitation.status != "pending":
        raise HTTPException(409, f"이미 {invitation.status} 처리된 초대예요")
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


class SentPatientInvitation(BaseModel):
    """[2026-07-23 추가] 보호자/기관이 보낸 "환자→계정 없음" 초대(relation_type="patient")는
    수락 전까지 patient_id가 없어서 InvitationPublic(patient_id 필수)을 그대로 못 쓴다."""
    id: int
    invited_phone: str | None = None
    status: str
    created_at: datetime
    expires_at: datetime | None = None


@router.get("/caregivers/{caregiver_id}/invitations", response_model=list[SentPatientInvitation])
def list_sent_patient_invitations(
    caregiver_id: int,
    caregiver: Caregiver = Depends(get_current_caregiver),
    session: Session = Depends(get_session),
):
    """연결관리(Connect.tsx) — 보호자/기관이 보낸 환자 초대 중 아직 대기중인 것.
    수락되면 caregiver_patients 연결이 생겨 환자 목록에 나타나므로 여기선 pending만 보여준다."""
    if caregiver_id != caregiver.id:
        raise HTTPException(403, "본인이 보낸 초대만 볼 수 있어요")
    invitations = session.exec(
        select(Invitation)
        .where(Invitation.relation_type == "patient")
        .where(Invitation.inviter_caregiver_id == caregiver_id)
        .where(Invitation.status == "pending")
        .order_by(Invitation.created_at.desc())
    ).all()
    result = []
    for inv in invitations:
        if inv.is_expired:
            inv.status = "expired"
            session.add(inv)
            continue
        result.append(inv)
    session.commit()
    return result


# ══════════════════════════════════════════
# 3. 돌봄관계 해제 (Trust Relation Dissolution, REQ-004)
# ══════════════════════════════════════════
# [2026-07-23 재설계] 해제 요청 자체(DELETE)는 monitoring_router.unlink_caregiver_from_patient가
# 맡는다 — 실제로 프론트가 호출하는 엔드포인트가 그쪽이라, 두 곳에 비슷한 로직을 중복해서
# 관리하지 않기 위해 요청 생성은 그 함수 하나로 모았다. 여기(care_router.py)는 이미 만들어진
# revocation_pending 건을 조회/승인/거부하는 것만 담당한다.
#
# [2026-07-23 변경] care_level(자가진단) 기반 판단은 제거했다 — 자가진단을 만드는 화면이
# 없어 실질적으로 항상 비어있었다. 대신 "기관(organization) 계정이 요청자인가"로 승인
# 필요 여부를 가른다: 환자·보호자가 스스로 관리하지 못하는 상황에서 기관이 사유 없이 손을
# 떼는 걸 막기 위함. 정당한 사유로 끊으려는 기관이 상대 무응답에 무기한 묶이지 않도록,
# REVOCATION_TIMEOUT_DAYS가 지나면 요청자 본인도 스스로 확정할 수 있다.
REVOCATION_TIMEOUT_DAYS = 14


class RevocationApprovalRequest(BaseModel):
    approve: bool


class RevocationApprovalResult(BaseModel):
    trust_id: int
    patient_id: int
    caregiver_id: int
    status: str
    revoked_at: datetime | None = None
    should_alert_now: bool = False


class PendingRevocation(BaseModel):
    """"받은 해제 요청" 목록 — 환자·보호자가 기관의 해제 사유를 보고 승인/거부하거나,
    요청자 본인이 타임아웃 경과 후 스스로 확정할 수 있는지(can_finalize) 확인하는 용도."""
    trust_id: int
    patient_id: int
    patient_name: str
    caregiver_id: int
    caregiver_name: str
    reason: str | None = None
    requested_at: datetime | None = None
    requested_by_role: str
    deadline: datetime | None = None
    can_finalize: bool = False


def _should_alert_now(patient: Patient) -> bool:
    """REQ-007a: dismissed_at이 None이거나 30일이 지났으면 안내를 표시해야 한다."""
    if patient.caregiver_alert_dismissed_at is None:
        return True
    return patient.caregiver_alert_dismissed_at + timedelta(days=30) < datetime.now()


@router.get("/trust/relations/pending", response_model=list[PendingRevocation])
def list_pending_revocations(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """"받은 해제 요청" — 환자 본인이거나, 그 환자와 연결된(revoked 아닌) 다른 보호자면
    이 환자의 대기중 해제 요청을 볼 수 있다(요청자 본인도 포함 — 타임아웃 후 직접 확정용)."""
    role, subject = actor
    if role == "patient":
        patient_ids = [subject.id]
    else:
        patient_ids = [
            link.patient_id
            for link in session.exec(
                select(CaregiverPatient)
                .where(CaregiverPatient.caregiver_id == subject.id)
                .where(CaregiverPatient.status != "revoked")
            ).all()
        ]
    if not patient_ids:
        return []

    links = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.patient_id.in_(patient_ids))
        .where(CaregiverPatient.status == "revocation_pending")
    ).all()

    result = []
    for link in links:
        patient = session.get(Patient, link.patient_id)
        caregiver = session.get(Caregiver, link.caregiver_id)
        deadline = (
            link.revocation_requested_at + timedelta(days=REVOCATION_TIMEOUT_DAYS)
            if link.revocation_requested_at
            else None
        )
        is_requester = link.revocation_requested_by == subject.id and link.requested_by_role == role
        result.append(
            PendingRevocation(
                trust_id=link.id,
                patient_id=link.patient_id,
                patient_name=patient.name if patient else "알 수 없음",
                caregiver_id=link.caregiver_id,
                caregiver_name=caregiver.name if caregiver else "알 수 없음",
                reason=link.revocation_reason,
                requested_at=link.revocation_requested_at,
                requested_by_role=link.requested_by_role or "caregiver",
                deadline=deadline,
                can_finalize=is_requester and deadline is not None and datetime.now() > deadline,
            )
        )
    return result


@router.post("/trust/relations/{trust_id}/revocation-approval", response_model=RevocationApprovalResult)
def approve_revocation(
    trust_id: int,
    payload: RevocationApprovalRequest,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """기관이 요청한(또는 과거 REQ-004 경로로 남아있는) 해제 요청의 승인/거부.

    approve=True  → status='revoked', revoked_at 기록.
                    남은 active 연결이 0명이면 should_alert_now=True 반환(REQ-007a).
    approve=False → status='active'로 복원(해제 거부).

    [2026-07-23 추가] 요청자 본인은 원칙적으로 승인 불가하지만, REVOCATION_TIMEOUT_DAYS(14일)가
    지나도록 상대가 응답하지 않았으면 본인이 approve=True로 직접 확정할 수 있다 — 정당한 사유로
    끊으려는 기관이 무응답에 무기한 묶이는 걸 막기 위함."""
    link = session.get(CaregiverPatient, trust_id)
    if not link:
        raise HTTPException(404, "존재하지 않는 연결이에요")

    require_actor_patient_access(link.patient_id, actor, session)

    if link.status != "revocation_pending":
        raise HTTPException(409, f"승인 대상이 아닌 연결이에요 (현재 상태: {link.status})")

    role, subject = actor
    is_requester = link.revocation_requested_by == subject.id and link.requested_by_role == role
    deadline_passed = link.revocation_requested_at is not None and datetime.now() > (
        link.revocation_requested_at + timedelta(days=REVOCATION_TIMEOUT_DAYS)
    )
    if is_requester and not deadline_passed:
        raise HTTPException(
            403,
            f"본인이 요청한 해제는 본인이 승인할 수 없어요 — 상대가 {REVOCATION_TIMEOUT_DAYS}일 안에 "
            "응답하지 않으면 직접 확정할 수 있어요.",
        )

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
        link.revocation_reason = None
        link.revocation_requested_at = None
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
