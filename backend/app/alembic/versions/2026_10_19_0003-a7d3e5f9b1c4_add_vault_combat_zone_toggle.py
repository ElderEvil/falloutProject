"""add per-vault combat zone toggle

Revision ID: a7d3e5f9b1c4
Revises: c9f3a7e1b2d4
Create Date: 2026-10-19 00:03:00.000000

The Combat Zone now ships enabled by default. A per-vault boolean lets an admin
turn it off for one vault without touching the global kill switch. Existing vaults
backfill to enabled, matching the new default.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7d3e5f9b1c4"
down_revision: str | None = "c9f3a7e1b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vault",
        sa.Column("combat_zone_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("vault", "combat_zone_enabled")
