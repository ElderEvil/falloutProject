"""add outfit SPECIAL bonus columns

Revision ID: c3d4e5f6a7b8
Revises: 7b2c4d9e1f30
Create Date: 2026-09-18 00:00:00.000000
"""

import json
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "7b2c4d9e1f30"
branch_labels = None
depends_on = None

SPECIAL_STATS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")

#: Catalog files are the source of truth for outfit bonuses; names are unique
#: across the five files, so a name match is a safe backfill key.
_CATALOG_DIR = Path(__file__).resolve().parents[2] / "data" / "items" / "outfits"


def _catalog_bonuses() -> dict[str, dict[str, int]]:
    bonuses: dict[str, dict[str, int]] = {}
    for catalog_file in sorted(_CATALOG_DIR.glob("*.json")):
        for item in json.loads(catalog_file.read_text()):
            name = str(item["name"])
            bonuses[name] = {stat: int(item.get(stat, 0)) for stat in SPECIAL_STATS}
    return bonuses


def upgrade() -> None:
    for stat in SPECIAL_STATS:
        op.add_column("outfit", sa.Column(stat, sa.Integer(), nullable=False, server_default="0"))

    for name, bonuses in _catalog_bonuses().items():
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
