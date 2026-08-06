"""make invitations.patient_id nullable

Revision ID: c3a413343157
Revises: 849bd15b19a5
Create Date: 2026-07-20 13:25:41.682310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = 'c3a413343157'
down_revision: Union[str, Sequence[str], None] = '849bd15b19a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — 보호자→환자 초대(REQ-037)는 수락 전까지 patient가 없어 nullable로 전환."""
    with op.batch_alter_table("invitations", schema=None) as batch_op:
        batch_op.alter_column(
            "patient_id", existing_type=sa.Integer(), nullable=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("invitations", schema=None) as batch_op:
        batch_op.alter_column(
            "patient_id", existing_type=sa.Integer(), nullable=False
        )
