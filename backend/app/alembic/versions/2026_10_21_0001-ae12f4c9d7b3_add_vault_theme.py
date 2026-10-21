"""add vault theme ownership

Revision ID: ae12f4c9d7b3
Revises: d9f1a2b3c4e5
Create Date: 2026-10-21 00:00:00.000000

Per-vault ownership of a Diner/Living Quarters theme, granted when a Theme
workshop order is collected. Boosted vaults are seeded with every theme crafted.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ae12f4c9d7b3"
down_revision: str | None = "d9f1a2b3c4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vault_theme",
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("style", sa.String(length=16), nullable=False),
        sa.Column("crafted_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vault_id", "style"),
    )


def downgrade() -> None:
    op.drop_table("vault_theme")
