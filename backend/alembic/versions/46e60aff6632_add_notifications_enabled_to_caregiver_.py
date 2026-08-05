"""add notifications_enabled to caregiver_patients

Revision ID: 46e60aff6632
Revises: 48230e8ff2b4
Create Date: 2026-07-30 18:22:13.762021

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '46e60aff6632'
down_revision: Union[str, Sequence[str], None] = '48230e8ff2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default를 직접 채운다 — autogenerate가 안 채워줘서 기존 행에 NOT NULL 컬럼을
    # 추가하면 실패한다(docs/etc/shared-dev-db-setup.md 관례). 기존 관계는 전부 알림 받는 중이던
    # 걸로 취급(True)한다 — 이 기능이 생기기 전이라 실제로도 다 받고 있었음.
    op.add_column(
        'caregiver_patients',
        sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('caregiver_patients', 'notifications_enabled')
