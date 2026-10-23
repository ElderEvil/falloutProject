"""Add CHILD_ADOPTED to the notification type enum.

Revision ID: a775cb7e3ed4
Revises: ecbe0fb70132
Create Date: 2026-10-23 17:30:25.708916
"""

from alembic import op

revision = "a775cb7e3ed4"
down_revision = "ecbe0fb70132"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'CHILD_ADOPTED'")


def downgrade() -> None:
    pass
