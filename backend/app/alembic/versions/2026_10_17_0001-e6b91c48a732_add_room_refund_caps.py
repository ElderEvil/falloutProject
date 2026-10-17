"""Preserve exact demolition refunds through room splitting and merging.

NULL deliberately retains the historical formula for existing rooms; no backfill
is needed. An allocated value is populated only when a room is remodeled.
"""

import sqlalchemy as sa
from alembic import op

revision = "e6b91c48a732"
down_revision = "d8e4c7a2b915"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("room", sa.Column("refund_caps", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("room", "refund_caps")
