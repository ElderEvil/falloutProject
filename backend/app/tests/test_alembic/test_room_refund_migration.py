from sqlalchemy import inspect

from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db


def test_room_refund_migration_keeps_existing_rows_unallocated():
    migration = load_migration("2026_10_17_0001-e6b91c48a732_add_room_refund_caps.py", "room_refund_migration")
    with sqlite_db("CREATE TABLE room (id INTEGER PRIMARY KEY)", "INSERT INTO room (id) VALUES (1)") as db:
        bind_op(migration, db)
        migration.upgrade()
        assert db.exec_driver_sql("SELECT refund_caps FROM room").scalar_one() is None
        db.exec_driver_sql("UPDATE room SET refund_caps = 0")
        assert db.exec_driver_sql("SELECT refund_caps FROM room").scalar_one() == 0
        migration.downgrade()
        assert [column["name"] for column in inspect(db).get_columns("room")] == ["id"]
