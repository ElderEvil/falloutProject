"""Tests for the Strength-based exploration pack capacity helpers."""

import pytest

from app.utils.exploration_carry import carry_capacity, pack_slots, pack_slots_used


def test_carry_capacity_matches_the_strength_curve() -> None:
    assert carry_capacity(1) == 17
    assert carry_capacity(5) == 25
    assert carry_capacity(10) == 35


@pytest.mark.parametrize(("strength", "expected"), [(0, 17), (-3, 17), (99, 35)])
def test_carry_capacity_clamps_out_of_range_strength(strength: int, expected: int) -> None:
    assert carry_capacity(strength) == expected


def test_pouch_items_take_no_slot() -> None:
    assert pack_slots({"item_name": "Stimpak", "item_type": "stimpak"}) == 0
    assert pack_slots({"item_name": "RadAway", "item_type": "radaway"}) == 0


def test_equipped_entries_take_no_slot() -> None:
    assert pack_slots({"item_name": "Fire hydrant bat", "item_type": "weapon", "equipped": True}) == 0


def test_quantity_counts_one_slot_per_unit() -> None:
    assert pack_slots({"item_name": "Desk Fan", "quantity": 3}) == 3
    # A zero or missing quantity still occupies the one slot the entry itself needs.
    assert pack_slots({"item_name": "Desk Fan", "quantity": 0}) == 1
    assert pack_slots({"item_name": "Desk Fan"}) == 1


def test_empty_loot_uses_no_slots() -> None:
    assert pack_slots_used([]) == 0


def test_pack_slots_used_sums_only_carried_entries() -> None:
    loot = [
        {"item_name": "Desk Fan", "quantity": 2, "item_type": "junk"},
        {"item_name": "Stimpak", "item_type": "stimpak"},
        {"item_name": "Fire hydrant bat", "item_type": "weapon", "equipped": True},
        {"item_name": "Duct tape", "quantity": 3, "item_type": "junk"},
    ]
    assert pack_slots_used(loot) == 5
