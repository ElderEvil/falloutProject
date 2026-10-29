"""add world map v3 road edges

Revision ID: c1d3e5f7a9b2
Revises: b7c9e1f3a5d2
Create Date: 2026-10-28 00:03:00.000000

Adds the smoothed vector road edges used for rendering. They are additive and empty by
default; the flat ``roads`` mask remains the derived gameplay mask. Existing rows render
from their mask exactly as before.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1d3e5f7a9b2"
down_revision: str | None = "b7c9e1f3a5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "worldsnapshot",
        sa.Column("road_edges", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("worldsnapshot", "road_edges")
