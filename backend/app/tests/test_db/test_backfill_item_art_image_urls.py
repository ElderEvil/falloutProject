"""Regression coverage for the item / legendary-dweller image URL backfill migration.

``image_url`` is persisted on rows, and the earlier image backfills only filled
``image_url IS NULL``. Every weapon that was unmapped when they ran already carries the
old generic ``10mm pistol FOS.png`` fallback, so it keeps a stale non-null value and
never picks up the widened art map. This pins the revision chain and the guards that keep
the re-resolve idempotent (write only when the value differs) and non-destructive (never
touch a dweller portrait that is not a catalog-managed static URL).
"""

import importlib.util
import inspect
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_09_28_0002-9f0a1b2c3d4e_backfill_item_art_image_urls.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("backfill_item_art_image_urls", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "9f0a1b2c3d4e"
    assert MIGRATION.down_revision == "c7e2b34a9d01"


def test_reresolves_every_item_table_and_legendary_dwellers() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert "UPDATE weapon SET image_url = :url" in source
    assert "UPDATE outfit SET image_url = :url" in source
    assert "UPDATE junk SET image_url = :url" in source
    assert "UPDATE dweller SET image_url = :url" in source


def test_item_updates_are_idempotent() -> None:
    """Each item table only writes when the stored URL differs from the canonical one."""
    source = inspect.getsource(MIGRATION.upgrade)
    assert source.count("image_url IS NULL OR image_url <> :url") == 3


def test_never_clobbers_uploaded_dweller_portraits() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert "image_url LIKE '/static/legendary_dweller_images/%'" in source
    assert "image_url LIKE '/static/legendary_dweller_images/%' AND image_url <> :url" in source


def test_downgrade_is_noop() -> None:
    assert "No-op" in inspect.getsource(MIGRATION.downgrade)
