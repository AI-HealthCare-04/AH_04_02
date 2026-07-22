"""add invited_phone_hash to invitations

Revision ID: 3a098c58f9f2
Revises: c3a413343157
Create Date: 2026-07-22 03:15:00.000000

[2026-07-22 정정] down_revision이 원래 4ebb3160427e를 가리키고 있었으나, 그 리비전은
커밋된 적 없는 로컬 워킹 디렉토리 전용 파일이라(팀원 PR 리뷰로 발견) fresh checkout에서
`alembic upgrade head`가 KeyError로 깨졌다 — 이 PR이 갈라져 나온 시점 dev의 실제 head인
c3a413343157로 정정한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '3a098c58f9f2'
down_revision: Union[str, Sequence[str], None] = 'c3a413343157'
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
