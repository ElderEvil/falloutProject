"""add world map v3 road anchors

Revision ID: d4e6f8a0c2b3
Revises: c1d3e5f7a9b2
Create Date: 2026-10-28 00:04:00.000000

Adds the locations-lite anchor layer used to build the road graph. Anchors are
topology only: they are not gameplay locations, discoveries, or dispatch targets.
Empty by default, so existing rows remain readable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e6f8a0c2b3"
down_revision: str | None = "c1d3e5f7a9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "worldsnapshot",
        sa.Column("road_anchors", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("worldsnapshot", "road_anchors")
