"""normalize dead dweller status and happiness

Revision ID: f4c2a6e8b103
Revises: d83a5c7e901f
Create Date: 2026-10-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4c2a6e8b103"
down_revision: str | None = "d83a5c7e901f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Correct legacy corpses whose status or happiness predates death handling."""
    op.execute("UPDATE dweller SET status = 'DEAD', happiness = 0 WHERE is_dead IS TRUE")


def downgrade() -> None:
    """No-op: these values are canonical for dead dwellers and cannot be reversed safely."""
