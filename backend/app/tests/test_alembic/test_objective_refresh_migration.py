"""Existing assignments are adopted for the current UTC periods on deployment."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_refresh_migration_adopts_periods_and_downgrades(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_18_0001-a8c41e06d925_objective_refresh_periods.py"
    spec = importlib.util.spec_from_file_location("objective_refresh_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as db:
        db.exec_driver_sql("CREATE TABLE gamestate (id INTEGER PRIMARY KEY)")
        db.exec_driver_sql("INSERT INTO gamestate VALUES (1)")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(db)))
        before = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        migration.upgrade()
        daily, weekly = db.exec_driver_sql(
            "SELECT daily_objectives_period,weekly_objectives_period FROM gamestate"
        ).one()
        daily, weekly = datetime.fromisoformat(daily), datetime.fromisoformat(weekly)
        assert daily == before
        assert weekly == before - timedelta(days=before.weekday())
        migration.downgrade()
        assert [column[1] for column in db.exec_driver_sql("PRAGMA table_info(gamestate)")] == ["id"]
    engine.dispose()
