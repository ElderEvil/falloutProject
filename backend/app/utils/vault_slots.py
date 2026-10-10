"""Vault slot placement: how a persisted slot maps to shared-atlas coordinates.

The atlas is one shared slot grid (see ``game_config.vault_slots``); each vault
occupies one unique slot and is discoverable by every player. Slot order is
scattered, not row-major, so vaults look randomly placed while staying stable and
non-overlapping. Coordinates are registry space (0-100).
"""

from functools import cache
from random import Random

from app.core.game_config import game_config


@cache
def _slot_permutation(count: int) -> tuple[int, ...]:
    """Seeded scatter of cell indices: stable, collision-free, and random-looking."""
    order = list(range(count))
    Random(0x5EED).shuffle(order)
    return tuple(order)


def _jitter(slot_index: int) -> tuple[float, float]:
    """Deterministic within-cell offset so vaults do not sit on a perfect grid."""
    h = (slot_index * 2654435761) & 0xFFFFFFFF
    return (((h & 0xFFFF) / 0xFFFF) - 0.5) * 0.6, (((h >> 16) & 0xFFFF) / 0xFFFF - 0.5) * 0.6


def slot_coords(slot_index: int) -> tuple[float, float]:
    """Registry coordinates (0-100) for a slot's scattered, jittered cell."""
    slots = game_config.vault_slots
    cell = 100 / slots.columns
    index = _slot_permutation(slots.count)[slot_index % slots.count]
    jx, jy = _jitter(slot_index)
    return ((index % slots.columns + 0.5 + jx) * cell, (index // slots.columns + 0.5 + jy) * cell)
