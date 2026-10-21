"""Backfill default portraits for dwellers without an image.

Revision ID: c4f1a7d92e10
Revises: d9e2f4a6b801
Create Date: 2026-10-24 00:02:00.000000
"""

import json
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

from app.utils.dweller_assets import resolve_dweller_image_urls

revision = "c4f1a7d92e10"
down_revision = "d9e2f4a6b801"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, gender, visual_attributes, image_url, thumbnail_url FROM dweller "
            "WHERE image_url IS NULL OR thumbnail_url IS NULL"
        )
    ).mappings().all()

    for row in rows:
        attrs = row["visual_attributes"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        dweller = SimpleNamespace(
            image_url=row["image_url"],
            thumbnail_url=row["thumbnail_url"],
            gender=row["gender"],
            visual_attributes=attrs or {},
        )
        image_url, thumbnail_url = resolve_dweller_image_urls(dweller)
        if image_url is None and thumbnail_url is None:
            continue
        bind.execute(
            sa.text("UPDATE dweller SET image_url = :image_url, thumbnail_url = :thumbnail_url WHERE id = :id"),
            {"id": row["id"], "image_url": image_url, "thumbnail_url": thumbnail_url},
        )


def downgrade() -> None:
    """Irreversible: a curated default and a custom portrait cannot be told apart afterwards."""
    pass
