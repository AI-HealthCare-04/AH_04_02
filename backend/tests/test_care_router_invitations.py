"""accept_invitation()의 트랜잭션 원자성 회귀 테스트.

[7/13] 신규 보호자 생성 직후 즉시 commit하던 걸 flush로 바꿔서, CaregiverPatient 연결·
invitation 상태 갱신까지 한 트랜잭션으로 묶었다. 이 테스트는 최종 커밋 전에 실패가 나면
방금 만든 Caregiver까지 롤백되는지(= 예전처럼 고아 Caregiver가 안 남는지) 확인한다.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import models
import pytest
from core.security import hash_token
from pydantic import ValidationError
from routers.care_router import (
    InvitationAccept,
    InvitationCreate,
    accept_invitation,
    accept_invitation_as_caregiver,
    create_invitation,
    delete_pending_invitation,
)
from sqlmodel import Session, SQLModel, create_engine, select

RAW_TOKEN = "tok123"


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_pending_invitation(
    session: Session, relation_type: str = "guardian", invited_phone: str | None = None
) -> models.Invitation:
    patient = models.Patient()
    patient.name = "테스트 환자"
    session.add(patient)
    session.commit()
    session.refresh(patient)

    invitation = models.Invitation(
        patient_id=patient.id,
        token_hash=hash_token(RAW_TOKEN),
        relation_type=relation_type,
        expires_at=datetime.now() + timedelta(days=7),
    )
    if invited_phone:
        invitation.invited_phone = invited_phone
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return invitation


def test_accept_invitation_commits_caregiver_and_link_together():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _make_pending_invitation(session)

        accept_invitation(RAW_TOKEN, InvitationAccept(caregiver_name="박보호"), session)

        caregivers = session.exec(select(models.Caregiver)).all()
        links = session.exec(select(models.CaregiverPatient)).all()
        assert len(caregivers) == 1
        assert len(links) == 1
        assert links[0].caregiver_id == caregivers[0].id


def test_invitation_create_rejects_arbitrary_relation_type():
    with pytest.raises(ValidationError):
        InvitationCreate(patient_id=1, relation_type="totally_arbitrary_garbage_value")


def test_create_guardian_invitation_from_patient_account():
    """환자→보호자류 초대 생성도 유지돼야 한다.

    보호자→환자 초대(relation_type="patient")와 함께 쓰는 양방향 연결 흐름이다.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        patient = models.Patient()
        patient.name = "테스트 환자"
        session.add(patient)
        session.commit()
        session.refresh(patient)

        result = create_invitation(
            InvitationCreate(
                patient_id=patient.id,
                relation_type="guardian",
                invited_phone="010-1234-5678",
            ),
            ("patient", patient),
            session,
        )

        assert "token" in result
        invitation = session.exec(select(models.Invitation)).one()
        assert invitation.patient_id == patient.id
        assert invitation.relation_type == "guardian"
        assert invitation.inviter_caregiver_id is None
        assert invitation.invited_phone == "010-1234-5678"


def test_delete_pending_guardian_invitation_cancels_token():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        patient = models.Patient()
        patient.name = "테스트 환자"
        session.add(patient)
        session.commit()
        session.refresh(patient)

        create_invitation(
            InvitationCreate(patient_id=patient.id, relation_type="guardian"),
            ("patient", patient),
            session,
        )
        invitation = session.exec(select(models.Invitation)).one()

        result = delete_pending_invitation(invitation.id, ("patient", patient), session)

        session.refresh(invitation)
        assert result == {"deleted": invitation.id, "status": "cancelled"}
        assert invitation.status == "cancelled"


def test_delete_pending_patient_invitation_requires_inviter_caregiver():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        owner = _make_caregiver(session, "초대한 보호자")
        other = _make_caregiver(session, "다른 보호자")
        invitation = _make_pending_patient_invitation(session, owner)

        with pytest.raises(Exception) as exc:
            delete_pending_invitation(invitation.id, ("caregiver", other), session)

        assert getattr(exc.value, "status_code", None) == 404


