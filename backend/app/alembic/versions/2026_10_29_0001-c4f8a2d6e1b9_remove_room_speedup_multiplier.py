"""Remove the unused room speedup multiplier.

Revision ID: c4f8a2d6e1b9
Revises: a9f3c2d1e8b7
Create Date: 2026-10-29 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4f8a2d6e1b9"
down_revision: str | Sequence[str] | None = "a9f3c2d1e8b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("room", "speedup_multiplier")


def downgrade() -> None:
    op.add_column(
        "room",
        sa.Column("speedup_multiplier", sa.Float(), nullable=False, server_default=sa.text("1.0")),
    )
    op.alter_column("room", "speedup_multiplier", server_default=None)
