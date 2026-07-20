"""medication_records: patient_medication_id nullable + confirmed_by 컬럼 추가

Revision ID: bfc3d4e49682
Revises: 9250cdf36945
Create Date: 2026-07-20 00:00:00.000000

[REQ-037 Phase2, 담당: 김영혜]
복약 체크인 기록을 medication_logs → medication_records 한 곳으로 일원화하기 위한 DDL.
- patient_medication_id를 nullable로 전환: OCR 기반 스케줄은 PatientMedication이 없어
  patient_medication_id를 채울 수 없다(불변식은 schedule_id/patient_medication_id 중
  최소 하나 — DB 제약이 아니라 애플리케이션 레벨).
- confirmed_by_type / confirmed_by_caregiver_id 추가: MedicationLog와 동일한 필드명/타입으로,
  "누가 체크했는지"(환자 본인 vs 보호자 대신)를 medication_records에서도 보존한다.

DML(medication_logs → medication_records 복사)은 이 DDL과 분리된 다음 마이그레이션에서 수행한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = 'bfc3d4e49682'
down_revision: Union[str, Sequence[str], None] = '66c32a201ba5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# [2026-07-20] medication_records에는 이름 없는 FK(patient_medication_id, schedule_id)가
# 이미 있는데, SQLite batch 모드가 테이블을 재생성하면서 그 FK들을 반영할 때 이름이 없으면
# "Constraint must have a name"으로 실패한다(6ec828d72e5f 주석과 동일한 이슈). 재생성 시
# 반영되는 제약에 결정적 이름을 붙여 이를 피한다.
NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s",
}


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table(
        'medication_records', schema=None, naming_convention=NAMING_CONVENTION
    ) as batch_op:
        batch_op.add_column(
            sa.Column('confirmed_by_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(sa.Column('confirmed_by_caregiver_id', sa.Integer(), nullable=True))
        batch_op.alter_column(
            'patient_medication_id', existing_type=sa.Integer(), nullable=True
        )
        batch_op.create_foreign_key(
            'fk_medication_records_confirmed_by_caregiver_id',
            'caregivers',
            ['confirmed_by_caregiver_id'],
            ['id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table(
        'medication_records', schema=None, naming_convention=NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            'fk_medication_records_confirmed_by_caregiver_id', type_='foreignkey'
        )
        # [주의] patient_medication_id를 다시 NOT NULL로 되돌린다 — 이 시점에 NULL 값이 있으면
        # (DML 마이그레이션이 이미 medication_logs를 옮겼다면) 실패할 수 있으므로, downgrade는
        # 반드시 DML 마이그레이션을 먼저 되돌린 상태(medication_records가 원래대로)에서 실행한다.
        batch_op.alter_column(
            'patient_medication_id', existing_type=sa.Integer(), nullable=False
        )
        batch_op.drop_column('confirmed_by_caregiver_id')
        batch_op.drop_column('confirmed_by_type')
