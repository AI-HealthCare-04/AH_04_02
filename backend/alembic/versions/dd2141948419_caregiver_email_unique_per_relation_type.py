"""caregiver email unique per relation type

Revision ID: dd2141948419
Revises: 16bd8c597acb
Create Date: 2026-07-23 14:48:49.592794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = 'dd2141948419'
down_revision: Union[str, Sequence[str], None] = '16bd8c597acb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """caregivers.email의 DB 유니크 제약을 제거한다 — phone_hash와 동일하게 relation_type
    (역할)끼리만 중복을 막도록 애플리케이션 레벨(monitoring_router.py)에서 검사한다.
    같은 사람이 보호자(가족)이면서 동시에 기관(요양보호사 등) 소속일 수 있어, 테이블
    전체 유니크로는 이 조합을 표현할 수 없다."""
    with op.batch_alter_table('caregivers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_caregivers_email'))
        batch_op.create_index(batch_op.f('ix_caregivers_email'), ['email'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('caregivers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_caregivers_email'))
        batch_op.create_index(batch_op.f('ix_caregivers_email'), ['email'], unique=True)
