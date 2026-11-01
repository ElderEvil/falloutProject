"""Regression coverage for the unused dweller index cleanup."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.models.dweller import Dweller

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_11_01_0002-d1f3a5c7e9b2_drop_unused_dweller_indexes.py"
)
INDEXES = {
    "ix_dweller_first_name": ("first_name",),
    "ix_dweller_last_name": ("last_name",),
    "ix_dweller_is_dead": ("is_dead",),
    "ix_dweller_is_permanently_dead": ("is_permanently_dead",),
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("drop_unused_dweller_indexes", MIGRATION_PATH)
    assert spec
    assert spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _index_names(connection) -> set[str]:
    return {
        row[1]
        for row in connection.execute(text('PRAGMA index_list("dweller")'))
        if not row[1].startswith("sqlite_autoindex_")
    }


def test_index_migration_drops_and_restores(monkeypatch):
    migration = _load_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                """CREATE TABLE dweller (
                id VARCHAR PRIMARY KEY,
                first_name VARCHAR,
                last_name VARCHAR,
                is_dead BOOLEAN,
                is_permanently_dead BOOLEAN
            )"""
            )
        )
        for index_name, columns in INDEXES.items():
            connection.execute(text(f"CREATE INDEX {index_name} ON dweller ({', '.join(columns)})"))
        assert _index_names(connection) == set(INDEXES)

        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert _index_names(connection) == set()

        migration.downgrade()
        assert _index_names(connection) == set(INDEXES)
    engine.dispose()


def test_dweller_model_no_longer_defines_dropped_indexes():
    assert {index.name for index in Dweller.__table__.indexes}.isdisjoint(INDEXES)
