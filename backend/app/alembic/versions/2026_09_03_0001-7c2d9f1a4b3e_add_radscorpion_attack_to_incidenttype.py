# ruff: noqa: INP001
"""add_radscorpion_attack_to_incidenttype

Revision ID: 7c2d9f1a4b3e
Revises: e4f5a6b7c8d9
Create Date: 2026-09-03

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7c2d9f1a4b3e"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE incidenttype ADD VALUE IF NOT EXISTS 'RADSCORPION_ATTACK'")


def downgrade() -> None:
    pass
