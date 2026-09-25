"""add map point clear state

Revision ID: e7f8a9b0c1d2
Revises: c6f1a2b3d4e5
Create Date: 2026-09-26 00:00:00.000000

Phase 1 of issue 772: per-point clear state on ``vaultlocationstate``.
Three additive columns; no backfill is needed because NULL / 0 is the
correct "never cleared" state for every existing row — it is not a
silently-wrong benign default (a real clear always sets a timestamp and
increments the count, so the default is distinguishable from data).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "c6f1a2b3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vaultlocationstate", sa.Column("cleared_at", sa.DateTime(), nullable=True))
    op.add_column("vaultlocationstate", sa.Column("reclear_available_at", sa.DateTime(), nullable=True))
    op.add_column("vaultlocationstate", sa.Column("clear_count", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("vaultlocationstate", "clear_count")
    op.drop_column("vaultlocationstate", "reclear_available_at")
    op.drop_column("vaultlocationstate", "cleared_at")
