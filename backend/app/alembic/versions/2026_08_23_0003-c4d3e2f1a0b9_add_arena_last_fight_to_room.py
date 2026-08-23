"""Add arena_last_fight_at to room - one match per assignment, then stop."""

from alembic import op

revision = "c4d3e2f1a0b9"
down_revision: str | None = "b3c2d1e0f9a8"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE room ADD COLUMN arena_last_fight_at TIMESTAMP WITHOUT TIME ZONE")


def downgrade() -> None:
    op.execute("ALTER TABLE room DROP COLUMN arena_last_fight_at")
