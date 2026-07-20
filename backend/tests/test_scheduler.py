"""
core/scheduler.py 테스트 (2026-07-19 신규, 담당: 김영혜)

REQ-026a(정시 알림)/REQ-026c(놓침 감지)/REQ-026d(third_party_needed 공동알림)의
핵심 로직을 검증한다. 스케줄러는 백그라운드 asyncio 루프라 lifespan을 실제로
띄우지 않고, _fire_due_reminders/_mark_missed를 명시적 now 인자로 직접 호출해
"정시가 됐다"를 시뮬레이션한다(실시간 sleep 없이 결정적으로 테스트하기 위함).
"""
import json
from datetime import datetime
from unittest.mock import patch

import pytest
from core import scheduler
from models import (
    Caregiver,
    CaregiverPatient,
    CareLevelAssessment,
    MedicationLog,
    MedicationSchedule,
    NotificationLog,
    NotificationSetting,
    Patient,
)
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_patient(session: Session, name: str = "환자", email: str | None = "patient@test.com") -> Patient:
    pt = Patient(hashed_password="x", email=email, email_opt_in=bool(email))
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_schedule(
    session: Session, patient: Patient, time_slot: str, active: bool = True, days_of_week: str | None = None
) -> MedicationSchedule:
    sched = MedicationSchedule(
        patient_id=patient.id, drug_name="테스트약", time_slot=time_slot, active=active, days_of_week=days_of_week
    )
    session.add(sched)
    session.commit()
    session.refresh(sched)
    return sched


def _make_caregiver_linked(session: Session, patient: Patient, name: str) -> Caregiver:
    cg = Caregiver(hashed_password="x", email=f"{name}@test.com", email_opt_in=True)
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=patient.id))
    session.commit()
    return cg


