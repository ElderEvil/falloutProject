"""Track daily and weekly quest rotation periods on game state.

Revision ID: b3f7a2c9d4e8
Revises: 9a73f29c2ed1
Create Date: 2026-11-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f7a2c9d4e8"
down_revision: str | None = "9a73f29c2ed1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable periods; NULL (not adopted) makes the first rotation call roll immediately."""
    op.add_column("gamestate", sa.Column("daily_quests_period", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gamestate", sa.Column("weekly_quests_period", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Drop rotation metadata. Data-wise a no-op: periods carry no player progress."""
    op.drop_column("gamestate", "weekly_quests_period")
    op.drop_column("gamestate", "daily_quests_period")
