"""rename expeditionrun.cleared_at to finished_at

Revision ID: b80551876fa9
Revises: f2cfb4f037d0
Create Date: 2026-09-25 19:00:00.000000

The terminal timestamp backs the 7-day per-vault+site cooldown for every
terminal status (CLEARED/RETREATED/DIED), so its name must not imply
clear-only. Rename while the feature is still unmerged; the live dev DB
already applied b74a718e1e92 with ``cleared_at``, so this is a rename, not
an edit of that migration.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b80551876fa9"
down_revision: str | None = "f2cfb4f037d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("expeditionrun", "cleared_at", new_column_name="finished_at")


def downgrade() -> None:
    op.alter_column("expeditionrun", "finished_at", new_column_name="cleared_at")
