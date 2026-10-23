"""Move curated dweller portrait URLs into base/variants age directories.

Revision ID: e3a7c1b9d5f2
Revises: b8e4f1a2c9d3
Create Date: 2026-10-25 00:01:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "e3a7c1b9d5f2"
down_revision = "b8e4f1a2c9d3"
branch_labels = None
depends_on = None

IMAGE_PREFIX = "/static/dweller_images/"
THUMBNAIL_PREFIX = "/static/dweller_thumbnails/"
_GROUPED_PREFIXES = (
    "base/",
    "variants/adult/",
    "variants/child/",
    "variants/teen/",
)


def _rewrite(url: str | None, prefix: str) -> str | None:
    if not url or not url.startswith(prefix):
        return url
    rest = url[len(prefix) :]
    if rest.startswith(_GROUPED_PREFIXES):
        return url
    filename = rest.rsplit("/", 1)[-1]
    if not filename.startswith("FOS_Dw_Default_"):
        return url
    if rest.startswith("variants/"):
        return f"{prefix}variants/adult/{rest[len('variants/') :]}"
    return f"{prefix}base/{rest}"


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, image_url, thumbnail_url FROM dweller "
            "WHERE image_url LIKE '/static/dweller_images/%' "
            "OR thumbnail_url LIKE '/static/dweller_thumbnails/%'"
        )
    ).mappings().all()

    for row in rows:
        image_url = _rewrite(row["image_url"], IMAGE_PREFIX)
        thumbnail_url = _rewrite(row["thumbnail_url"], THUMBNAIL_PREFIX)
        if image_url == row["image_url"] and thumbnail_url == row["thumbnail_url"]:
            continue
        bind.execute(
            sa.text("UPDATE dweller SET image_url = :image_url, thumbnail_url = :thumbnail_url WHERE id = :id"),
            {"id": row["id"], "image_url": image_url, "thumbnail_url": thumbnail_url},
        )


def downgrade() -> None:
    """Irreversible: grouped URLs do not retain whether they came from the base or variant root."""
    pass
