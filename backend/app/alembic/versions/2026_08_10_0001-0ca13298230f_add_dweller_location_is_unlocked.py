"""add_dweller_location_is_unlocked

Revision ID: 0ca13298230f
Revises: 4408ea93bd5b
Create Date: 2026-08-10 00:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0ca13298230f"
down_revision: str | None = "4408ea93bd5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dwellerlocation",
        sa.Column("is_unlocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_dwellerlocation_is_unlocked", "dwellerlocation", ["is_unlocked"])


def downgrade() -> None:
    op.drop_index("ix_dwellerlocation_is_unlocked", "dwellerlocation")
    op.drop_column("dwellerlocation", "is_unlocked")
