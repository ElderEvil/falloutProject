"""Add persisted youth apprenticeship state to dwellers.

Revision ID: a3e5f7b9c1d2
Revises: 6e2c94ad8f10
Create Date: 2026-08-29 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3e5f7b9c1d2"
down_revision: str | None = "6e2c94ad8f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


special_enum = sa.Enum(
    "STRENGTH",
    "PERCEPTION",
    "ENDURANCE",
    "CHARISMA",
    "INTELLIGENCE",
    "AGILITY",
    "LUCK",
    name="specialenum",
    create_type=False,
)


def upgrade() -> None:
    op.add_column("dweller", sa.Column("apprentice_stat", special_enum, nullable=True))
    op.add_column("dweller", sa.Column("apprentice_started_at", sa.DateTime(), nullable=True))
    op.create_index(
        "uq_dweller_active_apprentice_room",
        "dweller",
        ["room_id"],
        unique=True,
        postgresql_where=sa.text("apprentice_started_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_dweller_active_apprentice_room", table_name="dweller")
    op.drop_column("dweller", "apprentice_started_at")
    op.drop_column("dweller", "apprentice_stat")
