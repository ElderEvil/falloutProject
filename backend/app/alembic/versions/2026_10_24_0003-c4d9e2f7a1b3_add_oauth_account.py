"""add oauth_account

Revision ID: c4d9e2f7a1b3
Revises: b0a1c2d3e4f5
Create Date: 2026-10-24 00:03:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d9e2f7a1b3"
down_revision: str | Sequence[str] | None = "b0a1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_user_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_account_provider_provider_user_id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_account_user_provider"),
    )
    op.create_index(op.f("ix_oauth_account_id"), "oauth_account", ["id"], unique=False)
    op.create_index(op.f("ix_oauth_account_provider"), "oauth_account", ["provider"], unique=False)
    op.create_index(op.f("ix_oauth_account_provider_user_id"), "oauth_account", ["provider_user_id"], unique=False)
    op.create_index(op.f("ix_oauth_account_user_id"), "oauth_account", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_oauth_account_user_id"), table_name="oauth_account")
    op.drop_index(op.f("ix_oauth_account_provider_user_id"), table_name="oauth_account")
    op.drop_index(op.f("ix_oauth_account_provider"), table_name="oauth_account")
    op.drop_index(op.f("ix_oauth_account_id"), table_name="oauth_account")
    op.drop_table("oauth_account")
