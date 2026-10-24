"""add rush notification types

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
Create Date: 2026-10-24 11:03:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2d4f6a8c0e1"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'RUSH_SUCCEEDED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'RUSH_FAILED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; recreating the type would require
    # rewriting notification rows. Leaving the labels in place is harmless.
    pass
