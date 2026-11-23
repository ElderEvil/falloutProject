import inspect

from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration("9f0a1b2c3d4e", "backfill_item_art_image_urls")


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
    source = inspect.getsource(MIGRATION.upgrade)
    assert source.count("image_url IS NULL OR image_url <> :url") == 3


def test_never_clobbers_uploaded_dweller_portraits() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert "image_url LIKE '/static/legendary_dweller_images/%'" in source
    assert "image_url LIKE '/static/legendary_dweller_images/%' AND image_url <> :url" in source


def test_downgrade_is_noop() -> None:
    assert "No-op" in inspect.getsource(MIGRATION.downgrade)
