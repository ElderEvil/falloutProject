"""Tests for outfit image asset resolution."""

from app.utils.outfit_assets import OUTFIT_NAME_TO_IMAGE_FILE, get_outfit_image_url
from app.utils.static_data import game_data_store


def test_get_outfit_image_url_returns_static_path_for_mapped_outfits() -> None:
    assert get_outfit_image_url("Autumn's uniform") == "/static/apparel_images/FOS Autumn Uniform.png"
    assert get_outfit_image_url("Bittercup's outfit") == "/static/apparel_images/FOS Bittercup Outfit.png"
    assert get_outfit_image_url("T-51d power armor") == "/static/apparel_images/FOS T51 Outfit.png"


def test_get_outfit_image_url_is_case_and_whitespace_insensitive() -> None:
    assert get_outfit_image_url("  autumn's uniform  ") == "/static/apparel_images/FOS Autumn Uniform.png"
    assert get_outfit_image_url("T-51D POWER ARMOR") == "/static/apparel_images/FOS T51 Outfit.png"


def test_get_outfit_image_url_returns_none_for_unknown_outfit() -> None:
    assert get_outfit_image_url("Nonexistent outfit") is None


def test_get_outfit_image_url_returns_none_for_empty_name() -> None:
    assert get_outfit_image_url("") is None
    assert get_outfit_image_url(None) is None


def test_static_data_outfits_have_image_urls() -> None:
    outfits = game_data_store.outfits

    for outfit in outfits:
        assert outfit.name.casefold() in OUTFIT_NAME_TO_IMAGE_FILE, f"{outfit.name} has no apparel image mapping"
        assert outfit.image_url is not None, f"{outfit.name} should have an image_url"
        assert outfit.image_url.startswith("/static/apparel_images/")