class TestFireDueReminders:
    def test_fires_reminder_when_due_time_just_passed(self, session: Session):
        pt = _make_patient(session)
        now = datetime(2026, 7, 19, 8, 5)
        _make_schedule(session, pt, "08:00")

        scheduler._fire_due_reminders(session, now)

        logs = session.exec(select(NotificationLog)).all()
        assert len(logs) == 1
        assert logs[0].kind == "reminder"
        assert logs[0].status == "sent"
        assert logs[0].due_date == "2026-07-19"

    def test_does_not_fire_before_due_time(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 7, 59)

        scheduler._fire_due_reminders(session, now)

        assert session.exec(select(NotificationLog)).all() == []

    def test_does_not_fire_outside_catch_up_window(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 8, 30)  # CATCH_UP_MINUTES(10분) 훌쩍 넘김

        scheduler._fire_due_reminders(session, now)

        assert session.exec(select(NotificationLog)).all() == []

    def test_dedup_via_unique_constraint_second_tick_noop(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 8, 5)

        scheduler._fire_due_reminders(session, now)
        scheduler._fire_due_reminders(session, datetime(2026, 7, 19, 8, 8))  # 다음 틱, 같은 창 안

        logs = session.exec(select(NotificationLog)).all()
        assert len(logs) == 1  # 두 번째 틱은 이미 처리된 걸 보고 건너뜀

    def test_inactive_schedule_ignored(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00", active=False)
        now = datetime(2026, 7, 19, 8, 5)

        scheduler._fire_due_reminders(session, now)

        assert session.exec(select(NotificationLog)).all() == []

    def test_days_of_week_filters_out_non_matching_day(self, session: Session):
        pt = _make_patient(session)
        # 2026-07-19는 일요일(sun) — 스케줄은 월/수/금만
        _make_schedule(session, pt, "08:00", days_of_week='["mon","wed","fri"]')
        now = datetime(2026, 7, 19, 8, 5)

        scheduler._fire_due_reminders(session, now)

        assert session.exec(select(NotificationLog)).all() == []

    def test_malformed_time_slot_skipped_without_crash(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "아침")  # 구 데이터 형식
        now = datetime(2026, 7, 19, 8, 5)

        scheduler._fire_due_reminders(session, now)  # 예외 없이 건너뛰어야 함

        assert session.exec(select(NotificationLog)).all() == []

    def test_opt_out_suppresses_send_but_logs(self, session: Session):
        pt = _make_patient(session)
        session.add(NotificationSetting(patient_id=pt.id, medication_reminder_enabled=False))
        session.commit()
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 8, 5)

        scheduler._fire_due_reminders(session, now)

        logs = session.exec(select(NotificationLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "suppressed"
        assert logs[0].channels == "[]"


class TestMarkMissed:
    def test_marks_missed_when_no_log_after_window(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 9, 5)  # MISSED_AFTER_MINUTES(60분) 지남

        scheduler._mark_missed(session, now)

        logs = session.exec(select(NotificationLog)).all()
        assert len(logs) == 1
        assert logs[0].kind == "missed"

    def test_no_missed_if_already_checked_today(self, session: Session):
        # [round5 수정] checked_at을 명시하지 않으면 MedicationLog의 default_factory=datetime.now가
        # "실제" 시스템 날짜를 쓰는데, 이 테스트는 시뮬레이션된 now(2026-07-19)와 비교한다 —
        # 테스트를 만든 날은 실제 날짜도 7/19라 우연히 통과했지만, 다음 날 실행하면 실패한다
        # (실제로 재현됨). checked_at을 시뮬레이션된 now로 명시해 날짜에 무관하게 만든다.
        pt = _make_patient(session)
        sched = _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 9, 5)
        session.add(MedicationLog(schedule_id=sched.id, status="taken", checked_at=now))
        session.commit()

        scheduler._mark_missed(session, now)

        assert session.exec(select(NotificationLog)).all() == []

    def test_no_missed_before_window_elapses(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 8, 30)  # 아직 60분 안 지남

        scheduler._mark_missed(session, now)

        assert session.exec(select(NotificationLog)).all() == []

    def test_missed_dedup_second_tick_noop(self, session: Session):
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 9, 5)

        scheduler._mark_missed(session, now)
        scheduler._mark_missed(session, datetime(2026, 7, 19, 9, 10))

        assert len(session.exec(select(NotificationLog)).all()) == 1

    def test_reminder_and_missed_coexist_for_same_schedule_day(self, session: Session):
        """같은 (schedule, due_date, time_slot)이라도 kind가 다르면 유니크 제약에 안 걸려야 한다."""
        pt = _make_patient(session)
        _make_schedule(session, pt, "08:00")

        scheduler._fire_due_reminders(session, datetime(2026, 7, 19, 8, 5))
        scheduler._mark_missed(session, datetime(2026, 7, 19, 9, 5))

        logs = session.exec(select(NotificationLog)).all()
        assert {log.kind for log in logs} == {"reminder", "missed"}


