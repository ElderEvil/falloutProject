from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration("2026_09_26_0001-e7f8a9b0c1d2_add_map_point_clear_state.py", "add_map_point_clear_state")


def test_revision_chain() -> None:
    assert MIGRATION.revision == "e7f8a9b0c1d2"
    assert MIGRATION.down_revision == "c6f1a2b3d4e5"
