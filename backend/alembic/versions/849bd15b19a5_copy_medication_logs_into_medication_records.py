"""medication_logs → medication_records 데이터 복사 (forward-only)

Revision ID: 849bd15b19a5
Revises: bfc3d4e49682
Create Date: 2026-07-20 00:00:01.000000

[REQ-037 Phase2, 담당: 김영혜]
복약 체크인 기록을 medication_records 한 곳으로 일원화하기 위해, 기존 라이브 테이블
medication_logs의 모든 행을 medication_records로 복사한다(DDL은 앞선 bfc3d4e49682에서 완료).

매핑:
- schedule_id           ← 그대로
- patient_medication_id ← NULL (medication_logs에는 대응 개념이 없음)
- status                ← 그대로 (medication_logs는 taken/skipped만 존재)
- taken_at              ← checked_at
  (이 마이그레이션 이후 taken_at은 '상태가 확정된 시각(taken이든 skipped든)'을 의미하도록 재정의됨)
- scheduled_at          ← NULL (medication_records.scheduled_at은 nullable)
- created_at/updated_at ← checked_at
- memo                  ← note
- confirmed_by_type / confirmed_by_caregiver_id ← 그대로
- verification_method   ← confirmed_by_type == "caregiver"면 "caregiver", 아니면 "self_report"

[안전장치] scripts/migrate_local_data.py와 동일한 관례:
- 배치(500건) 단위 executemany로 적재한다.
- idempotent: 이미 옮겨진 행((schedule_id, taken_at)이 patient_medication_id IS NULL로 존재)은
  건너뛴다 — 부분 실패 후 재적용하거나 수동 재실행해도 중복 적재되지 않는다.
- medication_logs는 이 마이그레이션에서 지우지 않는다(DROP 없음 — 다음 스프린트 별도 PR).

[downgrade — forward-only, no-op]
patient_medication_id IS NULL을 "이 마이그레이션이 넣은 행"의 표식으로 쓸 수 없다 — 배포 후
routers/monitoring_router.py:check_intake가 만드는 모든 신규 체크인도 patient_medication_id를
NULL로 남긴다(OCR 기반 스케줄엔 대응하는 PatientMedication이 없으므로). 즉 배포 이후 실제
사용자가 쌓은 medication_records를 "이 마이그레이션이 넣은 복사본"과 구분할 방법이 없어서,
그 조건으로 삭제하면 실데이터가 함께 지워진다. 그래서 downgrade()는 아무것도 지우지 않는
no-op이다 — 이 DML은 진짜로 forward-only다. (뒤이은 bfc3d4e49682의 downgrade가 다시
patient_medication_id를 NOT NULL로 되돌리려 하면 NULL 행이 남아있는 한 실패하는데, 이건
의도된 동작이다 — 그 시점에 실데이터를 지울지 보존할지는 사람이 직접 판단해야 한다.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401 — 프로젝트 마이그레이션 관례상 항상 import


# revision identifiers, used by Alembic.
revision: str = '849bd15b19a5'
down_revision: Union[str, Sequence[str], None] = 'bfc3d4e49682'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BATCH_SIZE = 500

_medication_logs = sa.table(
    "medication_logs",
    sa.column("id", sa.Integer),
    sa.column("schedule_id", sa.Integer),
    sa.column("status", sa.String),
    sa.column("checked_at", sa.DateTime),
    sa.column("note", sa.String),
    sa.column("confirmed_by_type", sa.String),
    sa.column("confirmed_by_caregiver_id", sa.Integer),
)

_medication_records = sa.table(
    "medication_records",
    sa.column("patient_medication_id", sa.Integer),
    sa.column("schedule_id", sa.Integer),
    sa.column("scheduled_at", sa.DateTime),
    sa.column("taken_at", sa.DateTime),
    sa.column("status", sa.String),
    sa.column("verification_method", sa.String),
    sa.column("evidence_image_url", sa.String),
    sa.column("memo", sa.String),
    sa.column("confirmed_by_type", sa.String),
    sa.column("confirmed_by_caregiver_id", sa.Integer),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    logs = bind.execute(
        sa.select(
            _medication_logs.c.schedule_id,
            _medication_logs.c.status,
            _medication_logs.c.checked_at,
            _medication_logs.c.note,
            _medication_logs.c.confirmed_by_type,
            _medication_logs.c.confirmed_by_caregiver_id,
        )
    ).mappings().all()

    # 이미 옮겨진 행((schedule_id, taken_at) 조합)을 미리 모아 재적재를 막는다.
    already = set(
        bind.execute(
            sa.select(
                _medication_records.c.schedule_id, _medication_records.c.taken_at
            ).where(_medication_records.c.patient_medication_id.is_(None))
        ).all()
    )

    batch: list[dict] = []
    for log in logs:
        key = (log["schedule_id"], log["checked_at"])
        if key in already:
            continue
        already.add(key)
        verification_method = (
            "caregiver" if log["confirmed_by_type"] == "caregiver" else "self_report"
        )
        batch.append(
            {
                "patient_medication_id": None,
                "schedule_id": log["schedule_id"],
                "scheduled_at": None,
                "taken_at": log["checked_at"],
                "status": log["status"],
                "verification_method": verification_method,
                "evidence_image_url": None,
                "memo": log["note"],
                "confirmed_by_type": log["confirmed_by_type"],
                "confirmed_by_caregiver_id": log["confirmed_by_caregiver_id"],
                "created_at": log["checked_at"],
                "updated_at": log["checked_at"],
            }
        )
        if len(batch) >= BATCH_SIZE:
            bind.execute(sa.insert(_medication_records), batch)
            batch = []

    if batch:
        bind.execute(sa.insert(_medication_records), batch)


def downgrade() -> None:
    """No-op (forward-only — 위 docstring 참고). patient_medication_id IS NULL로는 이
    마이그레이션이 넣은 행과 배포 후 실사용자가 쌓은 행을 구분할 수 없어, 삭제 자체가
    안전하지 않다. 원본 medication_logs는 애초에 그대로 남아있으니 데이터 손실은 없다."""
