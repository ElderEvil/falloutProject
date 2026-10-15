"""Add ARENA_MORALE_BOOST to notificationtype (issue 999, arena morale bonus).

Revision ID: d87f17395e24
Revises: 7023cbca4fc1
Create Date: 2026-10-15 00:00:00.000000

The Python ``NotificationType`` defines ``ARENA_MORALE_BOOST`` but the
PostgreSQL ``notificationtype`` type was created without it. Alembic
autogenerate does not detect enum value changes, so this is a manual
``ALTER TYPE ... ADD VALUE`` (see AGENTS.md "DB Enums & Alembic Migrations").
``IF NOT EXISTS`` keeps the migration idempotent.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d87f17395e24"
down_revision: str | None = "7023cbca4fc1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ARENA_MORALE_BOOST'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE, so the label is intentionally left in place.
    # A true revert would require recreating the whole type while rewriting every
    # dependent ``notification.notification_type`` row, and is not worth the
    # data-rewrite risk. Documented no-op.
    pass
