"""backfill outfit special bonuses

The outfit SPECIAL columns (added in 2026_09_18_0003) default to 0, so every
outfit row created before that migration renders no stat rows on the item and
dweller-equipment cards.

SPECIAL_BY_NAME is a frozen snapshot taken when this revision was written, not a
read of the live catalog or ``vault_seed``: a later catalog/seed edit must not
change what this revision backfills, and a moved data source must not break
``alembic upgrade`` before ``upgrade()`` runs.

Only rows whose stats are still all zero are touched, so the migration is
idempotent and never overwrites a row that already carries a bonus.

Revision ID: b7c8d9e0f1a2
Revises: f6e5d4c3b2a1
Create Date: 2026-09-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "f6e5d4c3b2a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPECIAL_KEYS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")
ZERO_GUARD = " AND ".join(f"COALESCE({key}, 0) = 0" for key in SPECIAL_KEYS)
UPDATE_SQL = sa.text(
    f"UPDATE outfit SET {', '.join(f'{key} = :{key}' for key in SPECIAL_KEYS)} "
    f"WHERE LOWER(TRIM(name)) = :name AND {ZERO_GUARD}"
)

# Catalog outfits carrying at least one SPECIAL bonus, plus the seed-only starter outfits
# that have no catalog entry. Lowercased, trimmed names; 0 means "no bonus".
SPECIAL_BY_NAME: dict[str, dict[str, int]] = {
    "abraham's relaxedwear": {"strength": 1, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "armored vault suit": {"strength": 0, "perception": 3, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "autumn's uniform": {"strength": 2, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "bittercup's outfit": {"strength": 2, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "confessor cromwell's rags": {"strength": 0, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 1, "agility": 0, "luck": 2},
    "elder robe": {"strength": 0, "perception": 0, "endurance": 0, "charisma": 4, "intelligence": 0, "agility": 3, "luck": 0},
    "eulogy jones' suit": {"strength": 2, "perception": 2, "endurance": 1, "charisma": 2, "intelligence": 0, "agility": 0, "luck": 0},
    "firefighter suit": {"strength": 0, "perception": 0, "endurance": 4, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "firefighter suit, rad helmet": {"strength": 0, "perception": 0, "endurance": 5, "charisma": 0, "intelligence": 2, "agility": 0, "luck": 0},
    "hazmat suit": {"strength": 0, "perception": 0, "endurance": 2, "charisma": 0, "intelligence": 2, "agility": 0, "luck": 0},
    "heavy synth armor": {"strength": 0, "perception": 0, "endurance": 4, "charisma": 3, "intelligence": 0, "agility": 0, "luck": 0},
    "heavy vault suit": {"strength": 0, "perception": 7, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "leather armor": {"strength": 1, "perception": 0, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 1, "luck": 0},
    "mechanic jumpsuit": {"strength": 1, "perception": 0, "endurance": 0, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "metal armor": {"strength": 2, "perception": 0, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "ncr ranger outfit": {"strength": 0, "perception": 4, "endurance": 0, "charisma": 2, "intelligence": 0, "agility": 0, "luck": 0},
    "robco r&d suit": {"strength": 0, "perception": 0, "endurance": 2, "charisma": 0, "intelligence": 4, "agility": 0, "luck": 0},
    "robot armor": {"strength": 2, "perception": 0, "endurance": 2, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 2},
    "sturdy vault suit": {"strength": 0, "perception": 5, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-45a power armor": {"strength": 2, "perception": 3, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-45d power armor": {"strength": 2, "perception": 4, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-45f power armor": {"strength": 2, "perception": 5, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-51a power armor": {"strength": 3, "perception": 1, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-51b power armor": {"strength": 3, "perception": 1, "endurance": 2, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-51d power armor": {"strength": 3, "perception": 2, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-51f power armor": {"strength": 4, "perception": 3, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-60a power armor": {"strength": 2, "perception": 0, "endurance": 3, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-60d power armor": {"strength": 2, "perception": 0, "endurance": 4, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "t-60f power armor": {"strength": 1, "perception": 1, "endurance": 5, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "tattered longcoat": {"strength": 2, "perception": 0, "endurance": 2, "charisma": 2, "intelligence": 0, "agility": 0, "luck": 2},
    "vault jumpsuit": {"strength": 0, "perception": 0, "endurance": 0, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 1},
    "x-01 mk i power armor": {"strength": 3, "perception": 1, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "x-01 mk iv power armor": {"strength": 4, "perception": 1, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "x-01 mk vi power armor": {"strength": 5, "perception": 1, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
}


def upgrade() -> None:
    """Set SPECIAL bonuses on outfit rows still carrying the all-zero default."""
    conn = op.get_bind()
    for name, bonuses in SPECIAL_BY_NAME.items():
        conn.execute(UPDATE_SQL, {"name": name, **bonuses})


def downgrade() -> None:
    """No-op — data enrichment must not be reverted."""
