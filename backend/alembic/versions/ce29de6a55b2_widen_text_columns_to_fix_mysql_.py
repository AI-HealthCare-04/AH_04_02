"""widen text columns to fix mysql varchar255 truncation

Revision ID: ce29de6a55b2
Revises: 7d681562a9e0
Create Date: 2026-07-16 17:28:10.304494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import

# revision identifiers, used by Alembic.
revision: str = 'ce29de6a55b2'
down_revision: Union[str, Sequence[str], None] = '7d681562a9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # [수정] autogenerate가 만든 op.alter_column()을 그대로 두면 SQLite(로컬 기본 환경)에서
    # "near ALTER: syntax error"로 실행 자체가 실패한다 — SQLite는 ALTER COLUMN을 지원하지
    # 않아 batch 모드(테이블 재생성)로 우회해야 한다(다른 마이그레이션들과 동일한 관례).
    # 또한 autogenerate가 뽑아낸 mysql.VARCHAR(collation='utf8mb4_unicode_ci', ...)를 그대로
    # 두면, downgrade에서 이 타입으로 테이블을 재생성할 때 SQLite가 그 MySQL 전용 collation
    # 이름을 그대로 해석하려다 "no such collation sequence"로 또 실패한다 — 다른 VARCHAR
    # 컬럼들처럼 dialect 중립적인 sa.String(255)로 바꿔서 양쪽 DB 모두에서 동작하게 한다.
    with op.batch_alter_table('guide_results', schema=None) as batch_op:
        batch_op.alter_column('medication_guide',
                   existing_type=sa.String(length=255),
                   type_=sa.Text(),
                   existing_nullable=False)
        batch_op.alter_column('lifestyle_guide',
                   existing_type=sa.String(length=255),
                   type_=sa.Text(),
                   existing_nullable=False)
        batch_op.alter_column('source_refs',
                   existing_type=sa.String(length=255),
                   type_=sa.Text(),
                   nullable=True)

    with op.batch_alter_table('medical_records', schema=None) as batch_op:
        batch_op.alter_column('raw_text',
                   existing_type=sa.String(length=255),
                   type_=sa.Text(),
                   existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('medical_records', schema=None) as batch_op:
        batch_op.alter_column('raw_text',
                   existing_type=sa.Text(),
                   type_=sa.String(length=255),
                   existing_nullable=True)

    with op.batch_alter_table('guide_results', schema=None) as batch_op:
        batch_op.alter_column('source_refs',
                   existing_type=sa.Text(),
                   type_=sa.String(length=255),
                   nullable=False)
        batch_op.alter_column('lifestyle_guide',
                   existing_type=sa.Text(),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        batch_op.alter_column('medication_guide',
                   existing_type=sa.Text(),
                   type_=sa.String(length=255),
                   existing_nullable=False)
