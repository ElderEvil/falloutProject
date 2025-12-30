"""update_existing_dweller_status

Revision ID: a3ae46f91798
Revises: 8db3164d3ed7
Create Date: 2025-12-30 11:56:35.249637

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3ae46f91798'
down_revision: Union[str, None] = '8db3164d3ed7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing dwellers to have correct status based on their assignments
    # Dwellers in training rooms -> TRAINING
    # Dwellers in production rooms -> WORKING
    # Dwellers in other rooms -> WORKING
    # Dwellers not in rooms -> IDLE

    # First, set all dwellers without a room to IDLE
    op.execute("""
               UPDATE dweller
               SET status = 'IDLE'
               WHERE room_id IS NULL
               """)

    # Set dwellers in training rooms to TRAINING
    op.execute("""
               UPDATE dweller
               SET status = 'TRAINING'
               FROM room
               WHERE dweller.room_id = room.id
                 AND room.category = 'TRAINING'
               """)

    # Set dwellers in production rooms to WORKING
    op.execute("""
               UPDATE dweller
               SET status = 'WORKING'
               FROM room
               WHERE dweller.room_id = room.id
                 AND room.category = 'PRODUCTION'
               """)

    # Set dwellers in other rooms to WORKING (default for room assignment)
    op.execute("""
               UPDATE dweller
               SET status = 'WORKING'
               FROM room
               WHERE dweller.room_id = room.id
                 AND room.category NOT IN ('TRAINING', 'PRODUCTION')
               """)


def downgrade() -> None:
    # Reset all statuses to IDLE
    op.execute("""
               UPDATE dweller
               SET status = 'IDLE'
               """)
