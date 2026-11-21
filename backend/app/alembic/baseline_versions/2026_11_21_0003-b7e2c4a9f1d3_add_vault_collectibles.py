"""add vault collectible claims

Revision ID: b7e2c4a9f1d3
Revises: d4c8a1f6e293
Create Date: 2026-11-21 00:03:00.000000

Durable per-vault bobblehead claims, the one-time salvage marker on inert map points, and the
finder's derived bonus cache. Timestamps are timestamptz throughout. ``collectible_bonus`` stays
NULL for every existing dweller, which is the correct "no collectibles yet" state, so no backfill
is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c4a9f1d3"
down_revision: str | None = "d4c8a1f6e293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vaultcollectible",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("collectible_key", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("finder_dweller_id", sa.Uuid(), nullable=True),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("found_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["finder_dweller_id"], ["dweller.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["worldlocation.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_id", "collectible_key", name="uq_vault_collectible_key"),
    )
    op.create_index(op.f("ix_vaultcollectible_id"), "vaultcollectible", ["id"], unique=False)
    op.create_index(op.f("ix_vaultcollectible_vault_id"), "vaultcollectible", ["vault_id"], unique=False)
    op.create_index(op.f("ix_vaultcollectible_collectible_key"), "vaultcollectible", ["collectible_key"], unique=False)
    op.add_column("vaultlocationstate", sa.Column("searched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "dweller",
        sa.Column("collectible_bonus", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # PG has no DROP VALUE; the label is additive and pinned in PG_ENUM_LABELS_SNAPSHOT.
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'COLLECTIBLE_FOUND'")


def downgrade() -> None:
    # The notificationtype label cannot be removed without recreating the type; leave it.
    op.drop_column("dweller", "collectible_bonus")
    op.drop_column("vaultlocationstate", "searched_at")
    op.drop_index(op.f("ix_vaultcollectible_collectible_key"), table_name="vaultcollectible")
    op.drop_index(op.f("ix_vaultcollectible_vault_id"), table_name="vaultcollectible")
    op.drop_index(op.f("ix_vaultcollectible_id"), table_name="vaultcollectible")
    op.drop_table("vaultcollectible")
