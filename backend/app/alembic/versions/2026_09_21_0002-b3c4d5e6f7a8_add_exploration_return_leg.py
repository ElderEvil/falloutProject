"""add exploration return leg

Revision ID: b3c4d5e6f7a8
Revises: e5f6a7b8c9d0
Create Date: 2026-09-21 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Autogenerate does not detect enum value changes: the RETURNING member must be
    # added manually or writes poison the connection pool (see the DWELLER_DIED outage).
    op.execute("ALTER TYPE explorationstatus ADD VALUE IF NOT EXISTS 'RETURNING'")
    op.add_column("exploration", sa.Column("return_started_at", sa.DateTime(), nullable=True))
    op.add_column("exploration", sa.Column("return_completes_at", sa.DateTime(), nullable=True))
    op.add_column(
        "exploration",
        sa.Column("recalled_early", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("exploration", "recalled_early")
    op.drop_column("exploration", "return_completes_at")
    op.drop_column("exploration", "return_started_at")
    # PostgreSQL cannot drop a single enum value; a real revert would recreate the
    # type and rewrite the exploration table. Safe to skip — downgrades are rare.
