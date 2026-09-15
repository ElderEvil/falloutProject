"""add unclaimed_loot to incident for overflow take/sell

Revision ID: e1f2a3b4c5d6
Revises: d8b2f6a1c3e5
Create Date: 2026-09-15 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d8b2f6a1c3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incident",
        sa.Column("unclaimed_loot", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("incident", "unclaimed_loot")
