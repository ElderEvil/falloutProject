"""add_item_table_objective_category_and_rewardtype_enums

Revision ID: 5934c2bdf3e1
Revises: add_medical_storage_fields
Create Date: 2026-02-18 21:04:16.052683

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5934c2bdf3e1"
down_revision: str | None = "add_medical_storage_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    rarity_enum = postgresql.ENUM("COMMON", "RARE", "LEGENDARY", name="rarityenum", create_type=False)

    op.create_table(
        "item",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("rarity", rarity_enum, nullable=False),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("image_url", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_item_id"), "item", ["id"], unique=False)
    op.create_index(op.f("ix_item_name"), "item", ["name"], unique=False)

    op.add_column(
        "objective",
        sa.Column("category", sa.String(50), nullable=False, server_default="achievement"),
    )
    op.create_index(op.f("ix_objective_category"), "objective", ["category"], unique=False)

    op.execute("ALTER TYPE rewardtype ADD VALUE IF NOT EXISTS 'STIMPAK'")
    op.execute("ALTER TYPE rewardtype ADD VALUE IF NOT EXISTS 'RADAWAY'")
    op.execute("ALTER TYPE rewardtype ADD VALUE IF NOT EXISTS 'LUNCHBOX'")


def downgrade() -> None:
    # NOTE: PostgreSQL does not support DROP VALUE for enum types.
    # The added values 'STIMPAK', 'RADAWAY', and 'LUNCHBOX' in the 'rewardtype'
    # enum will remain. Manual DB-level steps are required to fully revert.
    op.drop_index(op.f("ix_objective_category"), table_name="objective")
    op.drop_column("objective", "category")

    op.drop_index(op.f("ix_item_name"), table_name="item")
    op.drop_index(op.f("ix_item_id"), table_name="item")
    op.drop_table("item")
