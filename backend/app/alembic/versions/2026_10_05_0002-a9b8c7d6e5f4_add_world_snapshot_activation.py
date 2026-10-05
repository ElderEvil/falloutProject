"""add world snapshot activation pointer

Revision ID: a9b8c7d6e5f4
Revises: 862c04111ec1
Create Date: 2026-10-05 00:02:00.000000

Adds the explicit one-shared-world selection to ``worldsnapshot``: an
``is_active`` flag (default false for every existing row, which is the correct
"no world activated yet" state and needs no backfill) plus an ``activated_at``
audit timestamp. A partial unique index on ``world_id`` where ``is_active`` is
set makes "at most one active snapshot per world" a database guarantee, so a
stored candidate is never activated implicitly.

Additive only: no data is removed or rewritten, and ``downgrade()`` drops the
index and columns without touching snapshot payloads.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "862c04111ec1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "worldsnapshot",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("worldsnapshot", sa.Column("activated_at", sa.DateTime(), nullable=True))
    op.create_index(
        "uq_worldsnapshot_active_world",
        "worldsnapshot",
        ["world_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(op.f("ix_worldsnapshot_is_active"), "worldsnapshot", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_worldsnapshot_is_active"), table_name="worldsnapshot")
    op.drop_index("uq_worldsnapshot_active_world", table_name="worldsnapshot")
    op.drop_column("worldsnapshot", "activated_at")
    op.drop_column("worldsnapshot", "is_active")
