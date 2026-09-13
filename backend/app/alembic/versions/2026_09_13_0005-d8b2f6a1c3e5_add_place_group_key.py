"""add place group key to world location

Revision ID: d8b2f6a1c3e5
Revises: c7a1e5f9b2d4
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8b2f6a1c3e5"
down_revision: str | None = "c7a1e5f9b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("worldlocation", sa.Column("group_key", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_worldlocation_group_key"), "worldlocation", ["group_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_worldlocation_group_key"), table_name="worldlocation")
    op.drop_column("worldlocation", "group_key")
