"""Tests for the shared item-roll helper (loot_calculator.roll_item)."""

import pytest

from app.schemas.exploration_event import JunkSchema, OutfitSchema, WeaponSchema
from app.services import catalog_service
from app.services.exploration.loot_calculator import loot_calculator
from app.utils.exceptions import ValidationException


def _junk_type_by_name() -> dict[str, str]:
    return {item["name"]: str(item["junk_type"]).lower() for item in catalog_service.load_junk_items()}


def test_roll_item_dispatches_by_type():
    assert isinstance(loot_calculator.roll_item(5, "weapon"), WeaponSchema)
    assert isinstance(loot_calculator.roll_item(5, "outfit"), OutfitSchema)
    assert isinstance(loot_calculator.roll_item(5, "junk"), JunkSchema)


def test_roll_item_honors_rarity_floor():
    item = loot_calculator.roll_item(5, "junk", min_rarity="rare")
    assert item.rarity.lower() in ("rare", "legendary")


def test_junk_roll_honors_junk_types():
    junk_types = _junk_type_by_name()
    for _ in range(20):
        item = loot_calculator.roll_item(5, "junk", junk_types=["circuitry"])
        assert junk_types[item.name] == "circuitry"


def test_junk_rarity_floor_and_category_filter_combine():
    junk_types = _junk_type_by_name()
    item = loot_calculator.roll_item(5, "junk", "rare", junk_types=["science"])
    assert item.rarity.lower() in ("rare", "legendary")
    assert junk_types[item.name] == "science"


def test_weapon_roll_honors_weapon_types():
    for _ in range(20):
        item = loot_calculator.roll_item(5, "weapon", weapon_types=["energy"])
        assert item.weapon_type.lower() == "energy"


def test_filter_with_no_catalog_match_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An authoring mistake must fail loud, never silently return a wrong-family item."""
    monkeypatch.setattr(
        "app.services.catalog_service.load_junk_items",
        lambda: [{"name": "Yarn", "rarity": "Common", "value": 2, "junk_type": "Cloth"}],
    )
    with pytest.raises(ValidationException, match="No junk matching"):
        loot_calculator.roll_item(5, "junk", junk_types=["steel"])


def test_filtered_roll_with_an_empty_catalog_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A category filter must never fall back to a wrong-family item, even with no catalog at all."""
    monkeypatch.setattr("app.services.catalog_service.load_weapons", list)

    with pytest.raises(ValidationException, match="No weapon matching"):
        loot_calculator.roll_item(5, "weapon", weapon_types=["energy"])


def test_unfiltered_roll_keeps_the_empty_catalog_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """The legacy placeholder still serves an unconfigured install when no filter is requested."""
    monkeypatch.setattr("app.services.catalog_service.load_junk_items", list)

    assert loot_calculator.roll_item(5, "junk").name == "Bottle Cap"
