"""core/audit.py — audit_logs 기록 헬퍼 (REQ-081, 최소 버전).

monitoring_router.py의 update_patient/update_schedule이 커밋 직전에 호출해, 실제로
바뀐 필드만 before/after로 남긴다. 조회 화면은 아직 없다 — 이번 티켓 범위는 "누가
언제 무엇을 바꿨는지 DB에 남기는 것"까지다.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from models import AuditLog
from sqlmodel import Session

from core.dependencies import Actor

# [주의] name/phone은 Patient/Caregiver에서 암호화 저장되는 PII다 — 이 값을 그대로
# before/after에 남기면 audit_logs가 암호화 보호 없이 평문 PII를 들고 있는 새로운
# 유출 경로가 된다. 값 대신 변경 여부만 "***"로 남긴다.
SENSITIVE_FIELDS = {"name", "phone"}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def record_audit_log(
    session: Session,
    table_name: str,
    record_id: int,
    actor: Actor,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """before/after 중 실제로 값이 달라진 필드만 골라 기록한다 — 값이 하나도 안
    바뀌었으면(같은 값으로 덮어쓴 PATCH 등) 로그를 남기지 않는다."""
    changed_before: dict[str, Any] = {}
    changed_after: dict[str, Any] = {}
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value == new_value:
            continue
        if key in SENSITIVE_FIELDS:
            changed_before[key] = "***"
            changed_after[key] = "***"
        else:
            changed_before[key] = _json_safe(old_value)
            changed_after[key] = _json_safe(new_value)

    if not changed_after:
        return

    role, subject = actor
    session.add(
        AuditLog(
            table_name=table_name,
            record_id=record_id,
            actor_id=subject.id,
            actor_role=role,
            before=json.dumps(changed_before, ensure_ascii=False),
            after=json.dumps(changed_after, ensure_ascii=False),
        )
    )
