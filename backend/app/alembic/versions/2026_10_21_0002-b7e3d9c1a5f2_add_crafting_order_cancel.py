"""add crafting order cancellation

Revision ID: b7e3d9c1a5f2
Revises: ae12f4c9d7b3
Create Date: 2026-10-21 00:00:00.000000

Adds the cancelled lifecycle state, the cancellation timestamp, and the exact
junk snapshot needed to refund a cancelled order's materials.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7e3d9c1a5f2"
down_revision: str | None = "ae12f4c9d7b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE craftingorderstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")
    op.add_column("craftingorder", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "craftingorder",
        sa.Column(
            "junk_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("craftingorder", "junk_snapshot")
    op.drop_column("craftingorder", "cancelled_at")
    # PostgreSQL cannot remove a single enum value; the type is recreated only when
    # the crafting-order table itself is dropped (see 2026_09_13_0003).
