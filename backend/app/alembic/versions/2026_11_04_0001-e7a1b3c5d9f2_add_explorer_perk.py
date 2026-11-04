"""Add one elective explorer perk and its progression notification.

Existing dwellers intentionally start without a perk: none was previously earned
or selected. The nullable column preserves that meaning without random backfills.
"""

import sqlalchemy as sa
from alembic import op

revision = "e7a1b3c5d9f2"
down_revision = "d1f3a5c7e9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dweller", sa.Column("selected_perk", sa.String(32), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'PERK_UNLOCKED'")


def downgrade() -> None:
    op.drop_column("dweller", "selected_perk")
    # PostgreSQL cannot remove a single enum label; retaining it is harmless.
