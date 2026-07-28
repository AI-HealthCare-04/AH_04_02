"""link_caregiver_to_patient()의 IDOR 회귀 테스트.

[7/13] PR #29 리뷰에서 발견: 이 엔드포인트가 "본인 계정으로 연결하는지"만 확인하고
"이 환자에 접근할 권한이 애초에 있는지"는 확인하지 않아서, patient_id를 순차 추측해
아무 환자에게나 자기 자신을 연결(=완전한 접근 권한 획득)할 수 있었다. 이미 다른
보호자가 연결된 환자면 거부하도록 고쳤다 — 방금 만든 환자에 본인을 최초 연결하는
정상 플로우는 그대로 통과해야 한다.
"""
import models
import pytest
from conftest import make_test_engine
from fastapi import HTTPException
from routers.monitoring_router import link_caregiver_to_patient
from sqlmodel import Session, select


def _make_session():
    engine = make_test_engine()
    return Session(engine)


def _make_caregiver(session: Session, name: str) -> models.Caregiver:
    caregiver = models.Caregiver()
    caregiver.name = name
    session.add(caregiver)
    session.commit()
    session.refresh(caregiver)
    return caregiver


def _make_patient(session: Session, name: str) -> models.Patient:
    patient = models.Patient()
    patient.name = name
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def test_caregiver_can_link_self_to_patient_with_no_existing_caregiver():
    """방금 만든 환자(연결된 보호자 없음)에 본인을 최초로 연결하는 정상 플로우는 통과해야 한다."""
    with _make_session() as session:
        caregiver = _make_caregiver(session, "박보호")
        patient = _make_patient(session, "새 환자")

        result = link_caregiver_to_patient(caregiver.id, patient.id, caregiver, session)

        assert result == {"linked": True, "caregiver_id": caregiver.id, "patient_id": patient.id}
        links = session.exec(select(models.CaregiverPatient)).all()
        assert len(links) == 1


def test_caregiver_cannot_self_link_to_patient_already_owned_by_another_caregiver():
    """이미 다른 보호자가 연결된 환자에는 초대 없이 자가 연결할 수 없어야 한다 (IDOR 방지)."""
    with _make_session() as session:
        owner = _make_caregiver(session, "원래 보호자")
        attacker = _make_caregiver(session, "다른 보호자")
        patient = _make_patient(session, "다른 사람의 환자")
        session.add(models.CaregiverPatient(caregiver_id=owner.id, patient_id=patient.id))
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            link_caregiver_to_patient(attacker.id, patient.id, attacker, session)
        assert exc_info.value.status_code == 403

        links = session.exec(
            select(models.CaregiverPatient).where(models.CaregiverPatient.caregiver_id == attacker.id)
        ).all()
        assert links == []  # 공격자 계정으로는 연결이 생기면 안 됨


def test_caregiver_relinking_self_to_already_linked_patient_is_idempotent():
    """이미 본인이 연결돼 있는 환자를 다시 연결 요청하면 에러 없이 already_linked만 반환한다."""
    with _make_session() as session:
        caregiver = _make_caregiver(session, "박보호")
        patient = _make_patient(session, "환자")
        session.add(models.CaregiverPatient(caregiver_id=caregiver.id, patient_id=patient.id))
        session.commit()

        result = link_caregiver_to_patient(caregiver.id, patient.id, caregiver, session)

        assert result == {"already_linked": True}
