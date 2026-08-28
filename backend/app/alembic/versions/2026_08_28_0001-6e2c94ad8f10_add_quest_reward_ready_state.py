"""Add the quest reward claim state.

Revision ID: 6e2c94ad8f10
Revises: f1a2b3c4d5e6
Create Date: 2026-08-28 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e2c94ad8f10"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vaultquestcompletionlink",
        sa.Column("is_reward_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("vaultquestcompletionlink", "is_reward_ready", server_default=None)


def downgrade() -> None:
    op.drop_column("vaultquestcompletionlink", "is_reward_ready")
