"""merge vault-slot and world-snapshot heads

Revision ID: f2a7926009fe
Revises: f8b2c3d4e5f6, a1f2b3c4d5e6
Create Date: 2026-10-03 00:04:00.000000

Join revision: the vault-slot chain (via ``f8b2c3d4e5f6``) and the world-snapshot
lane (via ``a1f2b3c4d5e6``) both branched from ``c19031dc6b22``. No schema change;
both branches apply in dependency order.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f2a7926009fe"
down_revision: str | Sequence[str] | None = ("f8b2c3d4e5f6", "a1f2b3c4d5e6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: join revision only."""


def downgrade() -> None:
    """No-op: join revision only."""
