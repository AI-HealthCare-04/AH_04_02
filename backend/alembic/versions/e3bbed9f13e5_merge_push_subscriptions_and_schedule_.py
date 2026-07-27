"""merge push_subscriptions and schedule_caregiver_alerts branches

Revision ID: e3bbed9f13e5
Revises: 0c197cae2268, 405992c665ba
Create Date: 2026-07-24 16:54:11.407590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = 'e3bbed9f13e5'
down_revision: Union[str, Sequence[str], None] = ('0c197cae2268', '405992c665ba')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
