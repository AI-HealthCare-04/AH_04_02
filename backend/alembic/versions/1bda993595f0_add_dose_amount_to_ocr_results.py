"""add dose_amount to ocr_results

Revision ID: 1bda993595f0
Revises: e3bbed9f13e5
Create Date: 2026-07-24 19:15:37.903338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import

# revision identifiers, used by Alembic.
revision: str = '1bda993595f0'
down_revision: Union[str, Sequence[str], None] = 'e3bbed9f13e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # [2026-07-25] autogenerate가 NOT NULL을 기본값 없이 추가하려고 해서(이미 행이 있는
    # ocr_results에 적용하면 실패) server_default를 채운다 — b6b239b93696(total_days
    # 추가)와 동일한 이유. caregiver_patients.status 타입 표기 변경과
    # schedule_caregiver_alerts 인덱스 삭제는 이 변경과 무관한 autogenerate 노이즈라 뺐다.
    op.add_column(
        'ocr_results',
        sa.Column('dose_amount', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ocr_results', 'dose_amount')
