"""add spatial movement columns to explorations

Revision ID: ed3106fee74f
Revises: 8a7c07e1b448
Create Date: 2026-10-04 00:03:00.000000

Slice 1 of spatial travel: persisted directional movement on explorations.
Every column is nullable with no backfill: ``NULL`` is the correct "legacy run"
state for every existing row, and is distinguishable from a spatial run because
a spatial departure always writes the full movement set (world version, origin,
heading, position, trail, position_as_of).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ed3106fee74f"
down_revision: str | None = "8a7c07e1b448"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exploration", sa.Column("world_version", sa.Integer(), nullable=True))
    op.add_column("exploration", sa.Column("origin_x", sa.Float(), nullable=True))
    op.add_column("exploration", sa.Column("origin_y", sa.Float(), nullable=True))
    op.add_column("exploration", sa.Column("heading_degrees", sa.Float(), nullable=True))
    op.add_column("exploration", sa.Column("pos_x", sa.Float(), nullable=True))
    op.add_column("exploration", sa.Column("pos_y", sa.Float(), nullable=True))
    op.add_column("exploration", sa.Column("trail", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("exploration", sa.Column("position_as_of", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("exploration", "position_as_of")
    op.drop_column("exploration", "trail")
    op.drop_column("exploration", "pos_y")
    op.drop_column("exploration", "pos_x")
    op.drop_column("exploration", "heading_degrees")
    op.drop_column("exploration", "origin_y")
    op.drop_column("exploration", "origin_x")
    op.drop_column("exploration", "world_version")
