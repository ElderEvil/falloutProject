from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration(
    "2026_09_26_0002-401f95d70b98_add_exploration_dispatch_target.py", "add_exploration_dispatch_target"
)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "401f95d70b98"
    assert MIGRATION.down_revision == "e7f8a9b0c1d2"
