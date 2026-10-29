"""add world map v3 towns

Revision ID: f7a9b2c4d6e8
Revises: d4e6f8a0c2b3
Create Date: 2026-10-28 00:06:00.000000

Adds town footprint/template metadata. The street polylines themselves live in
``road_edges``; this column lets the renderer paint a soft urban patch under the grid.
Empty by default, so existing v2 and v3 rows remain readable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f7a9b2c4d6e8"
down_revision: str | None = "d4e6f8a0c2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "worldsnapshot",
        sa.Column("towns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("worldsnapshot", "towns")
