"""Backfill human skin/hair portrait variants.

Revision ID: b8e4f1a2c9d3
Revises: c4f1a7d92e10
Create Date: 2026-10-24 00:03:00.000000
"""

import json

import sqlalchemy as sa
from alembic import op

from app.utils.dweller_assets import default_dweller_image_urls

revision = "b8e4f1a2c9d3"
down_revision = "c4f1a7d92e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, gender, visual_attributes, image_url, thumbnail_url FROM dweller "
            "WHERE image_url LIKE '/static/dweller_images/%' "
            "AND thumbnail_url LIKE '/static/dweller_thumbnails/%' "
            "AND LOWER(COALESCE(visual_attributes->>'race', 'human')) = 'human'"
        )
    ).mappings().all()

    for row in rows:
        attrs = row["visual_attributes"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        attrs = attrs or {}
        image_url, thumbnail_url = default_dweller_image_urls(
            "human",
            row["gender"],
            None,
            attrs.get("skin_tone"),
            attrs.get("hair_color"),
        )
        if image_url is None or image_url == row["image_url"]:
            continue
        bind.execute(
            sa.text("UPDATE dweller SET image_url = :image_url, thumbnail_url = :thumbnail_url WHERE id = :id"),
            {"id": row["id"], "image_url": image_url, "thumbnail_url": thumbnail_url},
        )


def downgrade() -> None:
    """Irreversible: base and variant curated URLs cannot be told apart afterwards."""
    pass
