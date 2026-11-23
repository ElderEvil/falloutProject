import shutil
from pathlib import Path

import pytest

from app.utils import weapon_assets
from app.utils.legendary_dweller_assets import LEGENDARY_DWELLER_IMAGE_FILES, get_legendary_dweller_image_url
from app.utils.static_data import game_data_store
from app.utils.weapon_assets import WEAPON_NAME_TO_IMAGE_FILE, get_weapon_image_url
from app.utils.weapon_naming import family_key

STATIC = Path(__file__).parent.parent.parent / "static"
WEAPON_DIR = STATIC / "weapon_images"
LEGENDARY_DIR = STATIC / "legendary_dweller_images"
FALLBACK = "/static/legendary_dweller_images/FOS_Dw_Legendary_Red.png"
VARIANT_CASES = [
    ("Hardened Gauss pistol", "Gauss Pistol FOS.png"),
    ("hardened gauss PISTOL", "Gauss Pistol FOS.png"),
    ("Auto pipe pistol", "Pipe Pistol FOS.png"),
    ("Tactical Junk Jet", "Junk Jet FOS.png"),
    ("Rusty T60 pistol", "FOS T60 pistol.png"),
    ("Surgical Ripper", "FOS Surgical Ripper.png"),
]


@pytest.fixture
def isolated_weapon_art(tmp_path, monkeypatch):
    monkeypatch.setattr(weapon_assets, "_WEAPON_IMAGE_DIR", tmp_path / "weapon_images")
    weapon_assets._disk_index.cache_clear()
    yield weapon_assets._WEAPON_IMAGE_DIR
    weapon_assets._disk_index.cache_clear()


def test_weapon_filename_lookup_caches_directory_snapshots(isolated_weapon_art):
    isolated_weapon_art.mkdir()
    (isolated_weapon_art / "Prototype blaster FOS.png").touch()
    (isolated_weapon_art / "10mm pistol FOS.png").touch()
    assert get_weapon_image_url("PROTOTYPE BLASTER") == "/static/weapon_images/Prototype blaster FOS.png"
    (isolated_weapon_art / "Future blaster FOS.png").touch()
    assert get_weapon_image_url("Future blaster") == "/static/weapon_images/10mm pistol FOS.png"
    weapon_assets._disk_index.cache_clear()
    assert get_weapon_image_url("Future blaster") == "/static/weapon_images/Future blaster FOS.png"
    shutil.rmtree(isolated_weapon_art)
    weapon_assets._disk_index.cache_clear()
    assert get_weapon_image_url("Prototype blaster") is None
    isolated_weapon_art.mkdir()
    (isolated_weapon_art / "Prototype blaster FOS.png").touch()
    assert get_weapon_image_url("Prototype blaster") is None
    weapon_assets._disk_index.cache_clear()
    assert get_weapon_image_url("Prototype blaster") == "/static/weapon_images/Prototype blaster FOS.png"


def test_static_weapons_have_image_urls() -> None:
    assert all(weapon.image_url for weapon in game_data_store.weapons)
    assert get_weapon_image_url("Laser pistol") == "/static/weapon_images/Laser pistol FOS.png"
    fallback = "/static/weapon_images/10mm pistol FOS.png"
    for weapon in game_data_store.weapons:
        if weapon.image_url == fallback:
            assert family_key(weapon.name) == "10mm pistol", weapon.name
    for mapping, directory in [(WEAPON_NAME_TO_IMAGE_FILE, WEAPON_DIR), (LEGENDARY_DWELLER_IMAGE_FILES, LEGENDARY_DIR)]:
        assert [f for f in set(mapping.values()) if not (directory / f).exists()] == []


def test_variants_resolve_to_family_icons() -> None:
    for name, filename in VARIANT_CASES:
        assert get_weapon_image_url(name) == f"/static/weapon_images/{filename}"


def test_legendary_portraits_are_complete_and_distinct() -> None:
    for dweller in game_data_store.dwellers:
        full = f"{dweller.first_name} {dweller.last_name or ''}".strip().casefold()
        if full in LEGENDARY_DWELLER_IMAGE_FILES:
            url = get_legendary_dweller_image_url(full)
            assert url is not None, full
            assert url != FALLBACK, full
    names = ["Lucy MacLean", "The Ghoul", "Maximus", "Ma June", "Snip Snip", "Snake Oil Salesman"]
    urls = [get_legendary_dweller_image_url(name) for name in names]
    assert all(url is not None and url != FALLBACK for url in urls)
    assert len(set(urls)) == len(names)
    for alias, canonical in [("Colonel Autumn", "Augustus Autumn"), ("Dr. Li", "Madison Li")]:
        assert get_legendary_dweller_image_url(alias) == get_legendary_dweller_image_url(canonical)
    assert get_legendary_dweller_image_url("Elder Lyons") == get_legendary_dweller_image_url("Owyn Lyons")
    assert "cx404" not in LEGENDARY_DWELLER_IMAGE_FILES
    assert not (LEGENDARY_DIR / "FOS_Dw_CX404.png").exists()
    assert (LEGENDARY_DIR.parent / "pet_images" / "FOS CX404.png").exists()