def test_delete_invitation_hides_status_from_non_owner():
    """권한 없는 사용자가 초대 ID를 찍어도 accepted/cancelled 같은 상태를 알 수 없어야 한다."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        owner = _make_caregiver(session, "초대한 보호자")
        other = _make_caregiver(session, "다른 보호자")
        invitation = _make_pending_patient_invitation(session, owner)
        invitation.status = "accepted"
        session.add(invitation)
        session.commit()

        with pytest.raises(Exception) as exc:
            delete_pending_invitation(invitation.id, ("caregiver", other), session)

        assert getattr(exc.value, "status_code", None) == 404


def test_accept_invitation_preserves_invitation_relation_type():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _make_pending_invitation(session, relation_type="life_support_worker")

        accept_invitation(RAW_TOKEN, InvitationAccept(caregiver_name="생활지원사"), session)

        caregiver = session.exec(select(models.Caregiver)).one()
        assert caregiver.relation_type == "life_support_worker"


def _make_caregiver(session: Session, name: str = "김보호", phone: str | None = None) -> models.Caregiver:
    caregiver = models.Caregiver(relation_type="guardian")
    caregiver.name = name
    caregiver.phone = phone
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


def test_accept_matching_invitation_hides_status_from_wrong_caregiver():
    """받은 초대 처리도 소유권 확인이 먼저라, 다른 보호자는 초대 상태를 유추할 수 없어야 한다."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        invitation = _make_pending_invitation(session, invited_phone="010-1111-2222")
        owner = _make_caregiver(session, "초대받은 보호자", phone="010-1111-2222")
        other = _make_caregiver(session, "다른 보호자", phone="010-9999-9999")
        invitation.status = "accepted"
        session.add(invitation)
        session.commit()

        with pytest.raises(Exception) as exc:
            accept_invitation_as_caregiver(invitation.id, other, session)

        assert getattr(exc.value, "status_code", None) == 404

        with pytest.raises(Exception) as exc:
            accept_invitation_as_caregiver(invitation.id, owner, session)

        assert getattr(exc.value, "status_code", None) == 409


def _make_pending_patient_invitation(
    session: Session, inviter: models.Caregiver, invited_phone: str | None = None
) -> models.Invitation:
    """보호자→환자 초대(relation_type="patient") — 아직 환자 계정이 없어 patient_id=None."""
    invitation = models.Invitation(
        patient_id=None,
        inviter_caregiver_id=inviter.id,
        token_hash=hash_token(RAW_TOKEN),
        relation_type="patient",
        expires_at=datetime.now() + timedelta(days=7),
    )
    if invited_phone:
        invitation.invited_phone = invited_phone
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return invitation


def test_create_patient_invitation_needs_no_patient_id():
    """(a) relation_type="patient" 초대는 patient_id 없이 생성돼야 한다."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        caregiver = _make_caregiver(session)

        result = create_invitation(
            InvitationCreate(relation_type="patient", inviter_caregiver_id=caregiver.id),
            ("caregiver", caregiver),
            session,
        )

        assert "token" in result
        invitation = session.exec(select(models.Invitation)).one()
        assert invitation.patient_id is None
        assert invitation.relation_type == "patient"
        assert invitation.inviter_caregiver_id == caregiver.id


def test_create_patient_invitation_requires_own_caregiver_id():
    """다른 보호자 id를 inviter로 넣어 초대하려 하면 403."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        me = _make_caregiver(session, "나")
        other = _make_caregiver(session, "남")

        with pytest.raises(Exception) as exc:
            create_invitation(
                InvitationCreate(relation_type="patient", inviter_caregiver_id=other.id),
                ("caregiver", me),
                session,
            )
        assert getattr(exc.value, "status_code", None) == 403


