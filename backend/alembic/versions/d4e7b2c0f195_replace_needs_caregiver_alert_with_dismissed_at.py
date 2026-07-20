"""replace needs_caregiver_alert bool with caregiver_alert_dismissed_at datetime (REQ-007a)

Revision ID: d4e7b2c0f195
Revises: c3d5f9a1e082
Create Date: 2026-07-20 13:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d4e7b2c0f195"
down_revision = "c3d5f9a1e082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("patients", "needs_caregiver_alert")
    op.add_column(
        "patients",
        sa.Column("caregiver_alert_dismissed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patients", "caregiver_alert_dismissed_at")
    op.add_column(
        "patients",
        sa.Column("needs_caregiver_alert", sa.Boolean(), nullable=False, server_default="0"),
    )