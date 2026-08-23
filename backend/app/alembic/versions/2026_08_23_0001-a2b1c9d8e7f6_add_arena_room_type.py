"""Add ARENA to roomtypeenum."""

from alembic import op

revision = "a2b1c9d8e7f6"
down_revision: str | None = "1c57603aa0f6"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE roomtypeenum ADD VALUE 'ARENA'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE; recreating the type is required to remove a value.
    pass