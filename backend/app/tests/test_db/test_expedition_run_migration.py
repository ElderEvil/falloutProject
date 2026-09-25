"""Regression coverage for the expedition_run migrations."""

import importlib.util
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[2] / "alembic/versions/2026_09_25_0001-b74a718e1e92_add_expedition_run.py"
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_expedition_run", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)

VAULT_SITE_MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_09_25_1825-f2cfb4f037d0_add_expeditionrun_open_vault_site_.py"
)
VAULT_SITE_MIGRATION_SPEC = importlib.util.spec_from_file_location(
    "add_expeditionrun_open_vault_site", VAULT_SITE_MIGRATION_PATH
)
assert VAULT_SITE_MIGRATION_SPEC
assert VAULT_SITE_MIGRATION_SPEC.loader
VAULT_SITE_MIGRATION = importlib.util.module_from_spec(VAULT_SITE_MIGRATION_SPEC)
VAULT_SITE_MIGRATION_SPEC.loader.exec_module(VAULT_SITE_MIGRATION)

RENAME_MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic/versions/2026_09_25_1900-b80551876fa9_rename_expeditionrun_cleared_at_to_finished_at.py"
)
RENAME_MIGRATION_SPEC = importlib.util.spec_from_file_location(
    "rename_expeditionrun_cleared_at_to_finished_at", RENAME_MIGRATION_PATH
)
assert RENAME_MIGRATION_SPEC
assert RENAME_MIGRATION_SPEC.loader
RENAME_MIGRATION = importlib.util.module_from_spec(RENAME_MIGRATION_SPEC)
RENAME_MIGRATION_SPEC.loader.exec_module(RENAME_MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "b74a718e1e92"
    assert MIGRATION.down_revision == "f4e5d6c7b8a9"


def test_open_run_partial_unique_index() -> None:
    import inspect

    source = inspect.getsource(MIGRATION.upgrade)
    assert "uq_expeditionrun_open_exploration" in source
    assert "ENTERED" in source
    assert "IN_ROOM" in source


def test_vault_site_index_revision_chain() -> None:
    assert VAULT_SITE_MIGRATION.revision == "f2cfb4f037d0"
    assert VAULT_SITE_MIGRATION.down_revision == "b74a718e1e92"


def test_vault_site_partial_unique_index() -> None:
    import inspect

    source = inspect.getsource(VAULT_SITE_MIGRATION.upgrade)
    assert "uq_expeditionrun_open_vault_site" in source
    assert "vault_id" in source
    assert "site_id" in source
    assert "ENTERED" in source
    assert "IN_ROOM" in source
    downgrade = inspect.getsource(VAULT_SITE_MIGRATION.downgrade)
    assert "drop_index" in downgrade


def test_rename_revision_chain() -> None:
    assert RENAME_MIGRATION.revision == "b80551876fa9"
    assert RENAME_MIGRATION.down_revision == "f2cfb4f037d0"


def test_rename_uses_alter_column() -> None:
    import inspect

    upgrade = inspect.getsource(RENAME_MIGRATION.upgrade)
    assert "alter_column" in upgrade
    assert "cleared_at" in upgrade
    assert "finished_at" in upgrade
    downgrade = inspect.getsource(RENAME_MIGRATION.downgrade)
    assert "alter_column" in downgrade
    assert "finished_at" in downgrade
    assert "cleared_at" in downgrade
