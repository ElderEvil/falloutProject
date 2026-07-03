"""add_dweller_died_notification_type

Revision ID: e4af3f6a7756
Revises: abc123def456
Create Date: 2026-07-02 10:54:17.254090

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4af3f6a7756"
down_revision: str | None = "abc123def456"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The Python model defines DWELLER_DIED but the PostgreSQL notificationtype
    # enum was created without it.  When the worker attempts to INSERT a
    # notification with this type, the DB rejects it with:
    #   InvalidTextRepresentationError: invalid input value for enum notificationtype: "DWELLER_DIED"
    # The transaction rolls back, SQLAlchemy enters a poisoned state, and the
    # Dramatiq worker crash-loops (~6.5 crashes/min).
    op.execute("ALTER TYPE notificationtype ADD VALUE 'DWELLER_DIED'")

    # Drop the unused index (was missed in previous cleanup)
    op.drop_index(op.f("ix_llminteraction_created_at"), table_name="llminteraction")


def downgrade() -> None:
    # PostgreSQL doesn't support removing a single value from an enum.
    # To truly revert you'd need to recreate the type:
    #   1. Ensure no rows use 'DWELLER_DIED'
    #   2. CREATE TYPE notificationtype_new AS ENUM(...)
    #   3. ALTER TABLE ... ALTER COLUMN ... TYPE ... USING ...::text::notificationtype_new
    #   4. DROP TYPE notificationtype
    #   5. ALTER TYPE notificationtype_new RENAME TO notificationtype
    # Safe to skip — downgrades are rare.
    op.create_index(op.f("ix_llminteraction_created_at"), "llminteraction", ["created_at"], unique=False)
