"""add broadcast model

Revision ID: c8f2a1b3d4e5
Revises: b7e3d9c1a5f2
Create Date: 2026-11-05 00:00:00.000000

Adds the Broadcast table for the Vault Radio Hour feature.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8f2a1b3d4e5"
down_revision: str | None = "d1f3a5c7e9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broadcast",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("audio_key", sa.String(length=512), nullable=True),
        sa.Column("trigger", sa.String(length=20), nullable=False, server_default="daily"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_broadcast_vault_id"), "broadcast", ["vault_id"], unique=False)
    op.create_index(
        op.f("ix_broadcast_created_at"), "broadcast", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_broadcast_created_at"), table_name="broadcast")
    op.drop_index(op.f("ix_broadcast_vault_id"), table_name="broadcast")
    op.drop_table("broadcast")
