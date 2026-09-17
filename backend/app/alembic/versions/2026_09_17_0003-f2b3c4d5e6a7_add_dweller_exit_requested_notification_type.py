"""add_dweller_exit_requested_notification_type

Revision ID: f2b3c4d5e6a7
Revises: e7c8d9a0b1f2
Create Date: 2026-09-17 00:00:02.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b3c4d5e6a7"
down_revision: str | None = "e7c8d9a0b1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Python NotificationType defines DWELLER_EXIT_REQUESTED but notificationtype was
    # created without it. Alembic autogenerate does not detect enum value changes — see
    # AGENTS.md "DB Enums & Alembic Migrations".
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DWELLER_EXIT_REQUESTED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value, so the type is recreated. Any rows still
    # using the label are removed first so the swap cannot fail on them.
    op.execute("DELETE FROM notification WHERE notification_type = 'DWELLER_EXIT_REQUESTED'")
    op.execute("ALTER TABLE notification ALTER COLUMN notification_type TYPE VARCHAR(64) USING notification_type::text")
    op.execute("DROP TYPE notificationtype")
    op.execute(
        "CREATE TYPE notificationtype AS ENUM ("
        "'EXPLORATION_UPDATE', 'EXPLORATION_COMPLETE', 'LEVEL_UP', 'TRAINING_COMPLETE', 'TRAINING_STARTED', "
        "'CRAFTING_COMPLETE', 'RELATIONSHIP_FORMED', 'PREGNANCY_DETECTED', 'BABY_BORN', 'COMBAT_STARTED', "
        "'COMBAT_VICTORY', 'COMBAT_DEFEAT', 'DWELLER_INJURED', 'DWELLER_DIED', 'RESOURCE_LOW', "
        "'RESOURCE_CRITICAL', 'POWER_OUTAGE', 'QUEST_COMPLETE', 'ACHIEVEMENT_UNLOCKED', 'RADIO_NEW_DWELLER', "
        "'MAP_REGISTRATION_FAILED')"
    )
    op.execute(
        "ALTER TABLE notification ALTER COLUMN notification_type TYPE notificationtype "
        "USING notification_type::notificationtype"
    )
