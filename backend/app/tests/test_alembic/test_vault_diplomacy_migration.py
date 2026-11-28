from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.exc import IntegrityError

from app.tests.test_alembic._support import (
    BASELINE_VERSIONS,
    column_names,
    load_migration,
    migration_path,
    sqlite_db,
)

BACKEND = Path(__file__).resolve().parents[3]
REVISION = "e7b4c9d2a1f8"
PARENT = "b9d4e2f7a1c6"
MIGRATION_PATH = migration_path(REVISION, BASELINE_VERSIONS)
MIGRATION = load_migration(REVISION, "add_vault_diplomacy_tables", BASELINE_VERSIONS)


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


def test_upgrade_creates_both_tables_and_downgrade_drops_them() -> None:
    with sqlite_db() as connection:
        _install(connection)
        MIGRATION.upgrade()
        assert set(column_names(connection, "vaultrelation")) == {
            "id",
            "vault_a_id",
            "vault_b_id",
            "status",
            "standing",
            "met_at",
            "locked_until",
            "created_at",
            "updated_at",
        }
        assert set(column_names(connection, "diplomaticfiling")) == {
            "id",
            "from_vault_id",
            "to_vault_id",
            "kind",
            "terms",
            "status",
            "expires_at",
            "responded_at",
            "created_at",
            "updated_at",
        }
        relation_indexes = {row[1] for row in connection.exec_driver_sql("PRAGMA index_list(vaultrelation)")}
        assert {"ix_vaultrelation_status_locked_until", "ix_vaultrelation_vault_a_id"} <= relation_indexes
        filing_indexes = {row[1] for row in connection.exec_driver_sql("PRAGMA index_list(diplomaticfiling)")}
        assert {"ix_diplomaticfiling_pair_kind_status", "ix_diplomaticfiling_status_expires_at"} <= filing_indexes
        connection.exec_driver_sql(
            "INSERT INTO vaultrelation (id, vault_a_id, vault_b_id, status, standing, created_at, updated_at)"
            " VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1',"
            " '00000000-0000-0000-0000-0000000000b1', 'UNMET', 0, '2026-11-28 00:00:00', '2026-11-28 00:00:00')"
        )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "INSERT INTO vaultrelation (id, vault_a_id, vault_b_id, status, standing, created_at, updated_at)"
                " VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000a1',"
                " '00000000-0000-0000-0000-0000000000b1', 'CONTACT', 5, '2026-11-28 01:00:00',"
                " '2026-11-28 01:00:00')"
            )
        MIGRATION.downgrade()
        tables = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"vaultrelation", "diplomaticfiling"}.isdisjoint(tables)


def test_status_and_kind_are_plain_varchar_columns() -> None:
    source = MIGRATION_PATH.read_text()
    assert source.count("sa.String(length=16)") == 3
    assert "sa.Enum(" not in source
    assert "postgresql.ENUM" not in source
