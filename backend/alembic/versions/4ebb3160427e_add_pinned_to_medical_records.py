"""add pinned to medical_records

Revision ID: 4ebb3160427e
Revises: c3a413343157
Create Date: 2026-07-21 16:09:41.806476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4ebb3160427e'
down_revision: Union[str, Sequence[str], None] = 'c3a413343157'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# [2026-07-21] autogenerate가 caregiver_patients.status의 VARCHAR(50) ↔ AutoString
# 타입 표기 차이도 같이 잡아냈는데, 실제 DB에서는 둘 다 같은 VARCHAR라 순수 노이즈다
# (진짜 DDL 아님) — pinned 컬럼 추가 하나만 남기고 제거함.


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('medical_records', sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('medical_records', 'pinned')
