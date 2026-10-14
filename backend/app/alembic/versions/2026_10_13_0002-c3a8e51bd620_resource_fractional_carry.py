"""Preserve fractional resource stock between integer ticks.

Zero is correct for existing rows: previous ticks discarded their fractions;
there is no historical fractional stock to backfill.
"""

import sqlalchemy as sa
from alembic import op

revision = "c3a8e51bd620"
down_revision = "b7d93840ac12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gamestate", sa.Column("resource_remainders", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("gamestate", "resource_remainders")
