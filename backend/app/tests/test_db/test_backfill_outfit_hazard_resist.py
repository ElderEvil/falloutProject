"""Regression coverage for the outfit hazard-resistance backfill migration.

The hazard-resistance columns shipped with ``fire_resist`` defaulting to 0 and
``radiation_resist`` left NULL, so every outfit row created before them granted
no fire or radiation protection. The migration enriches those rows from a frozen
catalog snapshot; this test pins the mapping it applies and the per-column
default guards that keep it idempotent and non-destructive.
"""

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic/versions/2026_09_21_0001-e5f6a7b8c9d0_backfill_outfit_hazard_resist.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("backfill_outfit_hazard_resist", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_backfill_uses_catalog_fire_resistance() -> None:
    assert MIGRATION.FIRE_RESIST_BY_NAME == {
        "firefighter suit": 0.5,
        "firefighter suit, rad helmet": 0.75,
    }


def test_backfill_uses_catalog_radiation_resistance() -> None:
    assert MIGRATION.RADIATION_RESIST_BY_NAME == {
        "firefighter suit": 0.0,
        "firefighter suit, rad helmet": 1.0,
        "hazmat suit": 1.0,
    }


def test_update_sql_guards_on_each_column_own_default() -> None:
    fire_sql = str(MIGRATION.FIRE_UPDATE_SQL)
    assert "LOWER(TRIM(name)) = :name" in fire_sql
    assert "fire_resist = :fire_resist" in fire_sql
    assert "fire_resist = 0" in fire_sql

    radiation_sql = str(MIGRATION.RADIATION_UPDATE_SQL)
    assert "LOWER(TRIM(name)) = :name" in radiation_sql
    assert "radiation_resist = :radiation_resist" in radiation_sql
    assert "radiation_resist IS NULL" in radiation_sql
