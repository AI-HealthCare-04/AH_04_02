"""DELETE /monitoring/caregivers/{caregiver_id}/patients/{patient_id} — REQ-004 재설계.

[2026-07-23 재설계] 기존엔 하드 삭제(즉시, 무조건)였다. 이제 기관(organization) 계정이
연결을 끊을 때는 사유를 반드시 남기고 상대(환자/다른 보호자)의 승인을 받아야 한다 —
환자·보호자가 스스로 관리하지 못하는 상황에서 기관이 사유 없이 손을 떼는 걸 막기 위함.
개인 보호자·환자 본인이 끊을 때는 기존과 동일하게 즉시(소프트) 처리한다.

이전에 care_router.py의 DELETE /trust/relations/{trust_id}가 담당하던(그러나 프론트에서
한 번도 호출되지 않던) care_level 기반 판단은 제거했다 — 이제 이 엔드포인트 하나가
실제로 프론트가 호출하는 "연결 해제" 경로이자, 승인 필요 여부까지 판단한다.
"""
import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _caregiver(session: Session, name: str = "보호자", relation_type: str = "guardian") -> Caregiver:
    cg = Caregiver(hashed_password="x", relation_type=relation_type)
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _link(session: Session, cg: Caregiver, pt: Patient) -> CaregiverPatient:
    lnk = CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id)
    session.add(lnk)
    session.commit()
    session.refresh(lnk)
    return lnk


def _headers(subject_id: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject_id, role)}"}


def _unlink_url(cg_id: int, pt_id: int) -> str:
    return f"/monitoring/caregivers/{cg_id}/patients/{pt_id}"


# ── 개인 보호자·환자 본인 = 즉시 해제 ──────────────────────────

def test_individual_guardian_unlink_is_immediate(client: TestClient, session: Session):
    cg, pt = _caregiver(session, relation_type="guardian"), _patient(session)
    _link(session, cg, pt)

    r = client.delete(_unlink_url(cg.id, pt.id), headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 200
    body = r.json()
    assert body["unlinked"] is True
    assert body["status"] == "revoked"


def test_patient_initiated_unlink_is_immediate(client: TestClient, session: Session):
    cg, pt = _caregiver(session, relation_type="organization"), _patient(session)
    _link(session, cg, pt)

    r = client.delete(_unlink_url(cg.id, pt.id), headers=_headers(pt.id, "patient"))

    assert r.status_code == 200
    assert r.json()["status"] == "revoked"


# ── 기관 = 사유 필수 + 승인 대기 ──────────────────────────────

def test_organization_unlink_without_reason_rejected(client: TestClient, session: Session):
    cg, pt = _caregiver(session, relation_type="organization"), _patient(session)
    _link(session, cg, pt)

    r = client.delete(_unlink_url(cg.id, pt.id), headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 400


def test_organization_unlink_with_reason_goes_pending(client: TestClient, session: Session):
    cg, pt = _caregiver(session, "행복요양원", relation_type="organization"), _patient(session)
    _link(session, cg, pt)

    r = client.delete(
        _unlink_url(cg.id, pt.id),
        params={"reason": "환자가 타 시설로 전원했어요"},
        headers=_headers(cg.id, "caregiver"),
    )

    assert r.status_code == 200
    body = r.json()
    assert body["unlinked"] is False
    assert body["status"] == "revocation_pending"

    link = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.caregiver_id == cg.id)
        .where(CaregiverPatient.patient_id == pt.id)
    ).first()
    assert link is not None
    assert link.status == "revocation_pending"
    assert link.revocation_reason == "환자가 타 시설로 전원했어요"
    assert link.revocation_requested_at is not None
    assert link.revocation_requested_by == cg.id
    assert link.requested_by_role == "caregiver"


def test_organization_unlink_still_has_full_access_while_pending(client: TestClient, session: Session):
    """[2026-07-23 추가] 대기 중에는 아직 실제로 끊긴 게 아니므로, 기관은 계속 환자에
    접근할 수 있어야 한다(require_patient_access가 revocation_pending은 통과시킴)."""
    cg, pt = _caregiver(session, relation_type="organization"), _patient(session)
    _link(session, cg, pt)
    client.delete(_unlink_url(cg.id, pt.id), params={"reason": "사유"}, headers=_headers(cg.id, "caregiver"))

    r = client.get(f"/monitoring/patients/{pt.id}/caregivers", headers=_headers(pt.id, "patient"))
    assert r.status_code == 200
    assert any(c["id"] == cg.id for c in r.json())


# ── 에러 케이스 ────────────────────────────────────────────

def test_unrelated_actor_403(client: TestClient, session: Session):
    cg, pt = _caregiver(session), _patient(session)
    _link(session, cg, pt)
    other_cg = _caregiver(session, "무관자")

    r = client.delete(_unlink_url(cg.id, pt.id), headers=_headers(other_cg.id, "caregiver"))

    assert r.status_code == 403


def test_no_link_404(client: TestClient, session: Session):
    cg, pt = _caregiver(session), _patient(session)

    r = client.delete(_unlink_url(cg.id, pt.id), headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 404


def test_already_revoked_link_404(client: TestClient, session: Session):
    cg, pt = _caregiver(session), _patient(session)
    _link(session, cg, pt)
    client.delete(_unlink_url(cg.id, pt.id), headers=_headers(cg.id, "caregiver"))

    r = client.delete(_unlink_url(cg.id, pt.id), headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 404


def test_already_pending_link_409(client: TestClient, session: Session):
    cg, pt = _caregiver(session, relation_type="organization"), _patient(session)
    _link(session, cg, pt)
    client.delete(_unlink_url(cg.id, pt.id), params={"reason": "사유"}, headers=_headers(cg.id, "caregiver"))

    r = client.delete(_unlink_url(cg.id, pt.id), params={"reason": "다른 사유"}, headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 409


# ── 핵심 보안 회귀: 해제된 보호자는 접근 권한도 잃는다 ──────────────

def test_revoked_caregiver_loses_patient_access(client: TestClient, session: Session):
    """[2026-07-23 추가, 핵심 회귀 테스트] unlink가 하드 삭제 대신 status="revoked"로 남는
    소프트 삭제로 바뀌면서, require_patient_access가 status를 걸러내지 않으면 해제된
    보호자도 행이 존재한다는 이유로 계속 그 환자에 접근할 수 있었다(권한 우회)."""
    cg, pt = _caregiver(session), _patient(session)
    _link(session, cg, pt)
    client.delete(_unlink_url(cg.id, pt.id), headers=_headers(cg.id, "caregiver"))

    r = client.get(f"/monitoring/patients/{pt.id}/caregivers", headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 403
