"""add room rush state

Revision ID: a1c3e5f7b9d2
Revises: a9f8e7d6c5b4
Create Date: 2026-10-24 11:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "a9f8e7d6c5b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("room", sa.Column("rush_stacks", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("room", sa.Column("last_rush_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("room", "last_rush_at")
    op.drop_column("room", "rush_stacks")