def test_accept_patient_invitation_creates_real_patient_and_link():
    """(b) 보호자→환자 초대를 수락하면 로그인 가능한(hashed_password 있는) Patient가 생기고
    inviter 보호자와의 CaregiverPatient 연결도 함께 생성된다."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        caregiver = _make_caregiver(session)
        _make_pending_patient_invitation(session, caregiver)

        result = accept_invitation(
            RAW_TOKEN,
            InvitationAccept(
                patient_name="환자본인",
                patient_email="patient@example.com",
                patient_password="secret123",
                patient_phone="010-1234-5678",
            ),
            session,
        )

        patient = session.exec(select(models.Patient)).one()
        assert result["patient_id"] == patient.id
        assert result["status"] == "accepted"
        assert patient.name == "환자본인"
        assert patient.hashed_password is not None  # 실제 로그인 가능한 계정

        link = session.exec(select(models.CaregiverPatient)).one()
        assert link.caregiver_id == caregiver.id
        assert link.patient_id == patient.id

        invitation = session.exec(select(models.Invitation)).one()
        assert invitation.status == "accepted"
        assert invitation.patient_id == patient.id


def test_accept_patient_invitation_requires_patient_name():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        caregiver = _make_caregiver(session)
        _make_pending_patient_invitation(session, caregiver)

        with pytest.raises(Exception) as exc:
            accept_invitation(RAW_TOKEN, InvitationAccept(patient_password="x"), session)
        assert getattr(exc.value, "status_code", None) == 400


def test_accept_patient_invitation_requires_matching_phone_when_invited_phone_set():
    """[2026-07-20 보안수정] relation_type="patient" 분기가 REQ-003 전화번호 검증보다
    먼저 return해서, invited_phone이 지정된 초대인데도 아무 번호로나(혹은 번호 없이)
    수락해 계정을 만들 수 있었다 — 링크만 탈취하면 본인 인증 없이 통과되던 문제."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        caregiver = _make_caregiver(session)
        _make_pending_patient_invitation(session, caregiver, invited_phone="010-1234-5678")

        with pytest.raises(Exception) as exc:
            accept_invitation(
                RAW_TOKEN,
                InvitationAccept(patient_name="환자본인", patient_phone="010-9999-9999"),
                session,
            )
        assert getattr(exc.value, "status_code", None) == 403
        assert session.exec(select(models.Patient)).all() == []


def test_accept_patient_invitation_succeeds_with_matching_phone():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        caregiver = _make_caregiver(session)
        _make_pending_patient_invitation(session, caregiver, invited_phone="010-1234-5678")

        result = accept_invitation(
            RAW_TOKEN,
            InvitationAccept(patient_name="환자본인", patient_phone="010-1234-5678"),
            session,
        )
        assert result["status"] == "accepted"


def test_accept_invitation_rolls_back_caregiver_when_failure_happens_after_creation():
    """Caregiver 생성 이후(= CaregiverPatient 연결/invitation 갱신 시점)에 장애가 나도,
    Caregiver가 이미 커밋돼서 고아로 남으면 안 된다.

    수정 전 코드(session.commit() 두 번)였다면 이 시점엔 이미 1차 commit이 끝나서 Caregiver가
    영구 저장된 상태라, 여기서 예외가 나도 Caregiver만 롤백 없이 남는다 — 이 테스트는 그걸
    재현하지 않는지(= flush로 바꾼 수정이 실제로 적용됐는지) 확인한다.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _make_pending_invitation(session)

        # invitation.accepted_at = datetime.now()는 Caregiver 생성/flush 이후, 최종 commit
        # 직전에 실행되는 지점이라 — 실제 장애가 그 사이 어디서든 났을 때와 동등한 시나리오다.
        with patch("routers.care_router.datetime") as mock_datetime:
            mock_datetime.now.side_effect = RuntimeError("Caregiver 생성 이후 장애 시뮬레이션")
            with pytest.raises(RuntimeError):
                accept_invitation(RAW_TOKEN, InvitationAccept(caregiver_name="박보호"), session)

        # 실제 get_session()의 `with Session(engine) as session:`이 예외 시 하는 것과 동일하게
        # 롤백한다 — flush만 됐던 Caregiver도 여기서 함께 사라져야 한다.
        session.rollback()

        assert session.exec(select(models.Caregiver)).all() == []
        assert session.exec(select(models.CaregiverPatient)).all() == []
        refreshed = session.exec(
            select(models.Invitation).where(models.Invitation.token_hash == hash_token(RAW_TOKEN))
        ).first()
        assert refreshed.status == "pending"  # 커밋 전 상태로 롤백됨
