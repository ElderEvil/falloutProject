from datetime import datetime, timedelta

from app.tests.test_alembic._support import bind_op, column_names, load_migration, sqlite_db
from app.utils.time import as_naive_utc, utcnow


def test_refresh_migration_adopts_periods_and_downgrades():
    migration = load_migration(
        "2026_10_18_0001-a8c41e06d925_objective_refresh_periods.py", "objective_refresh_migration"
    )
    with sqlite_db("CREATE TABLE gamestate (id INTEGER PRIMARY KEY)", "INSERT INTO gamestate VALUES (1)") as db:
        bind_op(migration, db)
        before = as_naive_utc(utcnow()).replace(hour=0, minute=0, second=0, microsecond=0)
        migration.upgrade()
        daily, weekly = db.exec_driver_sql(
            "SELECT daily_objectives_period,weekly_objectives_period FROM gamestate"
        ).one()
        daily, weekly = datetime.fromisoformat(daily), datetime.fromisoformat(weekly)
        assert daily == before
        assert weekly == before - timedelta(days=before.weekday())
        migration.downgrade()
        assert column_names(db, "gamestate") == ["id"]
