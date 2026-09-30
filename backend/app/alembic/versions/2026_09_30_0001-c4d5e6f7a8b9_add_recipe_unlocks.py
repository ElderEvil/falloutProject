"""add recipe unlocks

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-09-30 00:00:00.000000

Per-vault progress for learning a gated crafting recipe by scrapping the exact
item, plus the ``RECIPE_UNLOCKED`` notification type. ``ADD VALUE IF NOT EXISTS``
keeps the enum change idempotent.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vault_recipe_unlock",
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("recipe_name", sa.String(length=128), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vault_id", "item_type", "recipe_name"),
    )
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'RECIPE_UNLOCKED'")


def downgrade() -> None:
    op.drop_table("vault_recipe_unlock")
    # PostgreSQL cannot remove a single enum value; recreating the type is required
    # to revert RECIPE_UNLOCKED (see the location-notification migration).
