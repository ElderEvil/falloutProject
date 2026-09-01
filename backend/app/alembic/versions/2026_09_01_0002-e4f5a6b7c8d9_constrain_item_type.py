"""Constrain generic inventory item categories.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-01 12:30:00.000000
"""

from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

_ITEM_TYPES = "'misc', 'weapon', 'outfit', 'junk', 'consumable', 'lunchbox', 'pet', 'dweller'"


def upgrade() -> None:
    op.create_check_constraint("ck_item_item_type", "item", f"item_type IN ({_ITEM_TYPES})")


def downgrade() -> None:
    op.drop_constraint("ck_item_item_type", "item", type_="check")
