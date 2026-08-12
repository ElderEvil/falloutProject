"""add_map_registration_failed_notification_type

Revision ID: 2d31a1e4b5c6
Revises: 0ca13298230f
Create Date: 2026-08-12 00:01:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2d31a1e4b5c6"
down_revision: str | None = "0ca13298230f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'MAP_REGISTRATION_FAILED'")


def downgrade() -> None:
    # PostgreSQL cannot remove individual enum values. Recreating this type is
    # intentionally deferred because downgrades are not used in production.
    pass
