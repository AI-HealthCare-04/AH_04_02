"""add needs_caregiver_alert to patients (REQ-007a)

Revision ID: c3d5f9a1e082
Revises: a1f3e8b2c047
Create Date: 2026-07-20 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "c3d5f9a1e082"
down_revision = "a1f3e8b2c047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("needs_caregiver_alert", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("patients", "needs_caregiver_alert")