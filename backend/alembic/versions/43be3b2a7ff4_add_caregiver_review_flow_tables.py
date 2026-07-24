"""add caregiver review flow tables

Revision ID: 43be3b2a7ff4
Revises: 1bda993595f0
Create Date: 2026-07-24 19:55:27.780776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import

# revision identifiers, used by Alembic.
revision: str = '43be3b2a7ff4'
down_revision: Union[str, Sequence[str], None] = '1bda993595f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('record_correction_notices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipient_role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('record_id', sa.Integer(), nullable=False),
    sa.Column('event', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['record_id'], ['medical_records.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('medication_field_flags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ocr_result_id', sa.Integer(), nullable=False),
    sa.Column('field_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('corrected', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('corrected_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['ocr_result_id'], ['ocr_results.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # [2026-07-25] autogenerate가 NOT NULL을 기본값 없이 추가하려고 해서(이미 행이 있는
    # medical_records에 적용하면 실패) server_default를 채운다 — b6b239b93696과 동일한
    # 이유. caregiver_patients.status 타입 표기 변경과 schedule_caregiver_alerts 인덱스
    # 삭제는 이 변경과 무관한 autogenerate 노이즈라 뺐다.
    op.add_column(
        'medical_records',
        sa.Column('caregiver_review_status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='none'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('medical_records', 'caregiver_review_status')
    op.drop_table('medication_field_flags')
    op.drop_table('record_correction_notices')
