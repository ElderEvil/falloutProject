"""add arena match event actor

Revision ID: c4e8f6a1b2d3
Revises: b3d7e1f5a902
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8f6a1b2d3"
down_revision: str | Sequence[str] | None = "b3d7e1f5a902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("arena_match_event", sa.Column("actor_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("arena_match_event", "actor_id")
