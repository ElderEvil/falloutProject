"""backfill outfit hazard resistance

The outfit hazard-resistance columns (added in 2026_09_18_0002) shipped with
``fire_resist`` defaulting to 0 and ``radiation_resist`` left NULL, so every
outfit row created before that migration renders no fire or radiation
protection — the catalog values were only ever applied to newly seeded rows.

FIRE_RESIST_BY_NAME and RADIATION_RESIST_BY_NAME are frozen snapshots taken when
this revision was written, not reads of the live catalog or ``vault_seed``: a
later catalog edit must not change what this revision backfills, and a moved
data source must not break ``alembic upgrade`` before ``upgrade()`` runs.

The two columns have different "still at default" predicates. ``fire_resist`` is
NOT NULL with a server default of 0, so an untouched row sits at 0.
``radiation_resist`` is nullable, so an untouched row sits at NULL. Each update
touches only rows still at its own default, so the migration is idempotent and
never overwrites a row that already carries a value.

Revision ID: e5f6a7b8c9d0
Revises: f0e1d2c3b4a5
Create Date: 2026-09-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "f0e1d2c3b4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIRE_UPDATE_SQL = sa.text(
    "UPDATE outfit SET fire_resist = :fire_resist WHERE LOWER(TRIM(name)) = :name AND fire_resist = 0"
)
RADIATION_UPDATE_SQL = sa.text(
    "UPDATE outfit SET radiation_resist = :radiation_resist "
    "WHERE LOWER(TRIM(name)) = :name AND radiation_resist IS NULL"
)

# Catalog outfits declaring fire resistance. Lowercased, trimmed names.
FIRE_RESIST_BY_NAME: dict[str, float] = {
    "firefighter suit": 0.5,
    "firefighter suit, rad helmet": 0.75,
}

# Catalog outfits declaring radiation resistance. The explicit 0.0 on the plain
# firefighter suit is the catalog's own declaration, not an absent value.
RADIATION_RESIST_BY_NAME: dict[str, float] = {
    "firefighter suit": 0.0,
    "firefighter suit, rad helmet": 1.0,
    "hazmat suit": 1.0,
}


def upgrade() -> None:
    """Set hazard resistance on outfit rows still carrying their column default."""
    conn = op.get_bind()
    for name, fire_resist in FIRE_RESIST_BY_NAME.items():
        conn.execute(FIRE_UPDATE_SQL, {"name": name, "fire_resist": fire_resist})
    for name, radiation_resist in RADIATION_RESIST_BY_NAME.items():
        conn.execute(RADIATION_UPDATE_SQL, {"name": name, "radiation_resist": radiation_resist})


def downgrade() -> None:
    """No-op — data enrichment must not be reverted."""
