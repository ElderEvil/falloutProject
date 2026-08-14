from app.utils.legendary_dweller_assets import get_legendary_dweller_image_url
from app.utils.static_data import game_data_store
from app.utils.weapon_assets import get_weapon_image_url


def test_static_weapons_have_image_urls() -> None:
    assert all(weapon.image_url for weapon in game_data_store.weapons)
    assert get_weapon_image_url("Laser pistol") == "/static/weapon_images/Laser pistol FOS.png"


def test_legendary_dwellers_have_portrait_urls() -> None:
    legendary = [dweller for dweller in game_data_store.dwellers if dweller.rarity.lower() == "legendary"]
    assert legendary
    assert all(dweller.image_url for dweller in legendary)
    assert get_legendary_dweller_image_url("Abraham Washington")
