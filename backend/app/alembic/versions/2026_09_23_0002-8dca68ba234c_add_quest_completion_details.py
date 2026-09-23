"""add quest completion details

Revision ID: 8dca68ba234c
Revises: d5e6f7a8b9c0
Create Date: 2026-09-23 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8dca68ba234c"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Nullable with no backfill: NULL means "not claimed yet", which is the correct
    # state for every pre-existing row (see AGENTS.md data-bearing-columns rule).
    # completed_at is not derivable from return_completes_at, and granted rewards
    # were never stored, so there is nothing to backfill.
    op.add_column("vaultquestcompletionlink", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "vaultquestcompletionlink",
        sa.Column("granted_rewards", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vaultquestcompletionlink", "granted_rewards")
    op.drop_column("vaultquestcompletionlink", "completed_at")
