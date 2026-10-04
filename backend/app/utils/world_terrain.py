"""Terrain helpers shared by spatial movement and discovery placement.

Registry space is 0-100 with x east and y south; the world snapshot stores
terrain row-major as ``terrain[y * width + x]`` over the same orientation, so
registry coordinates map to tiles with no flip. The fog radii in
``frontend/src/modules/map/utils/fog.ts`` are counted in snapshot tiles; use
``reveal_radius_registry`` to translate them into registry space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol

    class TerrainSnapshot(Protocol):
        """The subset of a world snapshot these helpers read."""

        config: dict
        terrain: list[str]


#: Mirrors SITE_REVEAL in frontend/src/modules/map/utils/fog.ts.
SITE_REVEAL_TILES = 7
#: Mirrors TRAIL_REVEAL in frontend/src/modules/map/utils/fog.ts.
TRAIL_REVEAL_TILES = 4


def reveal_radius_registry(snapshot: TerrainSnapshot, tiles: int) -> float:
    """Registry-space distance equivalent to a fog reveal radius of *tiles*."""
    return tiles * (100.0 / snapshot.config["width"])


def _tile_index(snapshot: TerrainSnapshot, x: float, y: float) -> tuple[int, int]:
    width = snapshot.config["width"]
    height = snapshot.config["height"]
    return (
        min(width - 1, max(0, int(x / 100 * width))),
        min(height - 1, max(0, int(y / 100 * height))),
    )


def is_blocked(snapshot: TerrainSnapshot, x: float, y: float) -> bool:
    """True when a registry position is out of bounds or on water."""
    if not (0 <= x <= 100 and 0 <= y <= 100):
        return True
    width = snapshot.config["width"]
    tx, ty = _tile_index(snapshot, x, y)
    return snapshot.terrain[ty * width + tx] == "water"


def nearest_land(snapshot: TerrainSnapshot, x: float, y: float) -> tuple[float, float]:
    """Nearest non-water tile centre to a registry position (spiral search)."""
    width = snapshot.config["width"]
    height = snapshot.config["height"]
    tx, ty = _tile_index(snapshot, x, y)
    for radius in range(max(width, height)):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < width and 0 <= ny < height and snapshot.terrain[ny * width + nx] != "water":
                    return ((nx + 0.5) * 100 / width, (ny + 0.5) * 100 / height)
    return (x, y)
