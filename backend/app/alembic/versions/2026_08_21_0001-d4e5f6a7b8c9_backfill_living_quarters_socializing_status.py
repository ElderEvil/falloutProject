"""Backfill Living Quarters dwellers to socializing status."""

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "b7e9f2c1a3d5"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(
        """UPDATE dweller SET status = 'RESTING'::dwellerstatusenum
        FROM room WHERE dweller.room_id = room.id AND LOWER(room.name) LIKE '%living%'
        AND dweller.status IN ('IDLE'::dwellerstatusenum, 'WORKING'::dwellerstatusenum)"""
    )


def downgrade() -> None:
    pass  # The prior status is not recoverable without overwriting valid socializing dwellers.
