"""re-resolve persisted item and legendary-dweller image URLs against the widened art maps

The FOS art backfill (#822) widened the weapon/outfit/junk asset maps and added hundreds
of images, but ``image_url`` is persisted on the rows. The earlier image backfills
(``8155dd024c0b``, ``6e74d20b1b5e``) only filled ``image_url IS NULL``; every weapon that
was unmapped at the time already carries the old generic ``10mm pistol FOS.png`` fallback,
so it keeps a stale (non-null) value and never picks up the new mapping. This revision
re-resolves existing rows against the current canonical maps.

Name-keyed and idempotent: it recomputes the canonical URL from each row's name and only
writes when the stored value differs, so a re-run is a no-op and already-correct rows are
untouched. Dwellers are only re-resolved when they still point at the catalog-managed
``/static/legendary_dweller_images/`` directory, so uploaded portraits are never clobbered.

Revision ID: 9f0a1b2c3d4e
Revises: c7e2b34a9d01
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from app.utils.junk_assets import get_junk_image_url
from app.utils.legendary_dweller_assets import get_legendary_dweller_image_url
from app.utils.outfit_assets import get_outfit_image_url
from app.utils.weapon_assets import get_weapon_image_url

revision = "9f0a1b2c3d4e"
down_revision = "c7e2b34a9d01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Weapons: the widened map plus the filename-convention family lookup, with the
    # generic weapon image as the final fallback.
    for name in conn.execute(sa.text("SELECT DISTINCT name FROM weapon")).scalars().all():
        url = get_weapon_image_url(name)
        if not url:
            continue
        conn.execute(
            sa.text(
                "UPDATE weapon SET image_url = :url "
                "WHERE LOWER(TRIM(name)) = :name AND (image_url IS NULL OR image_url <> :url)"
            ),
            {"url": url, "name": name.strip().lower()},
        )

    for name in conn.execute(sa.text("SELECT DISTINCT name FROM outfit")).scalars().all():
        url = get_outfit_image_url(name)
        if not url:
            continue
        conn.execute(
            sa.text(
                "UPDATE outfit SET image_url = :url "
                "WHERE LOWER(TRIM(name)) = :name AND (image_url IS NULL OR image_url <> :url)"
            ),
            {"url": url, "name": name.strip().lower()},
        )

    for name in conn.execute(sa.text("SELECT DISTINCT name FROM junk")).scalars().all():
        url = get_junk_image_url(name)
        if not url:
            continue
        conn.execute(
            sa.text(
                "UPDATE junk SET image_url = :url "
                "WHERE LOWER(TRIM(name)) = :name AND (image_url IS NULL OR image_url <> :url)"
            ),
            {"url": url, "name": name.strip().lower()},
        )

    # Only catalog-managed legendary portraits, identified by their stored static path —
    # never NULL or an uploaded (storage) URL, which would be a real player portrait.
    legendary_names = conn.execute(
        sa.text(
            "SELECT DISTINCT first_name || ' ' || COALESCE(last_name, '') FROM dweller "
            "WHERE image_url LIKE '/static/legendary_dweller_images/%'"
        )
    ).scalars().all()
    for name in legendary_names:
        url = get_legendary_dweller_image_url(name)
        if not url:
            continue
        conn.execute(
            sa.text(
                "UPDATE dweller SET image_url = :url "
                "WHERE LOWER(TRIM(first_name || ' ' || COALESCE(last_name, ''))) = :name "
                "AND image_url LIKE '/static/legendary_dweller_images/%' AND image_url <> :url"
            ),
            {"url": url, "name": name.strip().lower()},
        )


def downgrade() -> None:
    """No-op — data enrichment must not be reverted."""
