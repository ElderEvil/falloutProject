from __future__ import annotations

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
REVISION = "d4c8a1f6e293"
PARENT = "e5a1b7c9d2f3"
MIGRATION_PATH = migration_path(REVISION, BASELINE_VERSIONS)
MIGRATION = load_migration(REVISION, "add_pvp_duels", BASELINE_VERSIONS)


def _install(connection) -> None:
    MIGRATION.op = Operations(MigrationContext.configure(connection))
    MIGRATION.context = SimpleNamespace(is_offline_mode=lambda: False)


def test_revision_chain_and_single_head() -> None:
    assert MIGRATION.revision == REVISION
    assert MIGRATION.down_revision == PARENT
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1, f"expected one head, got {heads}"
    assert REVISION in {rev.revision for rev in script.walk_revisions()}


def test_upgrade_creates_table_and_downgrade_drops_it() -> None:
    with sqlite_db() as connection:
        _install(connection)
        MIGRATION.upgrade()
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(pvpduel)")}
        assert {
            "id",
            "challenger_vault_id",
            "defender_vault_id",
            "status",
            "challenger_snapshot",
            "defender_snapshot",
            "outcome",
            "journal",
            "created_at",
            "accepted_at",
            "expires_at",
        } == columns
        indexes = {row[1] for row in connection.exec_driver_sql("PRAGMA index_list(pvpduel)")}
        assert "ix_pvpduel_status_expires_at" in indexes
        assert "ix_pvpduel_challenger_vault_id" in indexes
        connection.exec_driver_sql(
            "INSERT INTO pvpduel (id, challenger_vault_id, status, challenger_snapshot, created_at, expires_at)"
            " VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000f1',"
            " 'OPEN', '{}', '2026-11-21 00:00:00', '2026-11-22 00:00:00')"
        )
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM pvpduel").scalar_one() == 1
        MIGRATION.downgrade()
        tables = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "pvpduel" not in tables


def test_status_is_a_plain_varchar_column() -> None:
    source = MIGRATION_PATH.read_text()
    assert "sqlmodel.sql.sqltypes.AutoString(length=20)" in source
    assert '"status"' in source
    assert 'sa.Enum("OPEN"' not in source
