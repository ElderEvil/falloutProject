"""backfill weapon and legendary dweller image URLs

Revision ID: 6e74d20b1b5e
Revises: 8155dd024c0b
"""

from alembic import op
import sqlalchemy as sa

from app.utils.legendary_dweller_assets import LEGENDARY_DWELLER_IMAGE_FILES, get_legendary_dweller_image_url
from app.utils.weapon_assets import WEAPON_NAME_TO_IMAGE_FILE, get_weapon_image_url

revision = "6e74d20b1b5e"
down_revision = "8155dd024c0b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for name in WEAPON_NAME_TO_IMAGE_FILE:
        conn.execute(
            sa.text("UPDATE weapon SET image_url = :url WHERE LOWER(TRIM(name)) = :name AND image_url IS NULL"),
            {"url": get_weapon_image_url(name), "name": name},
        )
    conn.execute(
        sa.text("UPDATE weapon SET image_url = :url WHERE image_url IS NULL"),
        {"url": get_weapon_image_url(None)},
    )

    for name in LEGENDARY_DWELLER_IMAGE_FILES:
        conn.execute(
            sa.text(
                "UPDATE dweller SET image_url = :url "
                "WHERE LOWER(TRIM(first_name || ' ' || COALESCE(last_name, ''))) = :name AND image_url IS NULL"
            ),
            {"url": get_legendary_dweller_image_url(name), "name": name},
        )
    conn.execute(
        sa.text("UPDATE dweller SET image_url = :url WHERE LOWER(CAST(rarity AS TEXT)) = 'legendary' AND image_url IS NULL"),
        {"url": get_legendary_dweller_image_url(None)},
    )


def downgrade() -> None:
    """No-op — data enrichment must not be reverted."""
