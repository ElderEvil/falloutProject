"""Regression coverage for the expedition_run migration."""

import importlib.util
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[2] / "alembic/versions/2026_09_21_0001-b74a718e1e92_add_expedition_run.py"
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_expedition_run", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "b74a718e1e92"
    assert MIGRATION.down_revision == "f0e1d2c3b4a5"


def test_open_run_partial_unique_index() -> None:
    import inspect

    source = inspect.getsource(MIGRATION.upgrade)
    assert "uq_expeditionrun_open_exploration" in source
    assert "ENTERED" in source
    assert "IN_ROOM" in source
