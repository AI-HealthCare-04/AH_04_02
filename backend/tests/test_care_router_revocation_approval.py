"""POST /trust/relations/{trust_id}/revocation-approval — REQ-004 해제 승인/거부 테스트.

8개 시나리오:
1. 정상 승인 (approve=True) → revoked
2. 정상 거부 (approve=False) → active 복원
3. 본인이 본인 요청 승인 시도 (보호자) → 403
4. pending 아닌 상태에서 승인 시도 → 409
5. 무관한 보호자가 승인 시도 → 403
6. 마지막 연결 해제 시 should_alert_now=True (REQ-007a, dismissed_at=None 기준)
7. 환자가 요청 → 같은 환자가 승인 시도 → 403 (CRITICAL 수정, pecs0310 리뷰)
8. 환자가 요청 → 보호자가 승인 → 200 (정상 경로)
"""
from datetime import datetime, timedelta

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Caregiver, CaregiverPatient, Patient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

URL = "/trust/relations/{}/revocation-approval"


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


# ── 공통 헬퍼 ──────────────────────────────────────────────

def _patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _caregiver(session: Session, name: str = "보호자") -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _link(session: Session, cg: Caregiver, pt: Patient, status: str = "active") -> CaregiverPatient:
    lnk = CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id, status=status)
    session.add(lnk)
    session.commit()
    session.refresh(lnk)
    return lnk


def _pending_link(
    session: Session,
    requester: Caregiver,
    pt: Patient,
    *,
    requested_by_role: str = "caregiver",
    requested_by_id: int | None = None,
    requested_at: datetime | None = None,
) -> CaregiverPatient:
    lnk = CaregiverPatient(
        caregiver_id=requester.id,
        patient_id=pt.id,
        status="revocation_pending",
        revocation_requested_by=requested_by_id if requested_by_id is not None else requester.id,
        requested_by_role=requested_by_role,
        revocation_requested_at=requested_at if requested_at is not None else datetime.now(),
    )
    session.add(lnk)
    session.commit()
    session.refresh(lnk)
    return lnk


def _headers(subject_id: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject_id, role)}"}


# ── 1. 정상 승인 ───────────────────────────────────────────

def test_approve_sets_revoked(client: TestClient, session: Session):
    requester = _caregiver(session, "요청자")
    approver = _caregiver(session, "승인자")
    pt = _patient(session)

    # 두 보호자 모두 환자와 연결돼 있어야 require_actor_patient_access 통과
    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(approver.id, "caregiver"))

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "revoked"
    assert body["revoked_at"] is not None


# ── 2. 정상 거부 ───────────────────────────────────────────

def test_reject_restores_active(client: TestClient, session: Session):
    requester = _caregiver(session, "요청자")
    approver = _caregiver(session, "승인자")
    pt = _patient(session)

    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    r = client.post(URL.format(pending.id), json={"approve": False}, headers=_headers(approver.id, "caregiver"))

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["revoked_at"] is None

    # DB에서 revocation_requested_by / requested_by_role 모두 초기화됐는지 확인
    session.refresh(pending)
    assert pending.revocation_requested_by is None
    assert pending.requested_by_role is None


# ── 3. 본인이 본인 요청 승인 → 403 ────────────────────────

def test_self_approval_forbidden(client: TestClient, session: Session):
    requester = _caregiver(session, "요청자")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt)

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(requester.id, "caregiver"))

    assert r.status_code == 403


# ── 4. pending 아닌 상태에서 승인 시도 → 409 ───────────────

def test_non_pending_status_returns_409(client: TestClient, session: Session):
    cg = _caregiver(session)
    pt = _patient(session)
    active_link = _link(session, cg, pt, status="active")

    r = client.post(URL.format(active_link.id), json={"approve": True}, headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 409


# ── 5. 무관한 보호자가 승인 시도 → 403 ────────────────────

def test_unrelated_caregiver_forbidden(client: TestClient, session: Session):
    requester = _caregiver(session, "요청자")
    outsider = _caregiver(session, "무관자")
    pt = _patient(session)

    pending = _pending_link(session, requester, pt)
    # outsider는 이 환자와 연결 없음

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(outsider.id, "caregiver"))

    assert r.status_code == 403


