"""add_hazard_team_joined_notification_type

Revision ID: f6e5d4c3b2a1
Revises: d1e2f3a4b5c6
Create Date: 2026-09-19 00:00:00.000000

Python NotificationType defines HAZARD_TEAM_JOINED but the PostgreSQL
notificationtype enum was created without it. Alembic autogenerate does not
detect enum value changes — see AGENTS.md "DB Enums & Alembic Migrations".

PostgreSQL has no DROP VALUE for a single enum label, so the downgrade is a
deliberate no-op: the label stays in the type and the migration chain remains
reversible at the schema level.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6e5d4c3b2a1"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'HAZARD_TEAM_JOINED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; recreating the type would
    # require rewriting every row that uses the label. Deliberate no-op.
    pass
