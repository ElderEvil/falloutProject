"""add quest return leg

Revision ID: d5e6f7a8b9c0
Revises: b3c4d5e6f7a8
Create Date: 2026-09-23 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Nullable with no backfill: NULL means "not travelling", which is the correct
    # state for every pre-existing row (see AGENTS.md data-bearing-columns rule).
    op.add_column("vaultquestcompletionlink", sa.Column("return_started_at", sa.DateTime(), nullable=True))
    op.add_column("vaultquestcompletionlink", sa.Column("return_completes_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("vaultquestcompletionlink", "return_completes_at")
    op.drop_column("vaultquestcompletionlink", "return_started_at")