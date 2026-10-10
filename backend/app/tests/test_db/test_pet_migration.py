"""Regression coverage for the pet domain migration (plan §5.5).

Pins the revision chain, the idempotent legacy Item→Pet backfill guard, and the
downgrade that re-inserts legacy ``item`` rows.
"""

import importlib.util
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[2] / "alembic/versions/2026_10_01_0001-c19031dc6b22_add_pet_domain.py"
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_pet_domain", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "c19031dc6b22"
    assert MIGRATION.down_revision == "907b110e6ae4"


def test_backfill_guards_on_legacy_item_id() -> None:
    sql = str(MIGRATION.BACKFILL_SQL)
    assert "item_type = 'pet'" in sql
    assert "NOT EXISTS (SELECT 1 FROM pet p WHERE p.legacy_item_id = item.id)" in sql


def test_upgrade_deletes_legacy_items() -> None:
    sql = str(MIGRATION.DELETE_LEGACY_SQL)
    assert "DELETE FROM item WHERE item_type = 'pet'" in sql


def test_downgrade_restores_legacy_items() -> None:
    sql = str(MIGRATION.RESTORE_LEGACY_SQL)
    assert "INSERT INTO item" in sql
    assert "legacy_item_id IS NOT NULL" in sql
    assert "'pet'" in sql
