"""Pack capacity rules for a dweller exploring the wasteland.

A pack holds a finite number of slots that grows with Strength. Medical supplies live in the
pouch and worn gear is carried on the body, so neither consumes a slot.
"""

from collections.abc import Sequence

CARRY_BASE_SLOTS = 15
CARRY_SLOTS_PER_STRENGTH = 2

# Medical supplies live in the pouch, not the pack.
POUCH_ITEM_TYPES = frozenset({"stimpak", "radaway"})

# Real SPECIAL values are 1..10; clamp so a hand-edited row cannot produce a negative capacity.
_MIN_STRENGTH = 1
_MAX_STRENGTH = 10


def carry_capacity(strength: int) -> int:
    """Slots the pack holds at this Strength."""
    clamped = min(max(int(strength), _MIN_STRENGTH), _MAX_STRENGTH)
    return CARRY_BASE_SLOTS + CARRY_SLOTS_PER_STRENGTH * clamped


def pack_slots(entry: dict) -> int:
    """Slots one loot entry occupies; pouch items and worn gear take none."""
    if entry.get("equipped") or entry.get("item_type") in POUCH_ITEM_TYPES:
        return 0
    return max(1, int(entry.get("quantity", 1)))


def pack_slots_used(loot: Sequence[dict]) -> int:
    """Slots taken by everything currently carried."""
    return sum(pack_slots(entry) for entry in loot)
