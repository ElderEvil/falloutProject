"""Vault slot placement: how a persisted slot maps to shared-atlas coordinates.

The atlas is one shared slot grid (see ``game_config.vault_slots``); each vault
occupies one unique slot and is discoverable by every player. Slot order is
scattered, not row-major, so vaults look randomly placed while staying stable and
non-overlapping. Coordinates are registry space (0-100).
"""

from functools import cache
from random import Random

from app.core.game_config import game_config
from app.utils.world_terrain import tile_from_registry


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


def slot_tile_indices(width: int, height: int, *, margin: int = 0) -> set[int]:
    """Tile indices covered by every shared vault slot, plus a Chebyshev dry *margin*.

    Used to keep generation from carving water onto a persisted player vault.
    """
    slots = game_config.vault_slots
    tiles: set[int] = set()
    for slot_index in range(slots.count):
        tile_x, tile_y = tile_from_registry(width, height, *slot_coords(slot_index))
        for dy in range(-margin, margin + 1):
            for dx in range(-margin, margin + 1):
                nx, ny = tile_x + dx, tile_y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    tiles.add(ny * width + nx)
    return tiles
