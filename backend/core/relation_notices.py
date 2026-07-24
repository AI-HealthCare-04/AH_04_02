"""core/relation_notices.py — 환자-보호자 관계에 생긴 일(연결/해제/해제 승인·거부 결과)을
상대에게 알리는 RelationNotice 기록 헬퍼.

care_router.py(초대 수락, 해제 승인/거부)와 monitoring_router.py(즉시 해제)가 공용으로
쓴다 — 두 라우터 사이 순환 import를 피하려고 core에 둔다.
"""
from __future__ import annotations

from models import RelationNotice
from sqlmodel import Session


def create_relation_notice(
    session: Session,
    *,
    recipient_role: str,
    recipient_id: int,
    patient_id: int,
    patient_name: str,
    counterpart_name: str,
    event: str,
    reason: str | None = None,
) -> None:
    """호출자가 session.commit()까지 책임진다 — 링크 생성/해제와 한 트랜잭션으로 묶는다."""
    session.add(
        RelationNotice(
            recipient_role=recipient_role,
            recipient_id=recipient_id,
            patient_id=patient_id,
            patient_name=patient_name,
            counterpart_name=counterpart_name,
            event=event,
            reason=reason,
        )
    )
