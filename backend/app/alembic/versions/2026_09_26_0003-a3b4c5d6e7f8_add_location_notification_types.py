"""Add location notification types (issue 772, phase 4a).

Revision ID: a3b4c5d6e7f8
Revises: 401f95d70b98
Create Date: 2026-09-26 00:03:00.000000

The Python model defines LOCATION_CLEARED / LOCATION_READY but the PostgreSQL
notificationtype enum was created without them. When the worker attempts to
INSERT a notification with either type, the DB rejects it with:
  InvalidTextRepresentationError: invalid input value for enum notificationtype: "LOCATION_CLEARED"
The transaction rolls back, SQLAlchemy enters a poisoned state, and the
Dramatiq worker crash-loops. `IF NOT EXISTS` keeps the migration idempotent.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "401f95d70b98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'LOCATION_CLEARED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'LOCATION_READY'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing a single value from an enum.
    # To truly revert you'd need to recreate the type:
    #   1. Ensure no rows use 'LOCATION_CLEARED' or 'LOCATION_READY'
    #   2. CREATE TYPE notificationtype_new AS ENUM(...)
    #   3. ALTER TABLE ... ALTER COLUMN ... TYPE ... USING ...::text::notificationtype_new
    #   4. DROP TYPE notificationtype
    #   5. ALTER TYPE notificationtype_new RENAME TO notificationtype
    # Safe to skip — downgrades are rare.
    pass
