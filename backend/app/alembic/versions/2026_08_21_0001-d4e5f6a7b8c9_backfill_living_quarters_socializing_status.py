"""Backfill Living Quarters dwellers to socializing status."""

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "b7e9f2c1a3d5"
branch_labels = depends_on = None

BACKFILL_SOCIALIZING_DWELLERS_SQL = """UPDATE dweller SET status = 'RESTING'::dwellerstatusenum
FROM room WHERE dweller.room_id = room.id AND LOWER(room.name) LIKE '%living%'
AND room.category = 'CAPACITY'::roomtypeenum
AND dweller.status IN ('IDLE'::dwellerstatusenum, 'WORKING'::dwellerstatusenum)"""


def upgrade() -> None:
    op.execute(BACKFILL_SOCIALIZING_DWELLERS_SQL)


def downgrade() -> None:
    pass  # The prior status is not recoverable without overwriting valid socializing dwellers.
