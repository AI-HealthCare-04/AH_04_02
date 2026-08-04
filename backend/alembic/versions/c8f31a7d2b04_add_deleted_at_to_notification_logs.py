"""add deleted_at to notification logs

Revision ID: c8f31a7d2b04
Revises: 866990c81efe
Create Date: 2026-08-04 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8f31a7d2b04"
down_revision: str | Sequence[str] | None = "866990c81efe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notification_logs", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(
        op.f("ix_notification_logs_deleted_at"),
        "notification_logs",
        ["deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_deleted_at"), table_name="notification_logs")
    op.drop_column("notification_logs", "deleted_at")
