"""Add arena_morale_awarded_at to vault (issue 999, arena morale bonus).

Revision ID: 7023cbca4fc1
Revises: c1d2e3f4a5b6
Create Date: 2026-10-15 00:00:00.000000

Per-vault rolling cooldown stamp for the arena morale bonus: the arena that
finishes first sets the window and later completions inside it are skipped.
Nullable with no backfill — a vault that never hosted a match simply has no
window. Mirrors ``last_exit_request_at`` (2026_09_29_0001).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7023cbca4fc1"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vault", sa.Column("arena_morale_awarded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("vault", "arena_morale_awarded_at")
