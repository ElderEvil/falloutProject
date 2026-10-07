"""add roads and rivers to world snapshot

Revision ID: e2f3a4b5c6d7
Revises: 862c04111ec1
Create Date: 2026-10-07 00:01:00.000000

Display-only road and river masks for the backend-owned world snapshot. Each is a flat,
sorted list of tile indices over the ``width x height`` terrain grid.

Roads are routed in-recipe by ``generate_road_mask`` (junctions from the
``roads:junctions`` stream, Prim MST spanning, 4-connected A* detouring around water —
roads never bridge). Rivers are traced in-recipe by ``generate_rivers`` (meandering
``_trace_river`` walks from the ``rivers`` stream, small speckle components filtered
out) and are display-only: they never mutate terrain, so unlike the retired carve
approach they cannot alter traversal, ETA, or movement.

``server_default='[]'`` is deliberately a legitimate empty mask, not a placeholder:
every pre-mask row predates road/river generation and renders mask-less, which is
exactly what ``[]`` means. This is the same "empty is legal" pattern for both columns,
so existing snapshots need no backfill and remain readable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "862c04111ec1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "worldsnapshot",
        sa.Column("roads", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "worldsnapshot",
        sa.Column("rivers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    # Documented reversal of the additive change: drop both display-only masks.
    # This loses only the masks; terrain, slots, and recipe identity are untouched,
    # and a downgraded reader simply renders a road-less, river-less world.
    op.drop_column("worldsnapshot", "rivers")
    op.drop_column("worldsnapshot", "roads")
