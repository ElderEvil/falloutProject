"""Squashed arena + incident combat migrations.

Combines the seven linear arena-branch migrations into one step:
ARENA room type, incident combat_progress, arena fight state + journal
table, fighter slots, vault incidents_disabled flag, and the FIGHTING
dweller status. Squashing keeps the branch's DB story reviewable against
master (down_revision is master's head) without an eight-migration
history.
"""

from alembic import op

revision = "9f8e7d6c5b4a3"
down_revision: str | None = "1c57603aa0f6"
branch_labels = depends_on = None

# Base enum label sets (pre-branch values), used to rebuild the types on
# downgrade. PostgreSQL has no DROP VALUE, so removing the branch-added
# labels means recreating each enum without them.
ROOM_TYPE_LABELS = ["CAPACITY", "CRAFTING", "MISC", "PRODUCTION", "QUESTS", "THEME", "TRAINING"]
DWELLER_STATUS_LABELS = ["IDLE", "WORKING", "EXPLORING", "TRAINING", "RESTING", "DEAD", "QUESTING"]


def _recreate_enum(enum_name: str, labels: list[str], table: str, column: str) -> None:
    """Rebuild an enum type without the branch-added label.

    The old type is renamed aside, the new type is created with the base
    labels, the referencing column is cast through text, and the old type is
    dropped once nothing references it.
    """
    old_name = f"{enum_name}_old"
    op.execute(f"ALTER TYPE {enum_name} RENAME TO {old_name}")
    op.execute(f"CREATE TYPE {enum_name} AS ENUM ({', '.join(repr(label) for label in labels)})")
    op.execute(
        f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE {enum_name} '
        f'USING "{column}"::text::{enum_name}'
    )
    op.execute(f"DROP TYPE {old_name}")


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in
    # PostgreSQL, so each enum change gets its own autocommit block before
    # any dependent statement touches the new label.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE roomtypeenum ADD VALUE 'ARENA'")

    op.execute("ALTER TABLE incident ADD COLUMN combat_progress DOUBLE PRECISION NOT NULL DEFAULT 0")

    op.execute("ALTER TABLE room ADD COLUMN arena_last_fight_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE room ADD COLUMN arena_fight_started_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute(
        """
        CREATE TABLE arena_match_event (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES room (id) ON DELETE CASCADE,
            round_seq INTEGER NOT NULL DEFAULT 1,
            kind VARCHAR NOT NULL,
            message VARCHAR(200) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute("CREATE INDEX ix_arena_match_event_room_id ON arena_match_event (room_id)")
    op.execute("CREATE INDEX ix_arena_match_event_kind ON arena_match_event (kind)")

    op.execute("ALTER TABLE room ADD COLUMN arena_fighter_a_id UUID")
    op.execute("ALTER TABLE room ADD COLUMN arena_fighter_b_id UUID")
    op.execute(
        "ALTER TABLE room ADD CONSTRAINT fk_room_arena_fighter_a_id "
        "FOREIGN KEY (arena_fighter_a_id) REFERENCES dweller (id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE room ADD CONSTRAINT fk_room_arena_fighter_b_id "
        "FOREIGN KEY (arena_fighter_b_id) REFERENCES dweller (id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX ix_room_arena_fighter_a_id ON room (arena_fighter_a_id)")
    op.execute("CREATE INDEX ix_room_arena_fighter_b_id ON room (arena_fighter_b_id)")

    op.execute("ALTER TABLE vault ADD COLUMN incidents_disabled BOOLEAN NOT NULL DEFAULT FALSE")

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE dwellerstatusenum ADD VALUE 'FIGHTING'")
    op.execute(
        """
        UPDATE dweller
        SET status = 'FIGHTING'
        WHERE room_id IN (SELECT id FROM room WHERE category = 'ARENA'::roomtypeenum)
          AND status = 'WORKING'
        """
    )


def downgrade() -> None:
    # Move arena fighters back to WORKING and arena rooms back to MISC before
    # the labels are dropped, so no row references a value that disappears.
    op.execute(
        """
        UPDATE dweller
        SET status = 'WORKING'
        WHERE status = 'FIGHTING'
        """
    )
    op.execute(
        """
        UPDATE room
        SET category = 'MISC'
        WHERE category = 'ARENA'
        """
    )

    op.execute("DROP TABLE arena_match_event")

    op.execute("ALTER TABLE room DROP CONSTRAINT fk_room_arena_fighter_a_id")
    op.execute("ALTER TABLE room DROP CONSTRAINT fk_room_arena_fighter_b_id")
    op.execute("ALTER TABLE room DROP COLUMN arena_fighter_a_id")
    op.execute("ALTER TABLE room DROP COLUMN arena_fighter_b_id")

    op.execute("ALTER TABLE room DROP COLUMN arena_fight_started_at")
    op.execute("ALTER TABLE room DROP COLUMN arena_last_fight_at")

    op.execute("ALTER TABLE incident DROP COLUMN combat_progress")

    op.execute("ALTER TABLE vault DROP COLUMN incidents_disabled")

    _recreate_enum("roomtypeenum", ROOM_TYPE_LABELS, "room", "category")
    _recreate_enum("dwellerstatusenum", DWELLER_STATUS_LABELS, "dweller", "status")
