"""add world map v3 payload fields

Revision ID: b7c9e1f3a5d2
Revises: e2f3a4b5c6d7
Create Date: 2026-10-28 00:02:00.000000

Adds the World Map v3 payload: regions, per-tile region ids, bridges, places, the
validation report, and the authored blueprint. All fields are additive and empty by
default, so existing v2 snapshots stay readable and pinned explorations keep resolving
without a backfill.

Empty is a legal value for every column: an empty region map means "no region layer",
an empty bridge set means "no bridge crossings", and an empty blueprint means "fully
procedural world". The generator writes populated values only when ``GENERATOR_VERSION``
reaches v3.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c9e1f3a5d2"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB_COLUMNS: tuple[tuple[str, str], ...] = (
    ("regions", "'[]'::jsonb"),
    ("region_map", "'[]'::jsonb"),
    ("bridges", "'[]'::jsonb"),
    ("places", "'[]'::jsonb"),
    ("validation", "'{}'::jsonb"),
    ("blueprint", "'{}'::jsonb"),
)


def upgrade() -> None:
    for name, default in _JSONB_COLUMNS:
        op.add_column(
            "worldsnapshot",
            sa.Column(name, postgresql.JSONB(), nullable=False, server_default=sa.text(default)),
        )
    op.add_column(
        "worldsnapshot",
        sa.Column("blueprint_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "worldsnapshot",
        sa.Column("blueprint_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    # Only the unused v3 payload is lost; terrain, slots, masks and recipe identity stay intact.
    op.drop_column("worldsnapshot", "blueprint_version")
    op.drop_column("worldsnapshot", "blueprint_hash")
    for name, _default in reversed(_JSONB_COLUMNS):
        op.drop_column("worldsnapshot", name)