# ── 6. 마지막 연결 해제 시 should_alert_now=True (REQ-007a) ──

def test_last_caregiver_revoked_should_alert(client: TestClient, session: Session):
    """보호자가 1명뿐이고 dismissed_at=None인 환자의 마지막 연결을 해제하면
    active 연결 0명 + dismissed_at 미설정 → should_alert_now=True."""
    requester = _caregiver(session, "유일한보호자")
    pt = _patient(session)
    # caregiver_alert_dismissed_at은 기본 None

    pending = _pending_link(session, requester, pt)

    # 환자 본인이 승인
    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(pt.id, "patient"))

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "revoked"
    assert body["should_alert_now"] is True


def test_alert_suppressed_within_30_days(client: TestClient, session: Session):
    """dismissed_at이 최근(30일 이내)이면 should_alert_now=False."""
    from datetime import datetime, timedelta

    requester = _caregiver(session, "보호자")
    pt = _patient(session)
    # 방금 닫은 것처럼 dismissed_at 세팅
    pt.caregiver_alert_dismissed_at = datetime.now() - timedelta(days=1)
    session.add(pt)
    session.commit()

    pending = _pending_link(session, requester, pt)
    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(pt.id, "patient"))

    assert r.status_code == 200
    assert r.json()["should_alert_now"] is False


def test_alert_reappears_after_30_days(client: TestClient, session: Session):
    """dismissed_at이 30일을 초과하면 should_alert_now=True로 다시 뜬다."""
    from datetime import datetime, timedelta

    requester = _caregiver(session, "보호자")
    pt = _patient(session)
    pt.caregiver_alert_dismissed_at = datetime.now() - timedelta(days=31)
    session.add(pt)
    session.commit()

    pending = _pending_link(session, requester, pt)
    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(pt.id, "patient"))

    assert r.status_code == 200
    assert r.json()["should_alert_now"] is True


# ── 7. 환자 요청 → 같은 환자 승인 시도 → 403 (CRITICAL, pecs0310 리뷰) ──────

def test_patient_self_approval_forbidden(client: TestClient, session: Session):
    """환자가 본인 요청한 해제를 본인이 승인 시도 → 403.

    기존 가드는 role=="caregiver"만 검사해서 환자 경로를 통과시켰다 — 이 테스트가 그 버그를
    재현하고, 수정 후 403으로 막히는지 검증한다 (pecs0310 CRITICAL 리뷰 재현 시나리오).
    """
    cg = _caregiver(session)
    pt = _patient(session)
    # 환자가 요청한 pending 상태 — requested_by_role="patient", revocation_requested_by=pt.id
    pending = _pending_link(
        session, cg, pt,
        requested_by_role="patient",
        requested_by_id=pt.id,
    )

    # 같은 환자가 승인 시도
    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(pt.id, "patient"))

    assert r.status_code == 403


# ── 8. 환자 요청 → 보호자가 승인 → 200 (정상 경로) ──────────────────────────

def test_caregiver_approves_patient_request(client: TestClient, session: Session):
    """환자가 요청한 해제를 보호자가 승인 → 200 revoked."""
    cg = _caregiver(session)
    pt = _patient(session)
    pending = _pending_link(
        session, cg, pt,
        requested_by_role="patient",
        requested_by_id=pt.id,
    )

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(cg.id, "caregiver"))

    assert r.status_code == 200
    assert r.json()["status"] == "revoked"


# ── 9. 2주 타임아웃 — 요청자 본인 확정 (2026-07-23 추가) ────────────────────

def test_requester_still_blocked_before_timeout(client: TestClient, session: Session):
    """요청 후 14일이 안 지났으면 요청자 본인은 여전히 승인할 수 없다."""
    requester = _caregiver(session, "요청기관")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt, requested_at=datetime.now() - timedelta(days=13))

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(requester.id, "caregiver"))

    assert r.status_code == 403


def test_requester_can_finalize_after_timeout(client: TestClient, session: Session):
    """상대가 14일 안에 응답하지 않으면 요청자 본인이 직접 확정(승인)할 수 있다 —
    정당한 사유로 끊으려는 기관이 무응답에 무기한 묶이지 않도록 하는 타임아웃."""
    requester = _caregiver(session, "요청기관")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt, requested_at=datetime.now() - timedelta(days=15))

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(requester.id, "caregiver"))

    assert r.status_code == 200
    assert r.json()["status"] == "revoked"


