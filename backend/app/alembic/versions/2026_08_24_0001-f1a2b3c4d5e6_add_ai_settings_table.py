"""add_ai_settings_table

Revision ID: f1a2b3c4d5e6
Revises: 9f8e7d6c5b4a3
Create Date: 2026-08-24 00:01:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "9f8e7d6c5b4a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("base_url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("gateway_route", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_settings_id"), "ai_settings", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_settings_id"), table_name="ai_settings")
    op.drop_table("ai_settings")
