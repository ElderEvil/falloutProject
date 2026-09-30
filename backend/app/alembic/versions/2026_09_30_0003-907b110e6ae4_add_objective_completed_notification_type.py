"""add objective_completed notification type

Revision ID: 907b110e6ae4
Revises: cad3b442a260
Create Date: 2026-09-30 00:03:00.000000

Objective completion previously reused ``ACHIEVEMENT_UNLOCKED``; give it its own
type so the completion toast no longer also fires for family milestones.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "907b110e6ae4"
down_revision: str | None = "cad3b442a260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'OBJECTIVE_COMPLETED'")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE notification_type = 'OBJECTIVE_COMPLETED'")
    op.execute("ALTER TABLE notification ALTER COLUMN notification_type TYPE VARCHAR(64) USING notification_type::text")
    op.execute("DROP TYPE notificationtype")
    op.execute(
        "CREATE TYPE notificationtype AS ENUM ("
        "'EXPLORATION_UPDATE', 'EXPLORATION_COMPLETE', 'LEVEL_UP', 'TRAINING_COMPLETE', 'TRAINING_STARTED', "
        "'CRAFTING_COMPLETE', 'RECIPE_UNLOCKED', 'RELATIONSHIP_FORMED', 'PREGNANCY_DETECTED', 'BABY_BORN', "
        "'COMBAT_STARTED', 'COMBAT_VICTORY', 'COMBAT_DEFEAT', 'DWELLER_INJURED', 'DWELLER_DIED', "
        "'DWELLER_EXIT_REQUESTED', 'HAZARD_TEAM_JOINED', 'RESOURCE_LOW', 'RESOURCE_CRITICAL', 'POWER_OUTAGE', "
        "'QUEST_COMPLETE', 'ACHIEVEMENT_UNLOCKED', 'RADIO_NEW_DWELLER', 'RADIO_AUTO_SWITCHED_TO_HAPPINESS', "
        "'MAP_REGISTRATION_FAILED', 'LOCATION_CLEARED', 'LOCATION_READY')"
    )
    op.execute(
        "ALTER TABLE notification ALTER COLUMN notification_type TYPE notificationtype "
        "USING notification_type::notificationtype"
    )
