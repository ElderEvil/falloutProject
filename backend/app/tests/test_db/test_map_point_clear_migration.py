"""Regression coverage for the map-point clear state migration (issue 772)."""

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_09_26_0001-e7f8a9b0c1d2_add_map_point_clear_state.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_map_point_clear_state", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "e7f8a9b0c1d2"
    assert MIGRATION.down_revision == "c6f1a2b3d4e5"
