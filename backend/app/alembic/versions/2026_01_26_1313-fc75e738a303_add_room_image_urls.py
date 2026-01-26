"""add_room_image_urls

Revision ID: fc75e738a303
Revises: c7756d4e7543
Create Date: 2026-01-26 13:13:11.820798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'fc75e738a303'
down_revision: Union[str, None] = 'c7756d4e7543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Populate image_url for all existing rooms."""
    # Import the function here to avoid import issues
    from app.utils.room_assets import get_room_image_url

    # Get database connection
    connection = op.get_bind()

    # Fetch all rooms
    result = connection.execute(text("SELECT id, name, tier, size, size_min FROM room"))
    rooms = result.fetchall()

    # Update each room with its image_url
    for room in rooms:
        room_id, name, tier, size, size_min = room
        # Use size if available, otherwise fall back to size_min
        room_size = size if size is not None else size_min
        image_url = get_room_image_url(name, tier=tier, size=room_size)

        if image_url:
            connection.execute(
                text("UPDATE room SET image_url = :image_url WHERE id = :room_id"),
                {"image_url": image_url, "room_id": room_id}
            )

    connection.commit()


def downgrade() -> None:
    """Clear image_url for all rooms."""
    connection = op.get_bind()
    connection.execute(text("UPDATE room SET image_url = NULL"))
    connection.commit()