class TestCoNotification:
    def test_third_party_needed_notifies_all_linked_caregivers(self, session: Session):
        pt = _make_patient(session, email=None)  # 환자 본인은 이메일 미동의 — 보호자만 받는지 확인
        cg1 = Caregiver(hashed_password="x", email="cg1@test.com", email_opt_in=True)
        cg1.name = "보호자1"
        cg2 = Caregiver(hashed_password="x", email="cg2@test.com", email_opt_in=True)
        cg2.name = "보호자2"
        session.add(cg1)
        session.add(cg2)
        session.commit()
        session.refresh(cg1)
        session.refresh(cg2)
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=cg2.id, patient_id=pt.id))
        session.add(CareLevelAssessment(patient_id=pt.id, care_level="third_party_needed"))
        session.commit()
        _make_schedule(session, pt, "08:00")

        scheduler._fire_due_reminders(session, datetime(2026, 7, 19, 8, 5))

        log = session.exec(select(NotificationLog)).first()
        channels = json.loads(log.channels)
        assert f"email:caregiver:{cg1.id}" in channels
        assert f"email:caregiver:{cg2.id}" in channels

    def test_independent_care_level_notifies_only_first_linked_caregiver(self, session: Session):
        pt = _make_patient(session, email=None)
        cg1 = Caregiver(hashed_password="x", email="cg1@test.com", email_opt_in=True)
        cg1.name = "보호자1"
        cg2 = Caregiver(hashed_password="x", email="cg2@test.com", email_opt_in=True)
        cg2.name = "보호자2"
        session.add(cg1)
        session.add(cg2)
        session.commit()
        session.refresh(cg1)
        session.refresh(cg2)
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=cg2.id, patient_id=pt.id))
        session.commit()  # care_level 기본값 "independent"
        _make_schedule(session, pt, "08:00")

        scheduler._fire_due_reminders(session, datetime(2026, 7, 19, 8, 5))

        log = session.exec(select(NotificationLog)).first()
        channels = json.loads(log.channels)
        assert channels == [f"email:caregiver:{cg1.id}"]

    def test_schedule_caregiver_alert_false_skips_caregivers_but_not_patient(self, session: Session):
        """monitoring_router.py 스케줄 생성/수정 API에 이미 있는 per-schedule
        caregiver_alert 토글 — round5에서 발견: 스케줄러가 이 값을 전혀 참고하지 않고
        항상 보호자에게 알림을 보내던 실제 버그에 대한 회귀 테스트."""
        pt = _make_patient(session, email="patient@test.com")
        cg = _make_caregiver_linked(session, pt, "cg-alert-off")
        sched = MedicationSchedule(
            patient_id=pt.id, drug_name="테스트약", time_slot="08:00", active=True, caregiver_alert=False
        )
        session.add(sched)
        session.commit()

        scheduler._fire_due_reminders(session, datetime(2026, 7, 19, 8, 5))

        log = session.exec(select(NotificationLog)).first()
        channels = json.loads(log.channels)
        assert channels == ["email:patient"]
        assert f"email:caregiver:{cg.id}" not in channels

    def test_first_linked_caregiver_is_deterministic_by_id_not_insertion_coincidence(self, session: Session):
        """links 쿼리에 order_by가 없으면 SQLite에서는 우연히 삽입 순서로 보이지만 SQL
        표준상 보장되지 않는다(팀 실제 운영/개발 DB는 MySQL) — id로 정렬해 "최초 연결"이
        실제로 결정적인지 확인한다. cg2를 먼저 만들어 id가 더 작게 하고, CaregiverPatient는
        cg1(나중에 만든, id가 더 큼)을 먼저 연결해 "삽입 순서 우연"과 "id 순서"가 갈리게 한다."""
        pt = _make_patient(session, email=None)
        cg2 = Caregiver(hashed_password="x", email="cg2@test.com", email_opt_in=True)
        cg2.name = "먼저 생성된 보호자"
        session.add(cg2)
        session.commit()
        session.refresh(cg2)
        cg1 = Caregiver(hashed_password="x", email="cg1@test.com", email_opt_in=True)
        cg1.name = "나중에 생성된 보호자"
        session.add(cg1)
        session.commit()
        session.refresh(cg1)
        assert cg2.id < cg1.id

        # CaregiverPatient는 cg1을 먼저 연결(insert 순서상 cg1이 "먼저"지만 caregiver_patients.id는
        # 여전히 이 insert 순서를 따름 — 여기서 검증하려는 건 caregivers.id가 아니라
        # caregiver_patients.id로 "최초 연결"을 판단한다는 점).
        session.add(CaregiverPatient(caregiver_id=cg1.id, patient_id=pt.id))
        session.add(CaregiverPatient(caregiver_id=cg2.id, patient_id=pt.id))
        session.commit()
        _make_schedule(session, pt, "08:00")

        scheduler._fire_due_reminders(session, datetime(2026, 7, 19, 8, 5))

        log = session.exec(select(NotificationLog)).first()
        channels = json.loads(log.channels)
        # caregiver_patients row 삽입 순서상 cg1이 먼저 연결됐으므로 cg1이 "최초 연결"이어야 한다.
        assert channels == [f"email:caregiver:{cg1.id}"]


