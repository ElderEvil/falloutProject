"""add encounter pause timestamp to explorations

Revision ID: 862c04111ec1
Revises: ed3106fee74f
Create Date: 2026-10-05 00:01:00.000000

Slice 3b of spatial travel: ``paused_at`` marks when a site encounter froze the
journey clock. Nullable with no backfill: NULL is the correct "not paused" state
for every existing row, and the value is always written and cleared by the
entry/exit boundaries.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "862c04111ec1"
down_revision: str | None = "ed3106fee74f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exploration", sa.Column("paused_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("exploration", "paused_at")
