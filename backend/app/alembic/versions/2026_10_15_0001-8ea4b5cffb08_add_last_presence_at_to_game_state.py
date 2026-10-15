"""Add last_presence_at to game_state (incident spawn presence gating).

Revision ID: 8ea4b5cffb08
Revises: d87f17395e24
Create Date: 2026-10-15 00:00:00.000000

Visibility-gated vault-view heartbeat timestamp; spawns require one inside
the presence window so background tabs start nothing. Nullable with no
backfill — a vault never pinged simply has no presence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8ea4b5cffb08"
down_revision: str | None = "d87f17395e24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("gamestate", sa.Column("last_presence_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("gamestate", "last_presence_at")
