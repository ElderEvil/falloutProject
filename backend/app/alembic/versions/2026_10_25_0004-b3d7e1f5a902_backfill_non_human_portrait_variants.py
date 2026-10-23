"""Backfill non-human portrait alternates by stable dweller ID.

Revision ID: b3d7e1f5a902
Revises: f2b8d4e6c0a1
Create Date: 2026-10-25 00:04:00.000000
"""

import json

import sqlalchemy as sa
from alembic import op

from app.utils.dweller_assets import default_dweller_image_urls

revision = "b3d7e1f5a902"
down_revision = "f2b8d4e6c0a1"
branch_labels = None
depends_on = None

_NON_HUMAN_RACES = {"ghoul", "super_mutant", "synth"}


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
        if not _is_curated(row["image_url"]) or not _is_curated(row["thumbnail_url"]):
            continue
        attrs = row["visual_attributes"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        attrs = attrs or {}
        race = attrs.get("race")
        if race not in _NON_HUMAN_RACES:
            continue
        image_url, thumbnail_url = default_dweller_image_urls(
            race,
            row["gender"],
            attrs.get("state_of_being"),
            attrs.get("skin_tone"),
            attrs.get("hair_color"),
            row["age_group"],
            str(row["id"]),
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
    """Irreversible: alternate portraits are valid curated defaults after the swap."""
    pass
