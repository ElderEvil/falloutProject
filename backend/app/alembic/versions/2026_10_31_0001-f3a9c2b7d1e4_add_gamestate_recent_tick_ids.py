"""Add recent completed tick ids to game state.

The empty list is correct for existing rows: prior versions did not record tick
ids, so there is no historical completion to backfill.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "f3a9c2b7d1e4"
down_revision: str | None = "c7d9e1f3a5b2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("gamestate", sa.Column("recent_tick_ids", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("gamestate", "recent_tick_ids")
