"""add gender to patients

Revision ID: 3aea0a9d3604
Revises: 3a098c58f9f2
Create Date: 2026-07-22 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '3aea0a9d3604'
down_revision: Union[str, Sequence[str], None] = '3a098c58f9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('patients', sa.Column('gender', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('patients', 'gender')
