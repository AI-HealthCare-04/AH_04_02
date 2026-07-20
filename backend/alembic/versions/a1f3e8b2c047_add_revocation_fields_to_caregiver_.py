"""add revocation fields to caregiver_patients (REQ-004)

Revision ID: a1f3e8b2c047
Revises: d9616a377d8c
Create Date: 2026-07-20 11:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1f3e8b2c047"
down_revision = "9250cdf36945"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "caregiver_patients",
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
    )
    op.add_column(
        "caregiver_patients",
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "caregiver_patients",
        sa.Column("revocation_requested_by", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("caregiver_patients", "revocation_requested_by")
    op.drop_column("caregiver_patients", "revoked_at")
    op.drop_column("caregiver_patients", "status")