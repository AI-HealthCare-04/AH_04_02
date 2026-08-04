"""add missing indexes for slow queries (notification_logs.fired_at/kind, medication_records.taken_at)

Revision ID: 866990c81efe
Revises: 9f6b1c2d3e4f
Create Date: 2026-08-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import

# revision identifiers, used by Alembic.
revision: str = '866990c81efe'
down_revision: Union[str, Sequence[str], None] = '9f6b1c2d3e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    [2026-08-03, perf] /monitoring/schedules, /monitoring/logs가 배포 환경(Aiven MySQL)에서
    4~11초씩 걸리던 원인을 조사하면서, medication_records.taken_at과 notification_logs.kind/
    fired_at에 인덱스가 전혀 없다는 걸 확인했다(로컬 MySQL로 152,068건/25,271건 규모 합성
    데이터를 만들어 EXPLAIN으로 검증 — PR 본문 참고).

    patient_id/schedule_id/caregiver_id 같은 FK 컬럼은 MySQL(InnoDB)이 FOREIGN KEY 제약에
    자동으로 인덱스를 만들어주므로(SHOW CREATE TABLE로 확인) 이번 마이그레이션에서 뺐다 —
    추가했다면 같은 컬럼에 중복 인덱스가 생겨 조회엔 도움이 안 되고 쓰기 비용만 늘었을 것.
    """
    op.create_index(
        op.f('ix_medication_records_taken_at'), 'medication_records', ['taken_at'], unique=False
    )
    op.create_index(
        op.f('ix_notification_logs_fired_at'), 'notification_logs', ['fired_at'], unique=False
    )
    op.create_index(op.f('ix_notification_logs_kind'), 'notification_logs', ['kind'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_notification_logs_kind'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_fired_at'), table_name='notification_logs')
    op.drop_index(op.f('ix_medication_records_taken_at'), table_name='medication_records')