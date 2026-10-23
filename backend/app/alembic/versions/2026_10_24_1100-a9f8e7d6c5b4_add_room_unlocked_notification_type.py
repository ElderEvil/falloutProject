"""add room unlocked notification type

Revision ID: a9f8e7d6c5b4
Revises: e2f4a6c8d0b1
Create Date: 2026-10-24 11:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a9f8e7d6c5b4"
down_revision: str | Sequence[str] | None = "e2f4a6c8d0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ROOM_UNLOCKED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; recreate the type if a rollback is required.
    pass
