"""add arena mode and team columns

Revision ID: a1c2e3f4b5d6
Revises: 862c04111ec1
Create Date: 2026-10-13 00:01:00.000000

Wave P1 of the arena teams plan: a new ``arenamode`` PG enum plus two extra
dweller fighter slots (2v2) and a JSONB opponent list (PvE). Every column is
nullable with no backfill: NULL ``arena_mode`` means duel, the C/D slots are
unset, and ``arena_opponents`` is empty — exactly how existing rows already
behave. The enum labels are pinned in ``PG_ENUM_LABELS_SNAPSHOT`` (test_enum_drift)
in the same commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c2e3f4b5d6"
down_revision: str | None = "862c04111ec1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Brand-new enum type, so its values are safe to use in the same transaction.
    op.execute("CREATE TYPE arenamode AS ENUM ('DUEL', 'BRAWL', 'HUNT')")
    op.add_column(
        "room",
        sa.Column(
            "arena_mode",
            postgresql.ENUM("DUEL", "BRAWL", "HUNT", name="arenamode", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("room", sa.Column("fighter_c_id", sa.Uuid(), nullable=True))
    op.add_column("room", sa.Column("fighter_d_id", sa.Uuid(), nullable=True))
    op.add_column("room", sa.Column("arena_opponents", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key("fk_room_fighter_c_id", "room", "dweller", ["fighter_c_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_room_fighter_d_id", "room", "dweller", ["fighter_d_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_room_fighter_c_id", "room", ["fighter_c_id"])
    op.create_index("ix_room_fighter_d_id", "room", ["fighter_d_id"])


def downgrade() -> None:
    op.drop_index("ix_room_fighter_d_id", table_name="room")
    op.drop_index("ix_room_fighter_c_id", table_name="room")
    op.drop_constraint("fk_room_fighter_d_id", "room", type_="foreignkey")
    op.drop_constraint("fk_room_fighter_c_id", "room", type_="foreignkey")
    op.drop_column("room", "arena_opponents")
    op.drop_column("room", "fighter_d_id")
    op.drop_column("room", "fighter_c_id")
    op.drop_column("room", "arena_mode")
    op.execute("DROP TYPE arenamode")
