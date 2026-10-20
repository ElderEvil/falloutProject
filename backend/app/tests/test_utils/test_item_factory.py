"""Factory <-> catalog equivalence: the shared constructors must not drop catalog fields.

The stat-less outfit bug came from rows bypassing the factory, but the factory itself is the
other half of the guarantee: if a catalog field stops being mapped, every item built from
then on silently loses it. These tests pin the mapping over the whole catalog, so a new
column cannot be forgotten in ``build_outfit`` / ``build_weapon`` without failing here.
"""

import pytest

from app.core.enums import JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.services.catalog_service import load_outfits, load_weapons
from app.utils.item_factory import build_junk, build_outfit, build_weapon

SPECIAL_KEYS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")

OUTFIT_CATALOG = load_outfits()
WEAPON_CATALOG = load_weapons()


@pytest.mark.parametrize("entry", OUTFIT_CATALOG, ids=[str(entry["name"]) for entry in OUTFIT_CATALOG])
def test_build_outfit_reproduces_catalog_fields(entry: dict) -> None:
    outfit = build_outfit(entry, entry["rarity"], None)

    assert outfit.name == entry["name"]
    assert outfit.rarity == RarityEnum(entry["rarity"])
    assert outfit.outfit_type == OutfitTypeEnum(str(entry["outfit_type"]).lower())
    assert outfit.value == entry.get("value")

    for key in SPECIAL_KEYS:
        assert getattr(outfit, key) == int(entry.get(key) or 0), key

    assert outfit.fire_resist == float(entry.get("fire_resist") or 0.0)
    declared_radiation = entry.get("radiation_resist")
    assert outfit.radiation_resist == (float(declared_radiation) if declared_radiation is not None else None)


@pytest.mark.parametrize("entry", WEAPON_CATALOG, ids=[str(entry["name"]) for entry in WEAPON_CATALOG])
def test_build_weapon_reproduces_catalog_fields(entry: dict) -> None:
    weapon = build_weapon(entry, entry["rarity"], None)

    assert weapon.name == entry["name"]
    assert weapon.rarity == RarityEnum(entry["rarity"])
    assert weapon.weapon_type == WeaponTypeEnum(str(entry["weapon_type"]).lower())
    assert weapon.weapon_subtype == WeaponSubtypeEnum(str(entry["weapon_subtype"]).lower())
    assert weapon.stat == entry["stat"]
    assert weapon.damage_min == int(entry["damage_min"])
    assert weapon.damage_max == int(entry["damage_max"])
    assert weapon.value == entry.get("value")


def test_factory_normalizes_a_raw_rarity_string() -> None:
    """A raw catalog rarity string must not survive as a plain str (it breaks on insert)."""
    outfit = build_outfit({"name": "Probe suit", "rarity": "Legendary", "outfit_type": "legendary_outfit"}, "Legendary")

    assert outfit.rarity is RarityEnum.LEGENDARY


def test_build_junk_defaults_to_valuables_without_art() -> None:
    """Bare junk keeps the exploration shape: valuables, no art, caller-owned value."""
    junk = build_junk("Bottle Cap", "Common", None, value=1, description="Found during wasteland exploration")

    assert (junk.junk_type, junk.value, junk.description, junk.image_url) == (
        JunkTypeEnum.VALUABLES,
        1,
        "Found during wasteland exploration",
        None,
    )


def test_build_junk_keeps_caller_type_value_prose_and_art() -> None:
    """The widened factory forwards every caller-owned junk field unchanged."""
    junk = build_junk(
        "Desk Fan",
        "Rare",
        None,
        value=42,
        description="A dusty desk fan",
        junk_type=JunkTypeEnum.CIRCUITRY,
        image_url="/static/junk_images/FOS Desk fan.png",
    )

    assert junk.junk_type is JunkTypeEnum.CIRCUITRY
    assert junk.value == 42
    assert junk.description == "A dusty desk fan"
    assert junk.image_url == "/static/junk_images/FOS Desk fan.png"
