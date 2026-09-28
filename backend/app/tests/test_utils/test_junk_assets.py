from pathlib import Path

from app.utils.junk_assets import JUNK_NAME_TO_IMAGE_FILE, get_junk_image_url
from app.utils.static_data import game_data_store

JUNK_IMAGE_DIR = Path(__file__).parent.parent.parent / "static" / "junk_images"


def test_every_catalog_junk_has_its_own_image() -> None:
    """No catalog junk may go imageless (duct tape shares the military art)."""
    for junk in game_data_store.junk_items:
        assert junk.name.strip().casefold() in JUNK_NAME_TO_IMAGE_FILE, junk.name
        assert junk.image_url is not None, junk.name
        assert junk.image_url.startswith("/static/junk_images/")


def test_every_mapped_junk_file_exists_on_disk() -> None:
    missing = [f for f in set(JUNK_NAME_TO_IMAGE_FILE.values()) if not (JUNK_IMAGE_DIR / f).exists()]
    assert missing == []


def test_junk_lookup_is_case_insensitive() -> None:
    assert get_junk_image_url("  Teddy Bear ") == "/static/junk_images/FOS Teddy bear.png"
    assert get_junk_image_url("Wonderglue") == "/static/junk_images/FOS Wonderglue.png"


def test_unknown_or_missing_junk_has_no_url() -> None:
    assert get_junk_image_url("Steel") is None
    assert get_junk_image_url(None) is None
    assert get_junk_image_url("  ") is None
