"""add record_id to medication_schedules

Revision ID: 8064fd94bb1a
Revises: b6b239b93696
Create Date: 2026-07-20 10:26:16.073999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = '8064fd94bb1a'
down_revision: Union[str, Sequence[str], None] = 'b6b239b93696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('medication_schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('record_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_medication_schedules_record_id'), ['record_id'], unique=False)
        # [수정] autogenerate가 이름 없는(None) FK 제약을 만들어서 SQLite batch 모드에서
        # "Constraint must have a name" 에러가 났다 — 직접 이름을 지정해서 고침(PR #45의
        # patient_medication_id FK 마이그레이션과 동일한 이슈/해결).
        batch_op.create_foreign_key(
            'fk_medication_schedules_record_id', 'medical_records', ['record_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('medication_schedules', schema=None) as batch_op:
        batch_op.drop_constraint('fk_medication_schedules_record_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_medication_schedules_record_id'))
        batch_op.drop_column('record_id')
