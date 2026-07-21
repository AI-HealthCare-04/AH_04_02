"""add invited_phone_hash to invitations

Revision ID: 3a098c58f9f2
Revises: 4ebb3160427e
Create Date: 2026-07-22 03:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '3a098c58f9f2'
down_revision: Union[str, Sequence[str], None] = '4ebb3160427e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('invitations', sa.Column('invited_phone_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(op.f('ix_invitations_invited_phone_hash'), 'invitations', ['invited_phone_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_invitations_invited_phone_hash'), table_name='invitations')
    op.drop_column('invitations', 'invited_phone_hash')
