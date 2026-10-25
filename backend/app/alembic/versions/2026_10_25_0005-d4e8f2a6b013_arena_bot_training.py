"""Add full-team Arena bot training.

Revision ID: d4e8f2a6b013
Revises: c7e9a1b3d5f8
"""
from alembic import op

revision = "d4e8f2a6b013"
down_revision = "c7e9a1b3d5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE arenamode ADD VALUE IF NOT EXISTS 'TRAINING'")


def downgrade() -> None:
    # PostgreSQL cannot remove an enum label. Preserve historical training matches.
    pass
