"""add suggested_value to medication_field_flags

Revision ID: 2b030c4abcc2
Revises: 43be3b2a7ff4
Create Date: 2026-07-25 07:25:27.188443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import

# revision identifiers, used by Alembic.
revision: str = '2b030c4abcc2'
down_revision: Union[str, Sequence[str], None] = '43be3b2a7ff4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # [2026-07-25] autogenerate가 NOT NULL을 기본값 없이 추가하려고 해서(이미 행이 있는
    # medication_field_flags에 적용하면 실패) server_default를 채운다 — b6b239b93696과
    # 동일한 이유. caregiver_patients.status 타입 표기 변경과 schedule_caregiver_alerts
    # 인덱스 삭제는 이 변경과 무관한 autogenerate 노이즈라 뺐다.
    op.add_column(
        'medication_field_flags',
        sa.Column('suggested_value', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('medication_field_flags', 'suggested_value')
