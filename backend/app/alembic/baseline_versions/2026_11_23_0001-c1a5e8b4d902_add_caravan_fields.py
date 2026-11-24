"""add caravan purpose and cooldown

Revision ID: c1a5e8b4d902
Revises: b1e2f3a4c5d6
Create Date: 2026-11-23 00:01:00.000000

Trade caravans (issue 1493). No backfill: 'clear' is what every existing run is, and a NULL cooldown
means "never traded". Both adds are metadata-only in PG, so no maintenance window; the default is dropped
straight after so the migrated schema matches the model. No index on purpose — two values, never filtered
alone. If a trade-only scan ever needs one, a partial index is the right tool, not a btree over a boolean.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a5e8b4d902"
down_revision: str | None = "b1e2f3a4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exploration", sa.Column("purpose", sa.String(length=16), nullable=False, server_default="clear"))
    op.alter_column("exploration", "purpose", server_default=None)
    op.add_column("vaultlocationstate", sa.Column("caravan_available_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("vaultlocationstate", "caravan_available_at")
    op.drop_column("exploration", "purpose")
