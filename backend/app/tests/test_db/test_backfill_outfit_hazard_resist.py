from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration(
    "2026_09_21_0001-e5f6a7b8c9d0_backfill_outfit_hazard_resist.py", "backfill_outfit_hazard_resist"
)


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
