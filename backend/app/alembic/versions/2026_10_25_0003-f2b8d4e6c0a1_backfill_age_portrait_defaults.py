"""Backfill age portraits for legacy dwellers without skin/hair fields.

Revision ID: f2b8d4e6c0a1
Revises: a8c4d2e6f0b1
Create Date: 2026-10-25 00:03:00.000000
"""

import json

import sqlalchemy as sa
from alembic import op

from app.utils.dweller_assets import default_dweller_image_urls

revision = "f2b8d4e6c0a1"
down_revision = "a8c4d2e6f0b1"
branch_labels = None
depends_on = None


def _is_curated(url: str | None) -> bool:
    return bool(url and url.rsplit("/", 1)[-1].startswith("FOS_Dw_Default_"))


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, age_group, gender, visual_attributes, image_url, thumbnail_url FROM dweller "
            "WHERE image_url LIKE '/static/dweller_images/%' "
            "AND thumbnail_url LIKE '/static/dweller_thumbnails/%'"
        )
    ).mappings().all()

    for row in rows:
        age_group = getattr(row["age_group"], "value", row["age_group"])
        if str(age_group).upper() not in {"CHILD", "TEEN", "ELDER"}:
            continue
        if not _is_curated(row["image_url"]) or not _is_curated(row["thumbnail_url"]):
            continue
        attrs = row["visual_attributes"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        attrs = attrs or {}
        race = attrs.get("race")
        if str(race or "human").casefold() != "human":
            continue
        image_url, thumbnail_url = default_dweller_image_urls(
            "human",
            row["gender"],
            None,
            attrs.get("skin_tone"),
            attrs.get("hair_color"),
            row["age_group"],
        )
        if image_url is None:
            continue
        if image_url == row["image_url"] and thumbnail_url == row["thumbnail_url"]:
            continue
        bind.execute(
            sa.text("UPDATE dweller SET image_url = :image_url, thumbnail_url = :thumbnail_url WHERE id = :id"),
            {"id": row["id"], "image_url": image_url, "thumbnail_url": thumbnail_url},
        )


def downgrade() -> None:
    """Irreversible: the previous base/variant URLs cannot be reconstructed."""
    pass
