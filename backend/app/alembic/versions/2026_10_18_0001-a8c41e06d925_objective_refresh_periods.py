"""Persist successful UTC objective refresh periods without resetting current work."""

from datetime import datetime, timedelta

import sqlalchemy as sa
from alembic import op

revision = "a8c41e06d925"
down_revision = "e6b91c48a732"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Adopt existing assignments for the current period, preserving deployment progress."""
    op.add_column("gamestate", sa.Column("daily_objectives_period", sa.DateTime(), nullable=True))
    op.add_column("gamestate", sa.Column("weekly_objectives_period", sa.DateTime(), nullable=True))
    # NULL is reserved for state created later without an adopted refresh window.
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    state = sa.table(
        "gamestate",
        sa.column("daily_objectives_period", sa.DateTime()),
        sa.column("weekly_objectives_period", sa.DateTime()),
    )
    op.get_bind().execute(
        state.update().values(
            daily_objectives_period=today, weekly_objectives_period=today - timedelta(days=today.weekday())
        )
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'OBJECTIVES_REFRESHED'")


def downgrade() -> None:
    """Remove period metadata; PostgreSQL retains the unused notification enum label."""
    op.drop_column("gamestate", "weekly_objectives_period")
    op.drop_column("gamestate", "daily_objectives_period")
