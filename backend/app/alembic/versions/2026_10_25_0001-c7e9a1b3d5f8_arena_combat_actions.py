"""Persist resolved Arena actions for combat playback.

Revision ID: c7e9a1b3d5f8
Revises: b2d4f6a8c0e1
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7e9a1b3d5f8"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Historical prose cannot recover targets reliably. NULL intentionally means
    # no playback data; existing journals remain readable without fake backfills.
    op.add_column("arena_match_event", sa.Column("action", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("arena_match_event", "action")
