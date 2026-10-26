"""add account_merge audit table

Revision ID: a9f3c2d1e8b7
Revises: e2b4c6d8f012
Create Date: 2026-10-26 00:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9f3c2d1e8b7"
down_revision: str | Sequence[str] | None = "e2b4c6d8f012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_merge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_username", sa.String(length=32), nullable=False),
        sa.Column("target_username", sa.String(length=32), nullable=False),
        sa.Column("source_email", sa.String(length=320), nullable=True),
        sa.Column("target_email", sa.String(length=320), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("moved_counts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_user_id", name="uq_account_merge_source_user_id"),
    )
    op.create_index(op.f("ix_account_merge_id"), "account_merge", ["id"], unique=False)
    op.create_index(op.f("ix_account_merge_target_user_id"), "account_merge", ["target_user_id"], unique=False)
    op.create_index(op.f("ix_account_merge_actor_user_id"), "account_merge", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_account_merge_created_at"), "account_merge", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_account_merge_created_at"), table_name="account_merge")
    op.drop_index(op.f("ix_account_merge_actor_user_id"), table_name="account_merge")
    op.drop_index(op.f("ix_account_merge_target_user_id"), table_name="account_merge")
    op.drop_index(op.f("ix_account_merge_id"), table_name="account_merge")
    op.drop_table("account_merge")
