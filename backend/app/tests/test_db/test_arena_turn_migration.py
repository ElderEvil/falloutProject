"""The turn migration must backfill existing matches and default new rows to A."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_arena_turn_migration_backfills_and_downgrades():
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_18_0002-c72b4e6f109a_add_arena_attack_turn.py"
    spec = importlib.util.spec_from_file_location("arena_turn", path)
    assert spec
    assert spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with create_engine("sqlite://").begin() as connection:
        connection.execute(text("CREATE TABLE arena_state (room_id VARCHAR PRIMARY KEY)"))
        connection.execute(text("INSERT INTO arena_state (room_id) VALUES ('existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            connection.execute(text("INSERT INTO arena_state (room_id) VALUES ('new')"))
            assert connection.execute(
                text("SELECT next_attack_team FROM arena_state ORDER BY room_id")
            ).scalars().all() == ["A", "A"]
            connection.execute(text("UPDATE arena_state SET next_attack_team = 'B' WHERE room_id = 'existing'"))
            assert (
                connection.execute(
                    text("SELECT next_attack_team FROM arena_state WHERE room_id = 'existing'")
                ).scalar_one()
                == "B"
            )
            migration.downgrade()
        assert [column["name"] for column in inspect(connection).get_columns("arena_state")] == ["room_id"]
        assert connection.execute(text("SELECT COUNT(*) FROM arena_state")).scalar_one() == 2
