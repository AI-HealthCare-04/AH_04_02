"""accept_invitation()의 트랜잭션 원자성 회귀 테스트.

[7/13] 신규 보호자 생성 직후 즉시 commit하던 걸 flush로 바꿔서, CaregiverPatient 연결·
invitation 상태 갱신까지 한 트랜잭션으로 묶었다. 이 테스트는 최종 커밋 전에 실패가 나면
방금 만든 Caregiver까지 롤백되는지(= 예전처럼 고아 Caregiver가 안 남는지) 확인한다.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine, select

import models
from core.security import hash_token
from routers.care_router import InvitationAccept, InvitationCreate, accept_invitation

RAW_TOKEN = "tok123"


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_pending_invitation(session: Session, relation_type: str = "guardian") -> models.Invitation:
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


def test_accept_invitation_preserves_invitation_relation_type():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _make_pending_invitation(session, relation_type="life_support_worker")

        accept_invitation(RAW_TOKEN, InvitationAccept(caregiver_name="생활지원사"), session)

        caregiver = session.exec(select(models.Caregiver)).one()
        assert caregiver.relation_type == "life_support_worker"


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
