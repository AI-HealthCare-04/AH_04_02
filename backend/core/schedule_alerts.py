"""core/schedule_alerts.py — "이 복약 일정이 실제로 누구에게 알림을 보내는가"를 계산하는
공용 로직 (2026-07-24 신규).

routers/monitoring_router.py(Schedule.tsx API 응답의 alert_caregiver_ids)와
core/scheduler.py(실제 이메일 발송 대상)가 반드시 같은 계산을 공유해야 화면에 뜨는
이름과 실제 발송 대상이 어긋나지 않는다 — 한쪽만 고치면 "체크박스엔 없는데 알림은
가는" 또는 그 반대의 불일치가 생긴다.
"""
from __future__ import annotations

from models import CaregiverPatient, MedicationSchedule, ScheduleCaregiverAlert
from sqlmodel import Session, select


def linked_caregiver_ids(patient_id: int, session: Session) -> list[int]:
    """이 환자와 현재 연결된(해제되지 않은) caregiver id 전체 — 알림 선택 UI의 후보
    목록이자, 일정에 명시적 선택이 없을 때의 기본 수신자 집합이기도 하다."""
    return list(
        session.exec(
            select(CaregiverPatient.caregiver_id)
            .where(CaregiverPatient.patient_id == patient_id)
            .where(CaregiverPatient.status != "revoked")
            .order_by(CaregiverPatient.id)
        ).all()
    )


def effective_alert_caregiver_ids(schedule: MedicationSchedule, session: Session) -> list[int]:
    """이 일정이 실제로 알림을 보낼 caregiver id 목록.

    caregiver_alert가 꺼져 있으면 무조건 빈 목록(기존 kill switch 유지). 명시적으로
    고른 행(ScheduleCaregiverAlert)이 있으면 그 목록만 — 예전엔 "가장 먼저 연결된
    caregiver 1명"에게만 갔는데(임의의 단순화), 이제는 환자·보호자가 직접 고른 사람만
    받는다. 하나도 명시적으로 고른 적 없으면(과거 데이터, 또는 아직 새 체크박스 UI를
    거치지 않은 일정) 연결된 caregiver 전원에게 보낸다 — 아무도 못 받는 것보다 안전한
    기본값이자, 기존 "첫 연결자만" 제한을 오히려 완화하는 방향이다.

    [주의] "선택한 행이 0개"와 "한 번도 선택한 적 없음"을 이 함수는 구분하지 못한다 —
    체크박스를 전부 해제해서 명시적으로 "아무에게도 안 보낸다"를 표현하려면 반드시
    caregiver_alert=False도 같이 꺼야 한다(위 kill switch가 우선 적용된다).
    Schedule.tsx의 save()가 실제로 그렇게 두 값을 항상 같이 보낸다."""
    if not schedule.caregiver_alert:
        return []
    selected = list(
        session.exec(
            select(ScheduleCaregiverAlert.caregiver_id).where(
                ScheduleCaregiverAlert.schedule_id == schedule.id
            )
        ).all()
    )
    if selected:
        return selected
    return linked_caregiver_ids(schedule.patient_id, session)
