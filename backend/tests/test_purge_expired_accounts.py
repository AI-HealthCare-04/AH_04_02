"""
test_purge_expired_accounts.py — REQ-035 scripts/purge_expired_accounts.py (2026-07-15 추가)

유예기간이 지난 pending 감사기록만 골라 개인정보를 비식별화하고, 아직 안 지났거나
이미 cancelled인 건은 건드리지 않는지 검증한다. --dry-run은 아무것도 바꾸지 않아야 한다.
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import purge_expired_accounts as purge  # noqa: E402

from core import database
from core.auth import hash_password
from models import Patient, PrivacyPurgeAudit


@pytest.fixture(name="engine")
def engine_fixture(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    return engine


def _run_main(monkeypatch, dry_run: bool) -> None:
    """argparse가 pytest 자신의 CLI 인자를 읽지 않도록 parse_args만 이 테스트 동안 대체."""
    monkeypatch.setattr(
        argparse.ArgumentParser, "parse_args", lambda self, *a, **k: argparse.Namespace(dry_run=dry_run)
    )
    purge.main()


def _make_patient_with_audit(session: Session, email: str, scheduled_purge_at: datetime, status: str = "pending") -> int:
    patient = Patient(hashed_password=hash_password("pw"), email=email)
    patient.name = "삭제대상자"
    patient.phone = "010-1234-5678"
    session.add(patient)
    session.commit()
    session.refresh(patient)

    session.add(
        PrivacyPurgeAudit(
            subject_type="patient",
            subject_id=patient.id,
            deactivated_at=scheduled_purge_at - timedelta(days=30),
            scheduled_purge_at=scheduled_purge_at,
            status=status,
        )
    )
    session.commit()
    return patient.id


def test_dry_run_changes_nothing(engine, monkeypatch):
    with Session(engine) as session:
        patient_id = _make_patient_with_audit(session, "due@test.com", datetime.now() - timedelta(days=1))

    _run_main(monkeypatch, dry_run=True)

    with Session(engine) as session:
        patient = session.get(Patient, patient_id)
        assert patient.email == "due@test.com"  # dry-run이라 그대로
        audit = session.exec(select(PrivacyPurgeAudit).where(PrivacyPurgeAudit.subject_id == patient_id)).first()
        assert audit.status == "pending"


def test_real_run_scrubs_only_due_pending_accounts(engine, monkeypatch):
    with Session(engine) as session:
        due_id = _make_patient_with_audit(session, "due@test.com", datetime.now() - timedelta(days=1))
        not_due_id = _make_patient_with_audit(session, "not-due@test.com", datetime.now() + timedelta(days=25))
        cancelled_id = _make_patient_with_audit(
            session, "cancelled@test.com", datetime.now() - timedelta(days=10), status="cancelled"
        )

    _run_main(monkeypatch, dry_run=False)

    with Session(engine) as session:
        due = session.get(Patient, due_id)
        assert due.email is None
        assert due.hashed_password is None
        assert due.phone_encrypted is None
        assert due.name == purge._PURGED_NAME_PLACEHOLDER

        due_audit = session.exec(select(PrivacyPurgeAudit).where(PrivacyPurgeAudit.subject_id == due_id)).first()
        assert due_audit.status == "completed"
        assert due_audit.completed_at is not None

        not_due = session.get(Patient, not_due_id)
        assert not_due.email == "not-due@test.com"  # 아직 유예기간 안 지남 — 그대로

        cancelled = session.get(Patient, cancelled_id)
        assert cancelled.email == "cancelled@test.com"  # 취소된 건 — 그대로


def test_missing_account_marks_audit_completed_without_crashing(engine, monkeypatch):
    with Session(engine) as session:
        session.add(
            PrivacyPurgeAudit(
                subject_type="patient",
                subject_id=999999,  # 존재하지 않는 patient_id
                deactivated_at=datetime.now() - timedelta(days=31),
                scheduled_purge_at=datetime.now() - timedelta(days=1),
                status="pending",
            )
        )
        session.commit()

    _run_main(monkeypatch, dry_run=False)  # 예외 없이 완료돼야 함

    with Session(engine) as session:
        audit = session.exec(select(PrivacyPurgeAudit).where(PrivacyPurgeAudit.subject_id == 999999)).first()
        assert audit.status == "completed"
