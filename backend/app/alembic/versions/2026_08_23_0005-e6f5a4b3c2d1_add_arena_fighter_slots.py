"""Add arena fighter slot selection to room - pick who fights who."""

from alembic import op

revision = "e6f5a4b3c2d1"
down_revision: str | None = "d5e4f3a2b1c0"
branch_labels = depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("ALTER TABLE room DROP CONSTRAINT fk_room_arena_fighter_a_id")
    op.execute("ALTER TABLE room DROP CONSTRAINT fk_room_arena_fighter_b_id")
    op.execute("ALTER TABLE room DROP COLUMN arena_fighter_a_id")
    op.execute("ALTER TABLE room DROP COLUMN arena_fighter_b_id")