"""Add targeted-dispatch fields to explorations (issue 772).

Revision ID: 401f95d70b98
Revises: e7f8a9b0c1d2
Create Date: 2026-09-26 00:02:00.000000

A targeted run is an exploration sent to clear a known map point. Both columns
are nullable with no backfill: `NULL` is the correct "free-roam" state for every
existing row, and is distinguishable from a real dispatch because a targeted run
always writes a location id and a tier snapshot.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "401f95d70b98"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exploration", sa.Column("target_location_id", sa.Uuid(), nullable=True))
    op.add_column("exploration", sa.Column("clear_tier", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_exploration_target_location_id",
        "exploration",
        "worldlocation",
        ["target_location_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_exploration_target_location_id", "exploration", type_="foreignkey")
    op.drop_column("exploration", "clear_tier")
    op.drop_column("exploration", "target_location_id")
