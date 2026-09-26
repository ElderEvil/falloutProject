"""Regression coverage for the exploration dispatch-target migration (issue 772)."""

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_09_26_0002-401f95d70b98_add_exploration_dispatch_target.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_exploration_dispatch_target", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "401f95d70b98"
    assert MIGRATION.down_revision == "e7f8a9b0c1d2"


def test_upgrade_adds_dispatch_columns() -> None:
    import inspect

    source = inspect.getsource(MIGRATION.upgrade)
    assert "target_location_id" in source
    assert "clear_tier" in source
    assert "worldlocation" in source


def test_downgrade_drops_dispatch_columns() -> None:
    import inspect

    source = inspect.getsource(MIGRATION.downgrade)
    assert "target_location_id" in source
    assert "clear_tier" in source
