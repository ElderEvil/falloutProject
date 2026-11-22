"""add exploration location xp

Revision ID: f3a9c2d7b518
Revises: b7e2c4a9f1d3
Create Date: 2026-11-22 00:01:00.000000

Snapshotted base XP of a successful location clear. NULL for every existing run, which is the
correct "no clear recorded" state, so no backfill is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c2d7b518"
down_revision: str | None = "b7e2c4a9f1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exploration", sa.Column("location_xp", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("exploration", "location_xp")