# ── 10. "받은 해제 요청" 목록 (2026-07-23 추가) ──────────────────────────────

def test_patient_sees_pending_revocation_with_reason(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    pt = _patient(session)
    _pending_link(session, requester, pt)

    r = client.get("/trust/relations/pending", headers=_headers(pt.id, "patient"))

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["caregiver_id"] == requester.id
    assert body[0]["requested_by_role"] == "caregiver"


def test_unrelated_caregiver_does_not_see_pending_revocation(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    outsider = _caregiver(session, "무관자")
    pt = _patient(session)
    _pending_link(session, requester, pt)

    r = client.get("/trust/relations/pending", headers=_headers(outsider.id, "caregiver"))

    assert r.status_code == 200
    assert r.json() == []


# ── 11. 해제 요청 처리 결과 알림 (2026-07-23 추가) ──────────────────────────

def test_approve_creates_notice_for_requester(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    approver = _caregiver(session, "승인자")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(approver.id, "caregiver"))
    assert r.status_code == 200

    notices = client.get("/trust/relations/notices", headers=_headers(requester.id, "caregiver"))
    assert notices.status_code == 200
    body = notices.json()
    assert len(body) == 1
    assert body[0]["approved"] is True
    assert body[0]["patient_name"] == "환자"
    assert body[0]["counterpart_name"] == "승인자"
    assert body[0]["read_at"] is None


def test_reject_creates_notice_for_requester(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    approver = _caregiver(session, "승인자")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    r = client.post(URL.format(pending.id), json={"approve": False}, headers=_headers(approver.id, "caregiver"))
    assert r.status_code == 200

    notices = client.get("/trust/relations/notices", headers=_headers(requester.id, "caregiver"))
    assert notices.status_code == 200
    body = notices.json()
    assert len(body) == 1
    assert body[0]["approved"] is False


def test_notice_not_visible_to_unrelated_caregiver(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    approver = _caregiver(session, "승인자")
    outsider = _caregiver(session, "무관자")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(approver.id, "caregiver"))

    r = client.get("/trust/relations/notices", headers=_headers(outsider.id, "caregiver"))
    assert r.status_code == 200
    assert r.json() == []


def test_mark_notice_read(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    approver = _caregiver(session, "승인자")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(approver.id, "caregiver"))
    notice_id = client.get(
        "/trust/relations/notices", headers=_headers(requester.id, "caregiver")
    ).json()[0]["id"]

    r = client.post(
        f"/trust/relations/notices/{notice_id}/read", headers=_headers(requester.id, "caregiver")
    )
    assert r.status_code == 200
    assert r.json()["read_at"] is not None


def test_mark_notice_read_forbidden_for_other_caregiver(client: TestClient, session: Session):
    requester = _caregiver(session, "요청기관")
    approver = _caregiver(session, "승인자")
    outsider = _caregiver(session, "무관자")
    pt = _patient(session)
    pending = _pending_link(session, requester, pt)
    _link(session, approver, pt)

    client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(approver.id, "caregiver"))
    notice_id = client.get(
        "/trust/relations/notices", headers=_headers(requester.id, "caregiver")
    ).json()[0]["id"]

    r = client.post(
        f"/trust/relations/notices/{notice_id}/read", headers=_headers(outsider.id, "caregiver")
    )
    assert r.status_code == 404


def test_patient_requester_receives_notice(client: TestClient, session: Session):
    """환자가 요청한 해제를 보호자가 승인하면, 환자에게도(role=patient) 알림이 남는다."""
    caregiver = _caregiver(session, "보호자")
    pt = _patient(session)
    pending = _pending_link(session, caregiver, pt, requested_by_role="patient", requested_by_id=pt.id)

    r = client.post(URL.format(pending.id), json={"approve": True}, headers=_headers(caregiver.id, "caregiver"))
    assert r.status_code == 200

    notices = client.get("/trust/relations/notices", headers=_headers(pt.id, "patient"))
    assert notices.status_code == 200
    body = notices.json()
    assert len(body) == 1
    assert body[0]["counterpart_name"] == "보호자"
