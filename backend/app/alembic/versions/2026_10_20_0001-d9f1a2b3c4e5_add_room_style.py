"""add room style

Revision ID: d9f1a2b3c4e5
Revises: f4c2a6e8b103
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9f1a2b3c4e5"
down_revision: str | None = "f4c2a6e8b103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the cosmetic room style, defaulting existing rooms to the standard art."""
    op.add_column(
        "room",
        sa.Column("room_style", sa.String(length=16), nullable=False, server_default="default"),
    )


def downgrade() -> None:
    op.drop_column("room", "room_style")
