"""backfill legendary dweller thumbnail URLs

Revision ID: 5c88a7e4d918
Revises: 6e74d20b1b5e
"""

from alembic import op
import sqlalchemy as sa

from app.utils.legendary_dweller_assets import LEGENDARY_DWELLER_IMAGE_FILES, get_legendary_dweller_image_url

revision = "5c88a7e4d918"
down_revision = "6e74d20b1b5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for name in LEGENDARY_DWELLER_IMAGE_FILES:
        conn.execute(
            sa.text(
                "UPDATE dweller SET thumbnail_url = :url "
                "WHERE LOWER(TRIM(first_name || ' ' || COALESCE(last_name, ''))) = :name AND thumbnail_url IS NULL"
            ),
            {"url": get_legendary_dweller_image_url(name), "name": name},
        )
    conn.execute(
        sa.text(
            "UPDATE dweller SET thumbnail_url = :url "
            "WHERE LOWER(CAST(rarity AS TEXT)) = 'legendary' AND thumbnail_url IS NULL"
        ),
        {"url": get_legendary_dweller_image_url(None)},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE dweller SET thumbnail_url = NULL WHERE thumbnail_url LIKE '/static/legendary_dweller_images/%'"))
