"""add outfit SPECIAL bonus columns

Revision ID: c3d4e5f6a7b8
Revises: 7b2c4d9e1f30
Create Date: 2026-09-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "7b2c4d9e1f30"
branch_labels = None
depends_on = None

SPECIAL_STATS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")

#: Frozen snapshot of the outfit catalog's SPECIAL bonuses, taken at revision
#: time. Inline so the backfill stays reproducible after catalog refactors;
#: names are unique across the catalog files, so a name match is a safe key.
OUTFIT_SPECIAL_BONUSES: dict[str, dict[str, int]] = {
    "Mechanic jumpsuit": {"strength": 1, "perception": 0, "endurance": 0, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "Abraham's relaxedwear": {"strength": 1, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "Tattered longcoat": {"strength": 2, "perception": 0, "endurance": 2, "charisma": 2, "intelligence": 0, "agility": 0, "luck": 2},
    "Autumn's uniform": {"strength": 2, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "Bittercup's outfit": {"strength": 2, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 0, "agility": 0, "luck": 0},
    "Confessor Cromwell's rags": {"strength": 0, "perception": 2, "endurance": 2, "charisma": 1, "intelligence": 1, "agility": 0, "luck": 2},
    "Elder robe": {"strength": 0, "perception": 0, "endurance": 0, "charisma": 4, "intelligence": 0, "agility": 3, "luck": 0},
    "Eulogy Jones' suit": {"strength": 2, "perception": 2, "endurance": 1, "charisma": 2, "intelligence": 0, "agility": 0, "luck": 0},
    "Heavy synth armor": {"strength": 0, "perception": 0, "endurance": 4, "charisma": 3, "intelligence": 0, "agility": 0, "luck": 0},
    "Firefighter suit, rad helmet": {"strength": 0, "perception": 0, "endurance": 5, "charisma": 0, "intelligence": 2, "agility": 0, "luck": 0},
    "T-45a power armor": {"strength": 2, "perception": 3, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-45d power armor": {"strength": 2, "perception": 4, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-45f power armor": {"strength": 2, "perception": 5, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-51a power armor": {"strength": 3, "perception": 1, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-51d power armor": {"strength": 3, "perception": 2, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-51f power armor": {"strength": 4, "perception": 3, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-60a power armor": {"strength": 2, "perception": 0, "endurance": 3, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-60d power armor": {"strength": 2, "perception": 0, "endurance": 4, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "T-60f power armor": {"strength": 1, "perception": 1, "endurance": 5, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "X-01 Mk I power armor": {"strength": 3, "perception": 1, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "X-01 Mk IV power armor": {"strength": 4, "perception": 1, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "X-01 Mk VI power armor": {"strength": 5, "perception": 1, "endurance": 1, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "NCR Ranger outfit": {"strength": 0, "perception": 4, "endurance": 0, "charisma": 2, "intelligence": 0, "agility": 0, "luck": 0},
    "RobCo R&D suit": {"strength": 0, "perception": 0, "endurance": 2, "charisma": 0, "intelligence": 4, "agility": 0, "luck": 0},
    "Robot armor": {"strength": 2, "perception": 0, "endurance": 2, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 2},
    "Firefighter suit": {"strength": 0, "perception": 0, "endurance": 4, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "Hazmat suit": {"strength": 0, "perception": 0, "endurance": 2, "charisma": 0, "intelligence": 2, "agility": 0, "luck": 0},
    "Armored vault suit": {"strength": 0, "perception": 3, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "Sturdy vault suit": {"strength": 0, "perception": 5, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
    "Heavy vault suit": {"strength": 0, "perception": 7, "endurance": 0, "charisma": 0, "intelligence": 0, "agility": 0, "luck": 0},
}


def upgrade() -> None:
    for stat in SPECIAL_STATS:
        op.add_column("outfit", sa.Column(stat, sa.Integer(), nullable=False, server_default="0"))

    for name, bonuses in OUTFIT_SPECIAL_BONUSES.items():
        op.execute(
            sa.text(
                "UPDATE outfit SET strength = :strength, perception = :perception, endurance = :endurance, "
                "charisma = :charisma, intelligence = :intelligence, agility = :agility, luck = :luck "
                "WHERE name = :name"
            ).bindparams(name=name, **bonuses)
        )


def downgrade() -> None:
    for stat in SPECIAL_STATS:
        op.drop_column("outfit", stat)