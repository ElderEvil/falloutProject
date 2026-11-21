"""World event migration: both tables, the unique participation key, the ACTIVE guard.

The create/drop round trip runs on SQLite; the PG-only shapes (native enum, partial index
predicate) are pinned by reading the migration source, since SQLite has neither.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[3]
REVISION = "c1d4e7f0a2b9"
PARENT = "b3f7a2c9d4e8"
MIGRATIONS_DIR = BACKEND / "app/alembic/baseline_versions"


def _find_migration() -> Path:
    matches = sorted(MIGRATIONS_DIR.glob(f"*-{REVISION}_*.py"))
    assert len(matches) == 1, f"expected one migration for {REVISION}, found {matches}"
    return matches[0]


MIGRATION_PATH = _find_migration()
SPEC = importlib.util.spec_from_file_location("add_world_events", MIGRATION_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _install(connection) -> None:
    MIGRATION.op = Operations(MigrationContext.configure(connection))
    MIGRATION.context = SimpleNamespace(is_offline_mode=lambda: False)


def _columns(connection, table: str) -> set[str]:
    return {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}


def _index_names(connection, table: str) -> set[str]:
    return {row[1] for row in connection.exec_driver_sql(f"PRAGMA index_list({table})")}


def _unique_index_column_sets(connection, table: str) -> set[tuple[str, ...]]:
    """Column tuples of every unique index (SQLite auto-names named constraints)."""
    result = set()
    for row in connection.exec_driver_sql(f"PRAGMA index_list({table})"):
        if row[2]:
            columns = tuple(col[2] for col in connection.exec_driver_sql(f"PRAGMA index_info({row[1]})"))
            result.add(columns)
    return result


def test_revision_chain_and_single_head() -> None:
    assert MIGRATION.revision == REVISION
    assert MIGRATION.down_revision == PARENT
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1, f"expected one head, got {heads}"
    assert REVISION in {rev.revision for rev in script.walk_revisions()}


def test_upgrade_creates_both_tables_and_downgrade_drops_them() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _install(connection)
        MIGRATION.upgrade()

        assert {
            "id",
            "kind",
            "title",
            "description",
            "target_amount",
            "progress_amount",
            "personal_min",
            "reward",
            "starts_at",
            "ends_at",
            "status",
            "extended_at",
            "created_at",
            "updated_at",
        } <= _columns(connection, "worldevent")
        assert {
            "id",
            "world_event_id",
            "vault_id",
            "contribution",
            "reward_claimed_at",
            "created_at",
            "updated_at",
        } <= _columns(connection, "worldeventparticipation")

        assert "uq_world_event_single_active" in _index_names(connection, "worldevent")
        assert ("world_event_id", "vault_id") in _unique_index_column_sets(connection, "worldeventparticipation")

        # The JSONB reward column accepts the empty default payload.
        connection.exec_driver_sql(
            "INSERT INTO worldevent (id, kind, title, description, target_amount, progress_amount,"
            " personal_min, reward, starts_at, ends_at, status) VALUES"
            " ('00000000-0000-0000-0000-000000000001', 'caps', 't', 'd', 10, 0, 1, '[]',"
            " '2026-11-21 00:00:00', '2026-11-28 00:00:00', 'SCHEDULED')"
        )
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM worldevent").scalar_one() == 1

        MIGRATION.downgrade()
        tables = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "worldevent" not in tables
        assert "worldeventparticipation" not in tables
    engine.dispose()


def test_participation_is_unique_per_event_and_vault() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _install(connection)
        MIGRATION.upgrade()
        connection.exec_driver_sql(
            "INSERT INTO worldeventparticipation (id, world_event_id, vault_id, contribution)"
            " VALUES ('00000000-0000-0000-0000-00000000000a',"
            " '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000f1', 5)"
        )
        with pytest.raises(sa.exc.IntegrityError):
            connection.exec_driver_sql(
                "INSERT INTO worldeventparticipation (id, world_event_id, vault_id, contribution)"
                " VALUES ('00000000-0000-0000-0000-00000000000b',"
                " '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000f1', 6)"
            )
    engine.dispose()


def test_partial_active_index_and_native_enum_are_declared() -> None:
    """SQLite cannot express either shape; pin them from the migration source."""
    source = MIGRATION_PATH.read_text()
    index_block = re.search(r"op\.create_index\(\s*\"uq_world_event_single_active\".*?\n    \)", source, re.DOTALL)
    assert index_block, "uq_world_event_single_active index declaration not found"
    assert '["status"]' in index_block.group(0)
    assert "unique=True" in index_block.group(0)
    assert "postgresql_where=sa.text(\"status = 'ACTIVE'\")" in index_block.group(0)
    assert 'sa.Enum("SCHEDULED", "ACTIVE", "COMPLETED", "EXPIRED", name="worldeventstatus")' in source
    assert 'sa.Enum(name="worldeventstatus").drop(op.get_bind(), checkfirst=True)' in source
