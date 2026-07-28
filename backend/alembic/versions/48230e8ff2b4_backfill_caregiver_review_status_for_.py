"""backfill caregiver review status for pre-existing completed records

Revision ID: 48230e8ff2b4
Revises: 2b030c4abcc2
Create Date: 2026-07-28 13:11:21.184872

[2026-07-28 버그수정] 43be3b2a7ff4가 caregiver_review_status 컬럼을 server_default='none'
으로 추가했는데, 그 시점에 이미 completed 상태였고 보호자·기관이 연결돼 있던 기존
처방전들은 "pending"이어야 정상인데도 전부 "none"으로 남았다 — 그 이후로 그 처방전들은
연결된 보호자·기관 화면(Records.tsx)에 "보호자 검토 대기" 배지가 영원히 뜨지 않는다
(신규 확인(POST /records/{id}/confirm) 시점 로직인 _initial_caregiver_review_status는
그 시점 이후 새로 완료되는 처방전에만 적용되고, 이미 존재하던 행은 소급 적용되지 않음).

이 마이그레이션은 그 값만 바로잡는다 — _initial_caregiver_review_status와 달리
RecordCorrectionNotice/푸시 알림은 다시 만들지 않는다(오래된 처방전에 대해 이제 와서
"새 처방전이 등록됐어요" 알림을 새로 보내면 오히려 혼란을 준다).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import

# revision identifiers, used by Alembic.
revision: str = '48230e8ff2b4'
down_revision: Union[str, Sequence[str], None] = '2b030c4abcc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            """
            UPDATE medical_records
            SET caregiver_review_status = 'pending'
            WHERE status = 'completed'
              AND deleted_at IS NULL
              AND caregiver_review_status = 'none'
              AND EXISTS (
                  SELECT 1 FROM caregiver_patients
                  WHERE caregiver_patients.patient_id = medical_records.patient_id
                    AND caregiver_patients.status != 'revoked'
              )
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    [2026-07-28] 이 백필은 편도(one-way)로만 다룬다 — 되돌리면, 이 마이그레이션 이후
    정상적인 흐름(신규 확인, request-correction 등)으로 "pending"이 된 행까지 구분 없이
    "none"으로 되돌려버려 오히려 데이터를 손상시킨다. 의도적으로 아무 것도 하지 않는다.
    """
    pass