class TestDeliveryOrderingAvoidsDuplicateSend:
    """[2026-07-20 round2, 박소정님 리뷰에서 발견] 예전엔 _deliver()(실제 발송)가
    NotificationLog 커밋보다 먼저 실행됐다 — 유니크 제약이 "로그 행"의 중복은 막아도
    "발송 자체"의 중복은 못 막아서, 공유 DB에 동시 tick이 오면 두 프로세스가 각자
    이메일을 보낼 수 있었다(로그는 하나만 남지만). placeholder 행을 먼저 insert+commit해서
    유니크 제약으로 선점한 프로세스만 실제 발송하도록 순서를 바꿨다 — _deliver가 불리는
    시점엔 이미 로그 행이 커밋되어 있어야 한다."""

    def test_reminder_placeholder_committed_before_delivery_attempted(self, session: Session):
        pt = _make_patient(session)
        sched = _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 8, 5)

        log_existed_at_delivery_time = []
        original_deliver = scheduler._deliver

        def _spy_deliver(sess, schedule_arg, patient_arg, kind):
            existing = sess.exec(
                select(NotificationLog).where(NotificationLog.schedule_id == schedule_arg.id)
            ).first()
            log_existed_at_delivery_time.append(existing is not None)
            return original_deliver(sess, schedule_arg, patient_arg, kind)

        with patch("core.scheduler._deliver", side_effect=_spy_deliver):
            scheduler._fire_due_reminders(session, now)

        assert log_existed_at_delivery_time == [True]
        # placeholder는 최종적으로 실제 발송 결과로 갱신되어야 한다("pending"으로 안 남음).
        final = session.exec(select(NotificationLog).where(NotificationLog.schedule_id == sched.id)).first()
        assert final.status != "pending"

    def test_missed_placeholder_committed_before_delivery_attempted(self, session: Session):
        pt = _make_patient(session)
        sched = _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 9, 5)

        log_existed_at_delivery_time = []
        original_deliver = scheduler._deliver

        def _spy_deliver(sess, schedule_arg, patient_arg, kind):
            existing = sess.exec(
                select(NotificationLog).where(NotificationLog.schedule_id == schedule_arg.id)
            ).first()
            log_existed_at_delivery_time.append(existing is not None)
            return original_deliver(sess, schedule_arg, patient_arg, kind)

        with patch("core.scheduler._deliver", side_effect=_spy_deliver):
            scheduler._mark_missed(session, now)

        assert log_existed_at_delivery_time == [True]
        final = session.exec(select(NotificationLog).where(NotificationLog.schedule_id == sched.id)).first()
        assert final.status != "pending"

    def test_delivery_not_attempted_when_slot_already_claimed_by_another_process(self, session: Session):
        """다른 프로세스가 이미 이 (schedule, due_date, time_slot, kind)를 선점(커밋)해둔
        상태를 시뮬레이션 — placeholder insert가 유니크 제약에 걸려 실패하므로 발송 자체가
        아예 시도되면 안 된다."""
        pt = _make_patient(session)
        sched = _make_schedule(session, pt, "08:00")
        now = datetime(2026, 7, 19, 8, 5)

        session.add(
            NotificationLog(
                schedule_id=sched.id,
                patient_id=pt.id,
                due_date="2026-07-19",
                time_slot="08:00",
                kind="reminder",
                status="sent",
                channels="[]",
            )
        )
        session.commit()

        with patch("core.scheduler._deliver") as mock_deliver:
            scheduler._fire_due_reminders(session, now)

        mock_deliver.assert_not_called()


class TestSchedulerEnabledGate:
    def test_defaults_false_in_test_env(self, monkeypatch):
        monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
        assert scheduler.scheduler_enabled() is False

    def test_explicit_true_overrides_test_default(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_ENABLED", "true")
        assert scheduler.scheduler_enabled() is True
