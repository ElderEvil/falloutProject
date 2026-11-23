from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.tests.test_alembic._support import BASELINE_VERSIONS, load_migration, migration_path, sqlite_db

BACKEND = Path(__file__).resolve().parents[3]
REVISION = "c1d4e7f0a2b9"
PARENT = "b3f7a2c9d4e8"
MIGRATION_PATH = migration_path(REVISION, BASELINE_VERSIONS)
MIGRATION = load_migration(REVISION, "add_world_events", BASELINE_VERSIONS)


def _install(connection) -> None:
    MIGRATION.op = Operations(MigrationContext.configure(connection))
    MIGRATION.context = SimpleNamespace(is_offline_mode=lambda: False)


def _columns(connection, table: str) -> set[str]:
    return {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}


def _index_names(connection, table: str) -> set[str]:
    return {row[1] for row in connection.exec_driver_sql(f"PRAGMA index_list({table})")}


def _unique_index_column_sets(connection, table: str) -> set[tuple[str, ...]]:
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
    with sqlite_db() as connection:
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


def test_participation_is_unique_per_event_and_vault() -> None:
    with sqlite_db() as connection:
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


def test_partial_active_index_and_native_enum_are_declared() -> None:
    source = MIGRATION_PATH.read_text()
    index_block = re.search(r"op\.create_index\(\s*\"uq_world_event_single_active\".*?\n    \)", source, re.DOTALL)
    assert index_block, "uq_world_event_single_active index declaration not found"
    assert '["status"]' in index_block.group(0)
    assert "unique=True" in index_block.group(0)
    assert "postgresql_where=sa.text(\"status = 'ACTIVE'\")" in index_block.group(0)
    assert 'sa.Enum("SCHEDULED", "ACTIVE", "COMPLETED", "EXPIRED", name="worldeventstatus")' in source
    assert 'sa.Enum(name="worldeventstatus").drop(op.get_bind(), checkfirst=True)' in source
