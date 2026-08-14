"""backfill outfit image urls

Revision ID: 8155dd024c0b
Revises: 3f13e2c5a7d9
Create Date: 2026-08-14 20:26:13.355663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.outfit_assets import OUTFIT_NAME_TO_IMAGE_FILE, get_outfit_image_url


# revision identifiers, used by Alembic.
revision: str = '8155dd024c0b'
down_revision: Union[str, None] = '3f13e2c5a7d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill image_url for outfits that have a mapped apparel asset."""
    conn = op.get_bind()
    for name in OUTFIT_NAME_TO_IMAGE_FILE:
        image_url = get_outfit_image_url(name)
        if not image_url:
            continue
        conn.execute(
            sa.text(
                "UPDATE outfit SET image_url = :url WHERE LOWER(TRIM(name)) = :name AND image_url IS NULL"
            ),
            {"url": image_url, "name": name},
        )


def downgrade() -> None:
    """Clear backfilled outfit image URLs."""
    conn = op.get_bind()
    for name in OUTFIT_NAME_TO_IMAGE_FILE:
        image_url = get_outfit_image_url(name)
        if not image_url:
            continue
        conn.execute(
            sa.text("UPDATE outfit SET image_url = NULL WHERE image_url = :url"),
            {"url": image_url},
        )
