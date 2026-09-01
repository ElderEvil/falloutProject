"""Add generic inventory categories to storage.

Revision ID: d3e4f5a6b7c8
Revises: c2d4e6f8a0b1
Create Date: 2026-09-01 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d4e6f8a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("item", sa.Column("item_type", sa.String(length=32), nullable=False, server_default="misc"))
    op.add_column("item", sa.Column("storage_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_item_storage_id_storage", "item", "storage", ["storage_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_item_storage_id_storage", "item", type_="foreignkey")
    op.drop_column("item", "storage_id")
    op.drop_column("item", "item_type")
