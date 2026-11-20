"""Rotation periods ship NULL so the first ensure call rolls instead of waiting a period."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/baseline_versions/2026_11_20_0002-b3f7a2c9d4e8_quest_rotation_periods.py"
)


def test_quest_rotation_migration_adds_nullable_unadopted_periods(monkeypatch):
    spec = importlib.util.spec_from_file_location("quest_rotation_periods", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as db:
        db.exec_driver_sql("CREATE TABLE gamestate (id INTEGER PRIMARY KEY)")
        db.exec_driver_sql("INSERT INTO gamestate VALUES (1)")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(db)))
        migration.upgrade()
        columns = [column[1] for column in db.exec_driver_sql("PRAGMA table_info(gamestate)")]
        assert {"daily_quests_period", "weekly_quests_period"} <= set(columns)
        assert db.exec_driver_sql("SELECT daily_quests_period, weekly_quests_period FROM gamestate").one() == (
            None,
            None,
        )
        migration.downgrade()
        assert [column[1] for column in db.exec_driver_sql("PRAGMA table_info(gamestate)")] == ["id"]
    engine.dispose()
