"""Tests for the shared item-roll helper (loot_calculator.roll_item)."""

from app.schemas.exploration_event import JunkSchema, OutfitSchema, WeaponSchema
from app.services.exploration.loot_calculator import loot_calculator


def test_roll_item_dispatches_by_type():
    assert isinstance(loot_calculator.roll_item(5, "weapon"), WeaponSchema)
    assert isinstance(loot_calculator.roll_item(5, "outfit"), OutfitSchema)
    assert isinstance(loot_calculator.roll_item(5, "junk"), JunkSchema)


def test_roll_item_honors_rarity_floor():
    item = loot_calculator.roll_item(5, "junk", min_rarity="rare")
    assert item.rarity.lower() in ("rare", "legendary")
