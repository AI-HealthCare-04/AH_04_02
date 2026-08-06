"""store prescription images in database

Revision ID: 9f6b1c2d3e4f
Revises: 46e60aff6632
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "9f6b1c2d3e4f"
down_revision: str | Sequence[str] | None = "46e60aff6632"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    image_binary = sa.LargeBinary().with_variant(mysql.MEDIUMBLOB(), "mysql")
    op.create_table(
        "medical_record_images",
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("content", image_binary, nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["medical_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )


def downgrade() -> None:
    op.drop_table("medical_record_images")
