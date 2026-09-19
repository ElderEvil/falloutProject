"""backfill outfit special bonuses

The outfit SPECIAL columns (added in 2026_09_18_0003) default to 0, so every
outfit row created before that migration renders no stat rows on the item and
dweller-equipment cards. Enrich those rows from the same two sources the
seeders use: the outfit catalog for catalog items, and ``SEED_OUTFITS`` for the
seed-only starter outfits that have no catalog entry.

Only rows whose stats are still all zero are touched, so the migration is
idempotent and never overwrites a row that already carries a bonus.

Revision ID: b7c8d9e0f1a2
Revises: f6e5d4c3b2a1
Create Date: 2026-09-19 00:00:00.000000

"""

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.services.vault_seed import SEED_OUTFITS

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "f6e5d4c3b2a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPECIAL_KEYS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")
CATALOG_DIR = Path(__file__).resolve().parents[2] / "data" / "items" / "outfits"
ZERO_GUARD = " AND ".join(f"COALESCE({key}, 0) = 0" for key in SPECIAL_KEYS)
UPDATE_SQL = sa.text(
    f"UPDATE outfit SET {', '.join(f'{key} = :{key}' for key in SPECIAL_KEYS)} "
    f"WHERE LOWER(TRIM(name)) = :name AND {ZERO_GUARD}"
)


def _special_by_name() -> dict[str, dict[str, int]]:
    """Outfit name -> the seven SPECIAL bonuses it should carry."""
    entries: list[dict] = []
    for path in sorted(CATALOG_DIR.glob("*.json")):
        entries.extend(json.loads(path.read_text()))
    entries.extend(SEED_OUTFITS)
    return {
        str(entry["name"]).strip().lower(): {key: int(entry.get(key) or 0) for key in SPECIAL_KEYS}
        for entry in entries
    }


SPECIAL_BY_NAME: dict[str, dict[str, int]] = _special_by_name()


def upgrade() -> None:
    """Set SPECIAL bonuses on outfit rows still carrying the all-zero default."""
    conn = op.get_bind()
    for name, bonuses in SPECIAL_BY_NAME.items():
        conn.execute(UPDATE_SQL, {"name": name, **bonuses})


def downgrade() -> None:
    """No-op — data enrichment must not be reverted."""
