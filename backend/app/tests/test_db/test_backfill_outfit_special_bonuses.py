"""Regression coverage for the outfit SPECIAL backfill migration.

The SPECIAL columns shipped with a zero default, so every outfit row created
before them rendered no stat rows on the item / dweller-equipment cards. The
migration enriches those rows from the catalog plus the seed-only starter list;
this test pins the mapping it applies and the all-zero guard that keeps it
idempotent and non-destructive.
"""

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_09_19_0002-b7c8d9e0f1a2_backfill_outfit_special_bonuses.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("backfill_outfit_special_bonuses", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_backfill_uses_catalog_stats_for_legendary_dweller_outfits() -> None:
    expected = {
        "abraham's relaxedwear": {"strength": 1, "perception": 2, "endurance": 2, "charisma": 1},
        "bittercup's outfit": {"strength": 2, "perception": 2, "endurance": 2, "charisma": 1},
        "eulogy jones' suit": {"strength": 2, "perception": 2, "endurance": 1, "charisma": 2},
    }
    for name, stats in expected.items():
        bonuses = MIGRATION.SPECIAL_BY_NAME[name]
        assert {key: bonuses[key] for key in stats} == stats


def test_backfill_covers_seed_only_starter_outfits() -> None:
    expected = {
        "vault jumpsuit": {"charisma": 1, "luck": 1},
        "leather armor": {"strength": 1, "agility": 1},
        "metal armor": {"strength": 2, "endurance": 1},
        "t-51b power armor": {"strength": 3, "perception": 1, "endurance": 2},
    }
    for name, stats in expected.items():
        bonuses = MIGRATION.SPECIAL_BY_NAME[name]
        assert {key: bonuses[key] for key in stats} == stats


def test_every_backfilled_outfit_carries_all_seven_stats() -> None:
    keys = set(MIGRATION.SPECIAL_KEYS)
    assert keys == {"strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"}
    for name, bonuses in MIGRATION.SPECIAL_BY_NAME.items():
        assert set(bonuses) == keys, name


def test_update_sql_sets_every_stat_and_guards_on_all_zero() -> None:
    sql = str(MIGRATION.UPDATE_SQL)
    assert "LOWER(TRIM(name)) = :name" in sql
    for key in MIGRATION.SPECIAL_KEYS:
        assert f"{key} = :{key}" in sql
        assert f"COALESCE({key}, 0) = 0" in sql
