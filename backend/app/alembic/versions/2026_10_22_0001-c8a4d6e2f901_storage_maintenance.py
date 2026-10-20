"""Add hourly storage maintenance clocks and notification labels.

Revision ID: c8a4d6e2f901
Revises: b7e3d9c1a5f2
"""
import sqlalchemy as sa
from alembic import op

revision = "c8a4d6e2f901"
down_revision = "b7e3d9c1a5f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL means never trialed: all existing weapons receive an initialization grace hour.
    op.add_column("weapon", sa.Column("last_maintenance_trial_at", sa.DateTime(), nullable=True))
    op.create_index("ix_weapon_storage_trial", "weapon", ["storage_id", "last_maintenance_trial_at"])
    op.execute("ALTER TYPE notificationtype ADD VALUE 'STORAGE_ITEM_DEGRADED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE 'STORAGE_ITEM_UPGRADED'")


def downgrade() -> None:
    # PostgreSQL cannot DROP VALUE; notification labels intentionally remain for history.
    op.drop_index("ix_weapon_storage_trial", table_name="weapon")
    op.drop_column("weapon", "last_maintenance_trial_at")
