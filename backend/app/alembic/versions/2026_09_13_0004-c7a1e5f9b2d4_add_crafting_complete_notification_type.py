"""add_crafting_complete_notification_type

Revision ID: c7a1e5f9b2d4
Revises: 79550f90bdec
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a1e5f9b2d4"
down_revision: str | None = "79550f90bdec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The Python model defines CRAFTING_COMPLETE but the PostgreSQL notificationtype
    # enum was created without it. Without this, inserting the completion
    # notification raises InvalidTextRepresentationError, which poisons the tick
    # connection pool and crash-loops the worker (see the DWELLER_DIED migration).
    op.execute("ALTER TYPE notificationtype ADD VALUE 'CRAFTING_COMPLETE'")


def downgrade() -> None:
    # PostgreSQL can't drop a single enum value; a real revert would recreate the
    # type and rewrite the notification table. Safe to skip — downgrades are rare.
    pass
