"""Terrain helpers shared by spatial movement and discovery placement.

Registry space is 0-100 with x east and y south; the world snapshot stores
terrain row-major as ``terrain[y * width + x]`` over the same orientation, so
registry coordinates map to tiles with no flip. The fog radii in
``frontend/src/modules/map/utils/fog.ts`` are counted in snapshot tiles; use
``reveal_radius_registry`` to translate them into registry space.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol

    class TerrainSnapshot(Protocol):
        """The subset of a world snapshot these helpers read."""

        config: dict
        terrain: list[str]


#: Mirrors SITE_REVEAL in frontend/src/modules/map/utils/fog.ts.
SITE_REVEAL_TILES = 7

#: Registry-space distance within which a dispatch counts as arrived.
ARRIVAL_RADIUS = 2.0


def segment_passes_near(
    start: tuple[float, float], end: tuple[float, float], point: tuple[float, float], radius: float
) -> bool:
    """True when a point lies within *radius* of the segment, endpoints included.

    Catches arrivals that a single endpoint check would leapfrog over long
    offline catch-ups.
    """
    segment_dx, segment_dy = end[0] - start[0], end[1] - start[1]
    length_sq = segment_dx * segment_dx + segment_dy * segment_dy
    if length_sq == 0:
        closest = start
    else:
        t = ((point[0] - start[0]) * segment_dx + (point[1] - start[1]) * segment_dy) / length_sq
        t = min(1.0, max(0.0, t))
        closest = (start[0] + segment_dx * t, start[1] + segment_dy * t)
    return (point[0] - closest[0]) ** 2 + (point[1] - closest[1]) ** 2 <= radius * radius


def path_passes_near(points: list[tuple[float, float]], target: tuple[float, float], radius: float) -> bool:
    """True when a target lies within *radius* of a traveled path or its endpoints."""
    if not points:
        return False
    if len(points) == 1:
        px, py = points[0]
        return (target[0] - px) ** 2 + (target[1] - py) ** 2 <= radius * radius
    return any(segment_passes_near(points[i - 1], points[i], target, radius) for i in range(1, len(points)))


def heading_to(origin: tuple[float, float], target: tuple[float, float]) -> float:
    """Compass heading from origin toward target (0=N, 90=E), matching the map bearing math."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return 0.0
    return round((math.degrees(math.atan2(dx, -dy)) + 360) % 360, 2)


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
