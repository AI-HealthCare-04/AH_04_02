"""merge pinned + invited_phone_hash branches

Revision ID: 152860ef0223
Revises: 4ebb3160427e, 3aea0a9d3604
Create Date: 2026-07-22 14:05:33.829334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = '152860ef0223'
down_revision: Union[str, Sequence[str], None] = ('4ebb3160427e', '3aea0a9d3604')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
