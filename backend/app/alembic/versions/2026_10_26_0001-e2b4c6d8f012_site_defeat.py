"""Add a nonlethal, consumed expedition defeat outcome.

Revision ID: e2b4c6d8f012
Revises: d4e8f2a6b013
"""
from alembic import op

revision = "e2b4c6d8f012"
down_revision = "d4e8f2a6b013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE expeditionrunstatus ADD VALUE IF NOT EXISTS 'DEFEATED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a label; retain historical nonlethal defeat records.
    pass
