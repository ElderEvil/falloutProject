"""Add FIGHTING to dwellerstatusenum."""

from alembic import op

revision = "f1e2d3c4b5a6"
down_revision: str | None = "f0e9d8c7b6a5"
branch_labels = depends_on = None


def upgrade() -> None:
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
    # PostgreSQL has no DROP VALUE; recreating the type is required to remove a value.
    pass