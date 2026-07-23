"""
scheduler.py — 복약 알림/놓침 감지 백그라운드 스케줄러 (신규, 2026-07-19, 담당: 김영혜)

REQ-026a(정시 알림) + REQ-026c(놓침 감지) + REQ-026d(third_party_needed 공동알림)를
구현한다. 팀이 이미 두 번(REQ-035, REQ-028/029) Redis/Celery를 명시적으로 거부하고
더 단순한 방식을 택한 전례를 따라, 별도 워커 프로세스 없이 FastAPI 앱 프로세스 안에서
도는 asyncio 루프 하나로 구현한다 — routers/*.py 전반의 `asyncio.to_thread(...)` 관례와
동일하게, 동기 SQLModel Session 작업은 to_thread로 감싸 이벤트 루프를 막지 않는다.

동시성 주의: 이 팀은 로컬 개발 서버 여러 대가 공유 Aiven MySQL DB 하나를 바라본다
(docs/shared-dev-db-setup.md) — 즉 "지금 이 틱을 처리한 게 나 하나뿐"이라고 가정할 수
없다. 그래서 "이미 처리했는지"의 진실 공급원은 스케줄러의 타이밍이 아니라
NotificationLog의 (schedule_id, due_date, time_slot, kind) UniqueConstraint다 —
두 서버가 같은 틱에 같은 알림을 동시에 처리하려 해도 DB가 한쪽만 통과시킨다.

알려진 한계(팀 공유 필요, 코멘트에도 명시):
- 서버 로컬 시간대만 가정한다(Patient/MedicationSchedule의 timezone 필드는 아직 안 씀).
- 배달 채널은 core/email.py(mock/smtp)뿐이다 — 프론트에 Web Push/FCM 인프라가 없다.
- 여러 서버가 동시에 이 루프를 돌리는 멀티워커 배포는 가정하지 않는다(각자 로컬에서
  스케줄러를 꺼둘 수 있게 SCHEDULER_ENABLED로 게이트만 해둠 — 실제 운영 배포시 재검토 필요).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta

from models import (
    Caregiver,
    CaregiverPatient,
    MedicationRecord,
    MedicationSchedule,
    NotificationLog,
    NotificationSetting,
    Patient,
)
from sqlmodel import Session, func, select

from core.database import engine
from core.email import send_email

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
# [2026-07-19] 스케줄러가 60초마다 도는데, "정시"를 정확히 그 초에 맞춰 잡을 수 없으니
# due_time 이후 이 창 안에 들어온 것까지는 아직 "정시 알림 대상"으로 본다. 창을 넘기면
# 그때부터는 _fire_due_reminders가 아니라 _mark_missed가 처리한다.
CATCH_UP_MINUTES = 10
# [2026-07-19] 정시를 이만큼 넘기고도 MedicationRecord에 오늘자 체크가 없으면 "놓침"으로
# 판정한다. Dashboard.tsx의 "아직이요"(clear_intake) 버튼이 오늘자 로그를 지우면 이
# 창이 다시 흐르기 시작하므로, 사용자가 그 버튼을 정시 임박 직전에 누르면 곧바로 다시
# missed 판정될 수 있다는 걸 알고 있다(라운드2 검토에서 지적된 한계, 별도 UX 개선 필요).
MISSED_AFTER_MINUTES = 60

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _schedule_runs_today(schedule: MedicationSchedule, today: date) -> bool:
    if not schedule.days_of_week:
        return True
    try:
        days = json.loads(schedule.days_of_week)
    except (TypeError, ValueError):
        logger.warning(
            "schedule %s의 days_of_week가 JSON이 아니라 건너뜁니다: %r",
            schedule.id, schedule.days_of_week,
        )
        return True
    return _WEEKDAY_KEYS[today.weekday()] in days


def _parse_time_slot(time_slot: str) -> tuple[int, int] | None:
    try:
        hour_str, minute_str = time_slot.split(":", 1)
        return int(hour_str), int(minute_str)
    except (ValueError, AttributeError):
        logger.warning("time_slot 형식이 잘못돼 건너뜁니다: %r", time_slot)
        return None


def _has_today_log(session: Session, schedule_id: int, today_str: str) -> bool:
    return (
        session.exec(
            select(MedicationRecord)
            .where(MedicationRecord.schedule_id == schedule_id)
            .where(func.date(MedicationRecord.taken_at) == today_str)
            .where(MedicationRecord.status.in_(["taken", "skipped"]))
        ).first()
        is not None
    )


def _already_logged(session: Session, schedule_id: int, due_date: str, time_slot: str, kind: str) -> bool:
    return (
        session.exec(
            select(NotificationLog)
            .where(NotificationLog.schedule_id == schedule_id)
            .where(NotificationLog.due_date == due_date)
            .where(NotificationLog.time_slot == time_slot)
            .where(NotificationLog.kind == kind)
        ).first()
        is not None
    )


def _recipients(session: Session, patient: Patient, schedule: MedicationSchedule) -> list[tuple[str, str]]:
    """(채널라벨, 이메일) 목록. 첫 연결(caregiver_patients 최초 1건)만 "주 보호자"로 취급한다.
    "최초 연결 = 주 보호자"는 임의의 단순화이며, 실제 주/부 보호자 구분 필드가 생기면
    바꿔야 한다(라운드2에서 확인된 한계, 팀 공유 필요).

    [2026-07-23 삭제] care_level(자가진단) 기반 "전원 알림" 분기를 제거했다 — 자가진단을 만드는
    화면이 없어 assessment가 항상 None이라 이 분기는 실질적으로 한 번도 탄 적이 없었다.

    [2026-07-19 round5 수정] schedule.caregiver_alert(monitoring_router.py 스케줄 생성/수정
    API에 이미 있는 "이 일정만 보호자에게 알릴지" per-schedule 토글)를 지금까지 전혀 참고하지
    않고 있었다 — 환자가 특정 약 일정에서 이 값을 False로 꺼도 스케줄러가 무시하고 보호자에게
    계속 알림을 보내던 실제 버그. False면 보호자 후보를 아예 안 만든다(환자 본인 몫은 그대로).
    """
    recipients: list[tuple[str, str]] = []
    if patient.email_opt_in and patient.email:
        recipients.append(("email:patient", patient.email))

    if not schedule.caregiver_alert:
        return recipients

    # [2026-07-19 round5 수정] order_by 없이는 "최초 연결"이 SQLite에서는 우연히 삽입 순서와
    # 같게 보이지만 SQL 표준상 보장되지 않는다 — 이 팀의 실제 dev/운영 DB는 MySQL이라(공유
    # Aiven DB) 백엔드마다 순서가 달라질 수 있다. id 오름차순으로 명시해 "최초 연결"이 어느
    # 백엔드에서도 실제로 최초 연결을 가리키도록 고정한다.
    # [2026-07-23 추가] status != "revoked" — 연결이 끊긴(또는 기관이 끊는 중인) 보호자에게
    # 계속 알림이 가던 걸 막는다. revocation_pending은 아직 실제로 끊긴 게 아니므로 포함한다.
    links = session.exec(
        select(CaregiverPatient)
        .where(CaregiverPatient.patient_id == patient.id)
        .where(CaregiverPatient.status != "revoked")
        .order_by(CaregiverPatient.id)
    ).all()
    if not links:
        return recipients

    for link in links[:1]:
        caregiver = session.get(Caregiver, link.caregiver_id)
        if caregiver and caregiver.email_opt_in and caregiver.email:
            recipients.append((f"email:caregiver:{caregiver.id}", caregiver.email))
    return recipients


def _same_slot_drug_names(session: Session, schedule: MedicationSchedule) -> list[str]:
    """같은 환자·같은 시간대(time_slot)에 걸린 다른 활성 일정들의 약품명 — 알림 한 통에서
    "이 시간에 뭘 먹어야 하는지" 전부 보여주기 위함(REQ 아님, 사용자 요청: 시간별 그룹핑).
    NotificationLog의 (schedule_id, ...) 유니크 제약/멱등성 로직은 그대로 두고, 메시지
    내용만 풍부하게 만든다 — 스케줄러당 발송 건수는 기존과 동일(일정당 1건)."""
    siblings = session.exec(
        select(MedicationSchedule)
        .where(MedicationSchedule.patient_id == schedule.patient_id)
        .where(MedicationSchedule.time_slot == schedule.time_slot)
        .where(MedicationSchedule.active == True)  # noqa: E712
    ).all()
    names = [s.drug_name for s in siblings if s.drug_name]
    # 자기 자신이 맨 앞에 오도록(다른 약 우선순위를 임의로 매기지 않기 위해 순서만 보정)
    if schedule.drug_name in names:
        names.remove(schedule.drug_name)
    return [schedule.drug_name, *names]


def _deliver(session: Session, schedule: MedicationSchedule, patient: Patient, kind: str) -> tuple[str, list[str]]:
    """opt-out(NotificationSetting.medication_reminder_enabled)을 존중한다 — 꺼져 있으면
    NotificationLog는 남기되(놓침 판정 로직이 알림 설정과 무관하게 계속 동작하도록)
    상태만 suppressed로 남기고 실제 발송은 하지 않는다.
    """
    setting = session.get(NotificationSetting, patient.id)
    enabled = setting.medication_reminder_enabled if setting else True
    if not enabled:
        return "suppressed", []

    recipients = _recipients(session, patient, schedule)
    if not recipients:
        return "sent", []

    verb = "복약 시간이에요" if kind == "reminder" else "복약을 놓치신 것 같아요"
    drug_names = _same_slot_drug_names(session, schedule)
    drug_list = ", ".join(drug_names)
    subject = f"[건강동행] {schedule.time_slot} {verb}"
    body = f"{schedule.time_slot}에 복용할 약: {drug_list} — {verb}. 앱에서 확인해 주세요."
    channels: list[str] = []
    for label, email in recipients:
        send_email(to=email, subject=subject, body=body)
        channels.append(label)
    return "sent", channels


def _fire_due_reminders(session: Session, now: datetime) -> None:
    today = now.date()
    today_str = today.isoformat()
    schedules = session.exec(
        select(MedicationSchedule).where(MedicationSchedule.active == True)  # noqa: E712
    ).all()

    for schedule in schedules:
        if not _schedule_runs_today(schedule, today):
            continue
        parsed = _parse_time_slot(schedule.time_slot)
        if parsed is None:
            continue
        hour, minute = parsed
        due_at = datetime.combine(today, datetime.min.time()).replace(hour=hour, minute=minute)
        if due_at > now or now - due_at > timedelta(minutes=CATCH_UP_MINUTES):
            continue  # 아직 정시 전이거나, catch-up 창을 이미 넘겨 _mark_missed 몫
        if _already_logged(session, schedule.id, today_str, schedule.time_slot, "reminder"):
            continue

        patient = session.get(Patient, schedule.patient_id)
        if not patient:
            continue

        # [2026-07-20 round2 수정, 박소정님 리뷰에서 발견] 원래는 _deliver()(실제 이메일
        # 발송)를 먼저 하고 나서 NotificationLog를 커밋했다 — 그러면 유니크 제약이 "로그
        # 행"의 중복은 막아도 "발송 자체"의 중복은 못 막는다. 두 서버가 거의 동시에 같은
        # 틱을 처리하면 둘 다 커밋 전이라 _already_logged 체크를 통과해 각자 이메일을 보낼
        # 수 있었다(로그는 하나만 남지만 이메일은 두 번 나감). placeholder 행을 먼저
        # insert+commit해서 유니크 제약으로 "이 틱을 처리할 프로세스"를 먼저 선점하고,
        # 그 커밋이 성공했을 때만(=선점에 성공했을 때만) 실제 발송한다.
        placeholder = NotificationLog(
            schedule_id=schedule.id,
            patient_id=schedule.patient_id,
            due_date=today_str,
            time_slot=schedule.time_slot,
            kind="reminder",
            status="pending",
            channels="[]",
        )
        session.add(placeholder)
        try:
            session.commit()
        except Exception:
            # 공유 DB에 서버 여러 대가 동시에 같은 틱을 처리하다 UniqueConstraint에 걸리는
            # 경우 — 이미 다른 프로세스가 선점했다는 뜻이니 발송하지 않고 조용히 넘어간다.
            session.rollback()
            continue

        status, channels = _deliver(session, schedule, patient, "reminder")
        placeholder.status = status
        placeholder.channels = json.dumps(channels)
        session.add(placeholder)
        session.commit()


def _mark_missed(session: Session, now: datetime) -> None:
    today = now.date()
    today_str = today.isoformat()
    schedules = session.exec(
        select(MedicationSchedule).where(MedicationSchedule.active == True)  # noqa: E712
    ).all()

    for schedule in schedules:
        if not _schedule_runs_today(schedule, today):
            continue
        parsed = _parse_time_slot(schedule.time_slot)
        if parsed is None:
            continue
        hour, minute = parsed
        due_at = datetime.combine(today, datetime.min.time()).replace(hour=hour, minute=minute)
        if now - due_at < timedelta(minutes=MISSED_AFTER_MINUTES):
            continue
        if _has_today_log(session, schedule.id, today_str):
            continue  # 이미 taken/skipped 등으로 체크됨
        if _already_logged(session, schedule.id, today_str, schedule.time_slot, "missed"):
            continue

        patient = session.get(Patient, schedule.patient_id)
        if not patient:
            continue

        # [2026-07-20 round2 수정] _fire_due_reminders와 동일한 이유 — placeholder를
        # 먼저 insert+commit해서 유니크 제약으로 선점한 프로세스만 실제 발송한다.
        placeholder = NotificationLog(
            schedule_id=schedule.id,
            patient_id=schedule.patient_id,
            due_date=today_str,
            time_slot=schedule.time_slot,
            kind="missed",
            status="pending",
            channels="[]",
        )
        session.add(placeholder)
        try:
            session.commit()
        except Exception:
            session.rollback()
            continue

        status, channels = _deliver(session, schedule, patient, "missed")
        placeholder.status = status
        placeholder.channels = json.dumps(channels)
        session.add(placeholder)
        session.commit()


def _tick() -> None:
    now = datetime.now()
    with Session(engine) as session:
        _fire_due_reminders(session, now)
        _mark_missed(session, now)


async def reminder_loop() -> None:
    """lifespan에서 asyncio.create_task로 띄우고, 종료 시 CancelledError로 멈춘다."""
    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            logger.exception("scheduler tick 중 처리되지 않은 예외 발생 — 다음 틱은 계속 진행")
        await asyncio.sleep(TICK_SECONDS)


def scheduler_enabled() -> bool:
    # [2026-07-19] 로컬 개발 시 팀원 각자가 원치 않으면 끌 수 있게 게이트만 둔다.
    # 테스트에서는 backend/tests/conftest.py가 이 값을 확인하지 않고 그대로 앱을 띄우므로,
    # 테스트 격리를 위해 test 환경에서는 기본 꺼짐으로 둔다.
    from core.database import APP_ENV

    default = "false" if APP_ENV == "test" else "true"
    return os.environ.get("SCHEDULER_ENABLED", default).lower() == "true"
