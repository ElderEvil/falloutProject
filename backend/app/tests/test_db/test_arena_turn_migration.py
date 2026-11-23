from sqlalchemy import inspect, text

from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db


def test_arena_turn_migration_backfills_and_downgrades():
    migration = load_migration("2026_10_18_0002-c72b4e6f109a_add_arena_attack_turn.py", "arena_turn")
    with sqlite_db(
        "CREATE TABLE arena_state (room_id VARCHAR PRIMARY KEY)",
        "INSERT INTO arena_state (room_id) VALUES ('existing')",
    ) as connection:
        bind_op(migration, connection)
        migration.upgrade()
        connection.execute(text("INSERT INTO arena_state (room_id) VALUES ('new')"))
        assert connection.execute(
            text("SELECT next_attack_team FROM arena_state ORDER BY room_id")
        ).scalars().all() == [
            "A",
            "A",
        ]
        connection.execute(text("UPDATE arena_state SET next_attack_team = 'B' WHERE room_id = 'existing'"))
        assert (
            connection.execute(text("SELECT next_attack_team FROM arena_state WHERE room_id = 'existing'")).scalar_one()
            == "B"
        )
        migration.downgrade()
        assert [column["name"] for column in inspect(connection).get_columns("arena_state")] == ["room_id"]
        assert connection.execute(text("SELECT COUNT(*) FROM arena_state")).scalar_one() == 2
