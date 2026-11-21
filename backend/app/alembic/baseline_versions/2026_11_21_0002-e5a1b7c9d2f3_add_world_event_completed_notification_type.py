"""add world event completed notification type

Revision ID: e5a1b7c9d2f3
Revises: c1d4e7f0a2b9
Create Date: 2026-11-21 00:02:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5a1b7c9d2f3"
down_revision: str | Sequence[str] | None = "c1d4e7f0a2b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'WORLD_EVENT_COMPLETED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; recreating the type would need a full
    # rewrite of notification. Documented no-op, same as previous add-a-value revisions.
    pass
