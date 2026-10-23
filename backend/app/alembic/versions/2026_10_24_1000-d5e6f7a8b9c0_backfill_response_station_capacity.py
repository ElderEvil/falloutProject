"""backfill response station capacity

Revision ID: d5e6f7a8b9c0
Revises: c4d9e2f7a1b3
Create Date: 2026-10-24 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d9e2f7a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('UPDATE room SET capacity = size WHERE LOWER(name) = \'response station\' AND capacity IS NULL')


def downgrade() -> None:
    # Capacity is derived data; leaving it populated on downgrade is harmless.
    pass
