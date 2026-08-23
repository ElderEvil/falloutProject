"""Add combat_progress to incident for fractional kill accumulation."""

from alembic import op

revision = "b3c2d1e0f9a8"
down_revision: str | None = "a2b1c9d8e7f6"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE incident ADD COLUMN combat_progress DOUBLE PRECISION NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE incident DROP COLUMN combat_progress")
