"""add_radio_auto_switch_notification_type

Revision ID: 2e4f6a8b0c1d
Revises: 8dca68ba234c
Create Date: 2026-09-24 00:01:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e4f6a8b0c1d"
down_revision: str | None = "8dca68ba234c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Alembic autogenerate does not detect PostgreSQL enum value changes.
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'RADIO_AUTO_SWITCHED_TO_HAPPINESS'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum label, so recreate the type after
    # removing rows that use the value being rolled back.
    op.execute("DELETE FROM notification WHERE notification_type = 'RADIO_AUTO_SWITCHED_TO_HAPPINESS'")
    op.execute("ALTER TABLE notification ALTER COLUMN notification_type TYPE VARCHAR(64) USING notification_type::text")
    op.execute("DROP TYPE notificationtype")
    op.execute(
        "CREATE TYPE notificationtype AS ENUM ("
        "'EXPLORATION_UPDATE', 'EXPLORATION_COMPLETE', 'LEVEL_UP', 'TRAINING_COMPLETE', 'TRAINING_STARTED', "
        "'CRAFTING_COMPLETE', 'RELATIONSHIP_FORMED', 'PREGNANCY_DETECTED', 'BABY_BORN', 'COMBAT_STARTED', "
        "'COMBAT_VICTORY', 'COMBAT_DEFEAT', 'DWELLER_INJURED', 'DWELLER_DIED', 'DWELLER_EXIT_REQUESTED', "
        "'HAZARD_TEAM_JOINED', 'RESOURCE_LOW', 'RESOURCE_CRITICAL', 'POWER_OUTAGE', 'QUEST_COMPLETE', "
        "'ACHIEVEMENT_UNLOCKED', 'RADIO_NEW_DWELLER', 'MAP_REGISTRATION_FAILED')"
    )
    op.execute(
        "ALTER TABLE notification ALTER COLUMN notification_type TYPE notificationtype "
        "USING notification_type::notificationtype"
    )
