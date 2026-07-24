"""generalize revocation_notices into event-based relation notices

Revision ID: a313929ff868
Revises: bee05b2591cb
Create Date: 2026-07-24 12:12:26.437588

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'a313929ff868'
down_revision: str | Sequence[str] | None = 'bee05b2591cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """approved: bool -> event: str ("revocation_approved"/"revocation_rejected"), 기존 행이
    있으면 backfill한 뒤에 approved 컬럼을 지운다(현재 shared dev DB엔 행이 없지만 방어적으로)."""
    op.add_column('revocation_notices', sa.Column('event', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.execute(
        "UPDATE revocation_notices SET event = CASE WHEN approved = 1 "
        "THEN 'revocation_approved' ELSE 'revocation_rejected' END"
    )
    with op.batch_alter_table('revocation_notices', schema=None) as batch_op:
        batch_op.alter_column('event', existing_type=sqlmodel.sql.sqltypes.AutoString(), nullable=False)
        batch_op.drop_column('approved')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('revocation_notices', sa.Column('approved', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True))
    op.execute("UPDATE revocation_notices SET approved = (event = 'revocation_approved')")
    with op.batch_alter_table('revocation_notices', schema=None) as batch_op:
        batch_op.alter_column('approved', existing_type=mysql.TINYINT(display_width=1), nullable=False)
        batch_op.drop_column('event')
