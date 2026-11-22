"""add deprivation counters

Revision ID: b1e2f3a4c5d6
Revises: a7d4e1c85b20

Both columns default to 0, which is a correct value rather than a placeholder: 0 means "no deprived time
accumulated", and every existing vault is fed and watered, so no backfill is needed.
"""

import sqlalchemy as sa
from alembic import op

revision = "b1e2f3a4c5d6"
down_revision = "a7d4e1c85b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gamestate", sa.Column("food_deprived_ms", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "gamestate", sa.Column("water_deprived_ms", sa.BigInteger(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("gamestate", "water_deprived_ms")
    op.drop_column("gamestate", "food_deprived_ms")
