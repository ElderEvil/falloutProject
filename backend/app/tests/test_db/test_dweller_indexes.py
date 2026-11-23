from sqlalchemy import text

from app.models.dweller import Dweller
from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

MIGRATION = load_migration("2026_11_01_0002-d1f3a5c7e9b2_drop_unused_dweller_indexes.py", "drop_unused_dweller_indexes")
INDEXES = {
    "ix_dweller_first_name": ("first_name",),
    "ix_dweller_last_name": ("last_name",),
    "ix_dweller_is_dead": ("is_dead",),
    "ix_dweller_is_permanently_dead": ("is_permanently_dead",),
}


def _index_names(connection) -> set[str]:
    return {
        row[1]
        for row in connection.execute(text('PRAGMA index_list("dweller")'))
        if not row[1].startswith("sqlite_autoindex_")
    }


def test_index_migration_drops_and_restores():
    with sqlite_db(
        """CREATE TABLE dweller (
            id VARCHAR PRIMARY KEY,
            first_name VARCHAR,
            last_name VARCHAR,
            is_dead BOOLEAN,
            is_permanently_dead BOOLEAN
        )"""
    ) as connection:
        for index_name, columns in INDEXES.items():
            connection.execute(text(f"CREATE INDEX {index_name} ON dweller ({', '.join(columns)})"))
        assert _index_names(connection) == set(INDEXES)
        bind_op(MIGRATION, connection)
        MIGRATION.upgrade()
        assert _index_names(connection) == set()
        MIGRATION.downgrade()
        assert _index_names(connection) == set(INDEXES)


def test_dweller_model_no_longer_defines_dropped_indexes():
    assert {index.name for index in Dweller.__table__.indexes}.isdisjoint(INDEXES)
