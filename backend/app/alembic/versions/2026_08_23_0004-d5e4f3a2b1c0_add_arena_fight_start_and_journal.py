"""Add arena fight-start state to room and the arena match event journal table."""

from alembic import op

revision = "d5e4f3a2b1c0"
down_revision: str | None = "c4d3e2f1a0b9"
branch_labels = depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP TABLE arena_match_event")
    op.execute("ALTER TABLE room DROP COLUMN arena_fight_started_at")
