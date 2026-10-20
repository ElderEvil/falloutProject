"""Untouched rooms retain formula-based refunds; zero is a real allocated refund."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_room_refund_migration_keeps_existing_rows_unallocated(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_17_0001-e6b91c48a732_add_room_refund_caps.py"
    spec = importlib.util.spec_from_file_location("room_refund_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE room (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO room (id) VALUES (1)")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert connection.exec_driver_sql("SELECT refund_caps FROM room").scalar_one() is None
        connection.exec_driver_sql("UPDATE room SET refund_caps = 0")
        assert connection.exec_driver_sql("SELECT refund_caps FROM room").scalar_one() == 0
        migration.downgrade()
        assert [column["name"] for column in sa.inspect(connection).get_columns("room")] == ["id"]
    engine.dispose()
