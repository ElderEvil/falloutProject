from pathlib import Path

import pytest

from app.utils import weapon_assets
from app.utils.legendary_dweller_assets import (
    LEGENDARY_DWELLER_IMAGE_FILES,
    get_legendary_dweller_image_url,
)
from app.utils.static_data import game_data_store
from app.utils.weapon_assets import WEAPON_NAME_TO_IMAGE_FILE, get_weapon_image_url

WEAPON_IMAGE_DIR = Path(__file__).parent.parent.parent / "static" / "weapon_images"
LEGENDARY_IMAGE_DIR = Path(__file__).parent.parent.parent / "static" / "legendary_dweller_images"


@pytest.fixture
def isolated_weapon_art(tmp_path, monkeypatch):
    monkeypatch.setattr(weapon_assets, "_WEAPON_IMAGE_DIR", tmp_path / "weapon_images")
    weapon_assets._disk_index.cache_clear()
    yield weapon_assets._WEAPON_IMAGE_DIR
    weapon_assets._disk_index.cache_clear()


def test_weapon_filename_lookup_keeps_its_lazy_directory_snapshot(isolated_weapon_art):
    isolated_weapon_art.mkdir()
    (isolated_weapon_art / "Prototype blaster FOS.png").touch()
    (isolated_weapon_art / "10mm pistol FOS.png").touch()
    assert get_weapon_image_url("PROTOTYPE BLASTER") == "/static/weapon_images/Prototype blaster FOS.png"

    (isolated_weapon_art / "Future blaster FOS.png").touch()
    assert get_weapon_image_url("Future blaster") == "/static/weapon_images/10mm pistol FOS.png"
    weapon_assets._disk_index.cache_clear()
    assert get_weapon_image_url("Future blaster") == "/static/weapon_images/Future blaster FOS.png"


def test_weapon_filename_lookup_caches_a_missing_directory(isolated_weapon_art):
    assert get_weapon_image_url("Prototype blaster") is None
    isolated_weapon_art.mkdir()
    (isolated_weapon_art / "Prototype blaster FOS.png").touch()
    assert get_weapon_image_url("Prototype blaster") is None
    weapon_assets._disk_index.cache_clear()
    assert get_weapon_image_url("Prototype blaster") == "/static/weapon_images/Prototype blaster FOS.png"


def test_static_weapons_have_image_urls() -> None:
    assert all(weapon.image_url for weapon in game_data_store.weapons)
    assert get_weapon_image_url("Laser pistol") == "/static/weapon_images/Laser pistol FOS.png"


def test_every_catalog_weapon_has_its_own_image() -> None:
    """No catalog weapon may use the generic fallback — except 10mm variants, whose family icon IS the fallback."""
    from app.utils.weapon_naming import family_key

    fallback = "/static/weapon_images/10mm pistol FOS.png"
    for weapon in game_data_store.weapons:
        if weapon.image_url == fallback:
            assert family_key(weapon.name) == "10mm pistol", weapon.name


def test_rare_variant_resolves_to_family_icon() -> None:
    """A variant title resolves to its family icon (uniformity over stat cards)."""
    assert get_weapon_image_url("Hardened Gauss pistol") == "/static/weapon_images/Gauss Pistol FOS.png"
    assert get_weapon_image_url("hardened gauss PISTOL") == "/static/weapon_images/Gauss Pistol FOS.png"


def test_variant_without_a_card_shares_the_family_look() -> None:
    """Pipe/institute/junk variants with no wiki card use the family icon."""
    assert get_weapon_image_url("Auto pipe pistol") == "/static/weapon_images/Pipe Pistol FOS.png"
    assert get_weapon_image_url("Tactical Junk Jet") == "/static/weapon_images/Junk Jet FOS.png"


def test_new_family_variants_resolve() -> None:
    assert get_weapon_image_url("Rusty T60 pistol") == "/static/weapon_images/FOS T60 pistol.png"
    assert get_weapon_image_url("Surgical Ripper") == "/static/weapon_images/FOS Surgical Ripper.png"


def test_every_mapped_weapon_file_exists_on_disk() -> None:
    missing = [f for f in set(WEAPON_NAME_TO_IMAGE_FILE.values()) if not (WEAPON_IMAGE_DIR / f).exists()]
    assert missing == []


def test_every_legendary_dweller_has_a_portrait() -> None:
    """Every legendary.json dweller resolves to a real portrait, never the generic red fallback."""
    fallback = "/static/legendary_dweller_images/FOS_Dw_Legendary_Red.png"
    for dweller in game_data_store.dwellers:
        full = f"{dweller.first_name} {dweller.last_name or ''}".strip().casefold()
        if full not in LEGENDARY_DWELLER_IMAGE_FILES:
            continue
        url = get_legendary_dweller_image_url(full)
        assert url is not None, full
        assert url != fallback, full


def test_every_mapped_legendary_file_exists_on_disk() -> None:
    missing = [f for f in set(LEGENDARY_DWELLER_IMAGE_FILES.values()) if not (LEGENDARY_IMAGE_DIR / f).exists()]
    assert missing == []


def test_cx404_is_a_pet_not_a_dweller_portrait() -> None:
    """CX404 moved to pets; a dweller portrait for it is a miscategorized leftover."""
    assert "cx404" not in LEGENDARY_DWELLER_IMAGE_FILES
    assert not (LEGENDARY_IMAGE_DIR / "FOS_Dw_CX404.png").exists()
    assert (LEGENDARY_IMAGE_DIR.parent / "pet_images" / "FOS CX404.png").exists()


def test_legendary_aliases_resolve_to_the_same_portrait() -> None:
    """Catalog names that differ from the FOS character name share that character's portrait."""
    assert get_legendary_dweller_image_url("Colonel Autumn") == get_legendary_dweller_image_url("Augustus Autumn")
    assert get_legendary_dweller_image_url("Dr. Li") == get_legendary_dweller_image_url("Madison Li")
    assert get_legendary_dweller_image_url("Elder Lyons") == get_legendary_dweller_image_url("Owyn Lyons")


def test_quest_reward_dwellers_have_their_own_portraits() -> None:
    """TV-series quest rewards must not share the generic fallback (or anyone else's) portrait."""
    fallback = "/static/legendary_dweller_images/FOS_Dw_Legendary_Red.png"
    names = ["Lucy MacLean", "The Ghoul", "Maximus", "Ma June", "Snip Snip", "Snake Oil Salesman"]
    urls = [get_legendary_dweller_image_url(name) for name in names]
    assert all(url is not None and url != fallback for url in urls)
    assert len(set(urls)) == len(names)
