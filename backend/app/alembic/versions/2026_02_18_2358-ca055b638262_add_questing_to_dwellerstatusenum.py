# ruff: noqa: INP001
"""add_questing_to_dwellerstatusenum

Revision ID: ca055b638262
Revises: 5934c2bdf3e1
Create Date: 2026-02-18 23:58:35.250029

"""

from collections.abc import Sequence

from alembic import op

revision: str = "ca055b638262"
down_revision: str | None = "5934c2bdf3e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE dwellerstatusenum ADD VALUE IF NOT EXISTS 'QUESTING'")


def downgrade() -> None:
    pass
