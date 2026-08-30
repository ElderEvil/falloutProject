"""add is_traded to dweller

Revision ID: b4c5d6e7f8a9
Revises: a3e5f7b9c1d2
Create Date: 2026-08-30 18:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "a3e5f7b9c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_traded flag marking dwellers whose sale proceeds were already collected."""
    op.add_column(
        "dweller",
        sa.Column("is_traded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Remove the is_traded flag."""
    op.drop_column("dweller", "is_traded")
