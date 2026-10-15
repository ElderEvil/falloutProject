"""extract arena state into its own table

Revision ID: b2c3d4e5f6a7
Revises: a1c2e3f4b5d6
Create Date: 2026-10-15 00:01:00.000000

Moves the eight arena-only columns off ``room`` into a dedicated ``arena_state``
table (one row per configured arena room, ``room_id`` PK/FK cascade), plus a new
``knocked_out_ids`` JSONB that persists match knockouts across ticks and processes.
Generic room read/create/update contracts drop the moved fields.

Backfill copies every room that carries any arena state before the old columns are
dropped. ``down_revision`` keeps the linear history; no enum change is involved
(``arenamode`` already exists), so ``PG_ENUM_LABELS_SNAPSHOT`` is untouched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1c2e3f4b5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ARENA_MODE = postgresql.ENUM("DUEL", "BRAWL", "HUNT", name="arenamode", create_type=False)


def upgrade() -> None:
    op.create_table(
        "arena_state",
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("mode", _ARENA_MODE, nullable=True),
        sa.Column("fighter_a_id", sa.Uuid(), nullable=True),
        sa.Column("fighter_b_id", sa.Uuid(), nullable=True),
        sa.Column("fighter_c_id", sa.Uuid(), nullable=True),
        sa.Column("fighter_d_id", sa.Uuid(), nullable=True),
        sa.Column("opponents", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_fight_at", sa.DateTime(), nullable=True),
        sa.Column("fight_started_at", sa.DateTime(), nullable=True),
        sa.Column("knocked_out_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"], name="fk_arena_state_room_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["fighter_a_id"], ["dweller.id"], name="fk_arena_state_fighter_a_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["fighter_b_id"], ["dweller.id"], name="fk_arena_state_fighter_b_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["fighter_c_id"], ["dweller.id"], name="fk_arena_state_fighter_c_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["fighter_d_id"], ["dweller.id"], name="fk_arena_state_fighter_d_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("room_id", name="pk_arena_state"),
    )
    op.create_index("ix_arena_state_fighter_a_id", "arena_state", ["fighter_a_id"])
    op.create_index("ix_arena_state_fighter_b_id", "arena_state", ["fighter_b_id"])
    op.create_index("ix_arena_state_fighter_c_id", "arena_state", ["fighter_c_id"])
    op.create_index("ix_arena_state_fighter_d_id", "arena_state", ["fighter_d_id"])

    op.execute(
        """
        INSERT INTO arena_state (
            room_id, mode, fighter_a_id, fighter_b_id, fighter_c_id, fighter_d_id,
            opponents, last_fight_at, fight_started_at, created_at, updated_at
        )
        SELECT
            id, arena_mode, arena_fighter_a_id, arena_fighter_b_id, fighter_c_id, fighter_d_id,
            arena_opponents, arena_last_fight_at, arena_fight_started_at, now(), now()
        FROM room
        WHERE arena_mode IS NOT NULL
           OR arena_fighter_a_id IS NOT NULL
           OR arena_fighter_b_id IS NOT NULL
           OR fighter_c_id IS NOT NULL
           OR fighter_d_id IS NOT NULL
           OR arena_opponents IS NOT NULL
           OR arena_last_fight_at IS NOT NULL
           OR arena_fight_started_at IS NOT NULL
        """
    )

    op.drop_column("room", "arena_opponents")
    op.drop_column("room", "arena_fighter_a_id")
    op.drop_column("room", "arena_fighter_b_id")
    op.drop_column("room", "fighter_c_id")
    op.drop_column("room", "fighter_d_id")
    op.drop_column("room", "arena_mode")
    op.drop_column("room", "arena_last_fight_at")
    op.drop_column("room", "arena_fight_started_at")


def downgrade() -> None:
    op.add_column("room", sa.Column("arena_mode", _ARENA_MODE, nullable=True))
    op.add_column("room", sa.Column("arena_fighter_a_id", sa.Uuid(), nullable=True))
    op.add_column("room", sa.Column("arena_fighter_b_id", sa.Uuid(), nullable=True))
    op.add_column("room", sa.Column("fighter_c_id", sa.Uuid(), nullable=True))
    op.add_column("room", sa.Column("fighter_d_id", sa.Uuid(), nullable=True))
    op.add_column("room", sa.Column("arena_opponents", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("room", sa.Column("arena_last_fight_at", sa.DateTime(), nullable=True))
    op.add_column("room", sa.Column("arena_fight_started_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_room_arena_fighter_a_id", "room", "dweller", ["arena_fighter_a_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_room_arena_fighter_b_id", "room", "dweller", ["arena_fighter_b_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key("fk_room_fighter_c_id", "room", "dweller", ["fighter_c_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_room_fighter_d_id", "room", "dweller", ["fighter_d_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_room_arena_fighter_a_id", "room", ["arena_fighter_a_id"])
    op.create_index("ix_room_arena_fighter_b_id", "room", ["arena_fighter_b_id"])
    op.create_index("ix_room_fighter_c_id", "room", ["fighter_c_id"])
    op.create_index("ix_room_fighter_d_id", "room", ["fighter_d_id"])

    op.execute(
        """
        UPDATE room AS r SET
            arena_mode = s.mode,
            arena_fighter_a_id = s.fighter_a_id,
            arena_fighter_b_id = s.fighter_b_id,
            fighter_c_id = s.fighter_c_id,
            fighter_d_id = s.fighter_d_id,
            arena_opponents = s.opponents,
            arena_last_fight_at = s.last_fight_at,
            arena_fight_started_at = s.fight_started_at
        FROM arena_state AS s
        WHERE s.room_id = r.id
        """
    )

    op.drop_table("arena_state")
