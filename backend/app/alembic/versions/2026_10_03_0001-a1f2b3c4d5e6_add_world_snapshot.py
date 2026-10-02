"""add world snapshot

Revision ID: a1f2b3c4d5e6
Revises: c19031dc6b22
Create Date: 2026-10-03 00:01:00.000000

Persistence boundary migration for the backend-owned generated world snapshot:
one ``worldsnapshot`` row per (world_id, generator_version) holding the recipe
identity (seed, config, recipe fingerprint) plus the generated terrain and
land-safe slots as JSONB, alongside a canonical snapshot checksum. The snapshot
is written explicitly once and read thereafter; requests never regenerate it.
``downgrade()`` drops the table, losing all persisted snapshots.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1f2b3c4d5e6"
down_revision: str | None = "c19031dc6b22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worldsnapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("world_id", sa.String(length=32), nullable=False),
        sa.Column("generator_version", sa.Integer(), nullable=False),
        sa.Column("seed", sa.String(length=64), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("recipe_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("terrain", postgresql.JSONB(), nullable=False),
        sa.Column("slots", postgresql.JSONB(), nullable=False),
        sa.Column("anchors", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_worldsnapshot_id"), "worldsnapshot", ["id"], unique=False)
    op.create_index(op.f("ix_worldsnapshot_world_id"), "worldsnapshot", ["world_id"], unique=False)
    op.create_index(op.f("ix_worldsnapshot_recipe_fingerprint"), "worldsnapshot", ["recipe_fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_table("worldsnapshot")