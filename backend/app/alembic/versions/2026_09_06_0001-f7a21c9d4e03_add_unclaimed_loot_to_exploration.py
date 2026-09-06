"""add unclaimed_loot to exploration for overflow take/sell

Revision ID: f7a21c9d4e03
Revises: c0d1e2f3a4b5
Create Date: 2026-09-06 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "f7a21c9d4e03"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exploration",
        sa.Column("unclaimed_loot", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("exploration", "unclaimed_loot")
