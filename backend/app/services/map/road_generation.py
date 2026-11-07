"""Deterministic background roads on an existing world, independent of travel/occupancy.

Bump ROAD_VERSION when the recipe or geometry changes. Never bump the base world's
version for roads: it participates in terrain/slot seeds. All geometry is validated
here; the browser draws the persisted centerlines without smoothing them again.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
from collections import Counter
from collections.abc import Callable
from functools import cache
from itertools import pairwise, starmap
from random import Random
from typing import Literal, cast

from app.schemas.world_snapshot import WorldRoadRead, WorldRoadsRead
from app.services.map.world_generation import TRAVEL_COST, TerrainType, _largest_traversable_component

ROAD_VERSION = 4
MAX_ACCESS_LENGTH = 2.0  # Registry units (1.6 cells on the default 80 x 80 world).
# Country stroke in registry space (0.68 SVG / 1.6): a shorter spur grafts as a round-cap dot.
MIN_ACCESS_LENGTH = 0.425
# Largest casing is 1.36 SVG units: radius in registry space = 1.36 / 1.6 / 2.
# Extra clearance absorbs serialization rounding. Country roads use the same safe corridor.
ROAD_RADIUS = 0.426
Point = tuple[float, float]
RoadKind = Literal["highway", "country", "railroad"]
Clear = Callable[[Point, Point], bool]


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mix(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _intersects(a: Point, b: Point, left: float, top: float, right: float, bottom: float) -> bool:
    """Segment/rectangle slab test; expanded water rectangles conservatively cover casing."""
    lo, hi = 0.0, 1.0
    for start, end, lower, upper in ((a[0], b[0], left, right), (a[1], b[1], top, bottom)):
        delta = end - start
        if delta == 0:
            if start < lower or start > upper:
                return False
            continue
        enter, leave = sorted(((lower - start) / delta, (upper - start) / delta))
        lo, hi = max(lo, enter), min(hi, leave)
        if lo > hi:
            return False
    return True


def road_segment_clear(terrain: list[str], width: int, height: int, a: Point, b: Point) -> bool:
    """Check the entire segment and highway casing, not just sampled center points."""
    radius = ROAD_RADIUS
    if any(not radius <= value <= 100 - radius for value in (*a, *b)):
        return False
    sx, sy = 100 / width, 100 / height
    for y in range(max(0, int((min(a[1], b[1]) - radius) / sy)), min(height, int((max(a[1], b[1]) + radius) / sy) + 1)):
        for x in range(
            max(0, int((min(a[0], b[0]) - radius) / sx)), min(width, int((max(a[0], b[0]) + radius) / sx) + 1)
        ):
            if terrain[y * width + x] == "water" and _intersects(
                a, b, x * sx - radius, y * sy - radius, (x + 1) * sx + radius, (y + 1) * sy + radius
            ):
                return False
    return True


def _route(start: int, goal: int, land: set[int], terrain: list[str], width: int) -> list[int]:
    """Eight-neighbor A*, stable ties, no diagonal corner cutting."""

    def distance(a: int, b: int) -> float:
        return math.hypot(a % width - b % width, a // width - b // width)

    queue = [(distance(start, goal), 0.0, start)]
    costs = {start: 0.0}
    parents: dict[int, int] = {}
    while queue:
        _, cost, cell = heapq.heappop(queue)
        if cost != costs[cell]:
            continue
        if cell == goal:
            path = [cell]
            while cell in parents:
                cell = parents[cell]
                path.append(cell)
            return path[::-1]
        x, y = cell % width, cell // width
        for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            nx, ny = x + dx, y + dy
            neighbor = ny * width + nx
            if not 0 <= nx < width or ny < 0 or neighbor not in land:
                continue
            if dx and dy and (y * width + nx not in land or ny * width + x not in land):
                continue
            next_cost = cost + math.hypot(dx, dy) * TRAVEL_COST[cast("TerrainType", terrain[neighbor])]
            if next_cost < costs.get(neighbor, math.inf):
                costs[neighbor] = next_cost
                parents[neighbor] = cell
                heapq.heappush(queue, (next_cost + distance(neighbor, goal), next_cost, neighbor))
    return []


def _rail_geometry(points: list[Point], locked: set[Point], clear: Clear) -> list[Point]:
    """Long surveyed tangents, with short 10-15 degree transition steps at bends."""
    tangents = [points[0]]
    i = 0
    while i < len(points) - 1:
        end = next((j for j in range(i + 1, len(points)) if points[j] in locked), len(points) - 1)
        while end > i + 1 and not clear(points[i], points[end]):
            end -= 1
        tangents.append(points[end])
        i = end
    result = [tangents[0]]
    for a, b, c in zip(tangents, tangents[1:], tangents[2:], strict=False):
        ab, bc = _distance(a, b), _distance(b, c)
        cosine = ((b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])) / (ab * bc)
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        if angle <= 15 or b in locked:
            result.append(b)
            continue
        cut = min(4.0, ab / 4, bc / 4)
        entry, leave = _mix(b, a, cut / ab), _mix(b, c, cut / bc)
        steps = max(2, math.ceil(angle / 10))
        curve = [_mix(_mix(entry, b, j / steps), _mix(b, leave, j / steps), j / steps) for j in range(steps + 1)]
        result.extend(curve if all(starmap(clear, pairwise(curve))) else [b])
    result.append(tangents[-1])
    return [(round(x, 4), round(y, 4)) for x, y in result]


def _geometry(points: list[Point], locked: set[Point], clear: Clear, rng: Random, kind: RoadKind) -> list[Point]:
    """Bend the route itself, then interpolate land-safe curves through exact junctions."""
    if kind == "railroad":
        return _rail_geometry(points, locked, clear)
    simplified = [points[0]]
    i = 0
    while i < len(points) - 1:
        end = min(i + 12, len(points) - 1)
        for j in range(i + 1, end):
            if points[j] in locked:
                end = j
                break
        while end > i + 1 and not clear(points[i], points[end]):
            end -= 1
        simplified.append(points[end])
        i = end

    # Give even a formerly straight corridor interior control points. A slow
    # lateral wave produces broad bends, not independent noisy tile offsets.
    anchors = [simplified[0]]
    for a, b in pairwise(simplified):
        if _distance(a, b) > 5:
            anchors.append(_mix(a, b, 0.5))
        anchors.append(b)
    phase = rng.uniform(0, math.tau)
    wavelength = rng.uniform(15, 24) if kind == "country" else rng.uniform(28, 40)
    amplitude = {"highway": 2.2, "country": 4.0, "railroad": 1.2}[kind]
    controls = anchors.copy()
    traveled = 0.0
    for i in range(1, len(anchors) - 1):
        a, b, c = anchors[i - 1 : i + 2]
        traveled += _distance(a, b)
        if b in locked:
            continue
        span = _distance(a, c)
        if span == 0:
            continue
        offset = min(amplitude, min(_distance(a, b), _distance(b, c)) * 0.65)
        offset *= math.sin(phase + traveled * math.tau / wavelength)
        for scale in (1.0, 0.5, 0.25):
            shifted = (b[0] - (c[1] - a[1]) / span * offset * scale, b[1] + (c[0] - a[0]) / span * offset * scale)
            if clear(controls[i - 1], shifted) and clear(shifted, c):
                controls[i] = shifted
                break

    curved = [controls[0]]
    for i, (a, b) in enumerate(pairwise(controls)):
        before, after = controls[max(0, i - 1)], controls[min(len(controls) - 1, i + 2)]
        steps = max(4, math.ceil(_distance(a, b) / 0.25))
        # Reduce tangent length beside water. At zero this is the already checked
        # straight span; no unconstrained browser smoothing can undo clearance.
        for tension in (1 / 6, 1 / 12, 0):
            c1 = (a[0] + (b[0] - before[0]) * tension, a[1] + (b[1] - before[1]) * tension)
            c2 = (b[0] - (after[0] - a[0]) * tension, b[1] - (after[1] - a[1]) * tension)
            curve = []
            for j in range(steps + 1):
                t = j / steps
                curve.append(
                    _mix(_mix(_mix(a, c1, t), _mix(c1, c2, t), t), _mix(_mix(c1, c2, t), _mix(c2, b, t), t), t)
                )
            if all(starmap(clear, pairwise(curve))):
                curved.extend(curve[1:])
                break
        else:
            raise ValueError("Curved road leaves its land corridor")
    return [(round(x, 4), round(y, 4)) for x, y in curved]


def generate_roads(*, terrain: list[str], width: int, height: int, seed: str, base_checksum: str) -> WorldRoadsRead:
    """Generate a bounded network from stored terrain; never regenerate that terrain."""
    if width < 1 or height < 1 or len(terrain) != width * height or any(t not in TRAVEL_COST for t in terrain):
        raise ValueError("Invalid road terrain grid")

    @cache
    def center(cell: int) -> Point:
        return ((cell % width + 0.5) * 100 / width, (cell // width + 0.5) * 100 / height)

    def clear(a: Point, b: Point) -> bool:
        return road_segment_clear(terrain, width, height, a, b)

    land = _largest_traversable_component(cast("list[TerrainType]", terrain), width, height)
    land = {cell for cell in land if clear(center(cell), center(cell))}
    rng = Random(hashlib.blake2b(f"roads:2:{seed}".encode(), digest_size=16).digest())
    candidates = sorted(land)
    rng.shuffle(candidates)
    branch_candidates = [cell for cell in candidates if all(3 <= v <= 97 for v in center(cell))]
    # Interior hubs avoid a perimeter ring. Prefer ruins, but keep the network regional.
    interior = [cell for cell in candidates if all(8 <= v <= 92 for v in center(cell))]
    candidates = interior or candidates
    hubs: list[int] = []
    if candidates:
        hubs.append(min(candidates, key=lambda c: _distance(center(c), (50, 50)) + (0 if terrain[c] == "ruins" else 8)))
    while len(hubs) < 10:
        remaining = [c for c in candidates if all(_distance(center(c), center(h)) >= 18 for h in hubs)]
        if not remaining:
            break
        hubs.append(
            max(
                remaining,
                key=lambda c: (
                    min(_distance(center(c), center(h)) for h in hubs) * (1.15 if terrain[c] == "ruins" else 1)
                ),
            )
        )

    raw: list[tuple[RoadKind, list[int]]] = []
    network: set[int] = set(hubs[:1])
    connected = hubs[:1]
    pending = hubs[1:]
    while pending:
        start, goal = min(
            ((a, b) for a in pending for b in connected), key=lambda pair: _distance(center(pair[0]), center(pair[1]))
        )
        path = _route(start, goal, land, terrain, width)
        if not path:
            raise ValueError("Required road hubs are disconnected")
        # Stop at the first existing road: no redundant parallel/overlapping tail.
        join = next(i for i, cell in enumerate(path) if cell in network)
        path = path[: join + 1]
        raw.append(("highway", path))
        network.update(path)
        connected.append(start)
        pending.remove(start)

    # A few local loops when genuinely new corridors exist. Trim shared tails
    # so it joins the backbone without painting duplicate roads over it.
    loops = 0
    pairs = [(a, b) for i, a in enumerate(hubs) for b in hubs[i + 1 :]]
    for start, goal in sorted(pairs, key=lambda pair: _distance(center(pair[0]), center(pair[1]))):
        path = _route(start, goal, land, terrain, width)
        fresh = [i for i, cell in enumerate(path) if cell not in network]
        if len(fresh) < max(8, len(path) * 0.65):
            continue
        path = path[fresh[0] - 1 : fresh[-1] + 2]
        if any(cell in network for cell in path[1:-1]):
            continue
        raw.append(("country", path))
        network.update(path)
        loops += 1
        if loops == 4:
            break

    # Local branches attach to exact existing vertices. A few later branches can
    # join earlier ones, but a location being occupied never influences this list.
    distances = {c: min((_distance(center(c), center(n)) for n in network), default=0) for c in branch_candidates}
    branches: list[int] = []
    for _ in range(70):
        options = [c for c in branch_candidates if all(_distance(center(c), center(b)) >= 5.5 for b in hubs + branches)]
        if not options or not network:
            break
        start = max(
            options,
            key=lambda c: distances[c] * (1.2 if terrain[c] == "ruins" else 1),
        )
        goal = min(sorted(network), key=lambda c: _distance(center(c), center(start)))
        branches.append(start)
        if _distance(center(start), center(goal)) < 3:
            continue
        path = _route(start, goal, land, terrain, width)
        if not path:
            continue
        join = next(i for i, cell in enumerate(path) if cell in network)
        path = path[: join + 1]
        raw.append(("country", path))
        fresh = set(path) - network
        for c in branch_candidates:
            distances[c] = min(
                distances[c], min((_distance(center(c), center(n)) for n in fresh), default=distances[c])
            )
        network.update(path)

    # A sparse rail trunk and feeder, independent of the road network. Crossings
    # are background cartography, not stations, overpasses, or new travel rules.
    rail_rng = Random(hashlib.blake2b(f"rails:2:{seed}".encode(), digest_size=16).digest())
    if len(candidates) > 1:
        start = min(candidates, key=lambda c: sum(center(c)))
        end = max(candidates, key=lambda c: sum(center(c)))
        trunk = _route(start, end, land, terrain, width)
        if len(trunk) > 1:
            raw.append(("railroad", trunk))
            start = max(candidates, key=lambda c: center(c)[0] - center(c)[1])
            goal = min(trunk, key=lambda c: _distance(center(c), center(start)))
            feeder = _route(start, goal, land, terrain, width)
            if len(feeder) > 1:
                rail_cells = set(trunk)
                join = next(i for i, cell in enumerate(feeder) if cell in rail_cells)
                if join:
                    raw.append(("railroad", feeder[: join + 1]))

    # Road and rail junctions stay exact within their own network. Crossing a road
    # must not force a railway to adopt that road's curve (or vice versa).
    counts = Counter((kind == "railroad", cell) for kind, path in raw for cell in path)
    locks = {
        rail: {center(cell) for (is_rail, cell), count in counts.items() if count > 1 and is_rail == rail}
        for rail in (False, True)
    }
    segments: list[WorldRoadRead] = []
    for i, (kind, path) in enumerate(raw):
        if len(path) < 2:
            continue
        points = _geometry(
            [center(c) for c in path], locks[kind == "railroad"], clear, rail_rng if kind == "railroad" else rng, kind
        )
        if not all(starmap(clear, pairwise(points))):
            raise ValueError("Road geometry leaves its land corridor")
        segments.append(WorldRoadRead(id=f"road-{i}", kind=kind, points=points))
    payload = {
        "version": ROAD_VERSION,
        "base_checksum": base_checksum,
        "segments": [s.model_dump(mode="json", exclude_none=True) for s in segments],
    }
    checksum = hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), digest_size=16
    ).hexdigest()
    return WorldRoadsRead(version=ROAD_VERSION, base_checksum=base_checksum, checksum=checksum, segments=segments)


def place_on_road(origin: Point, vertices: set[Point]) -> bool:
    """True when the coordinate already stands on a road vertex closer than a visible driveway."""
    return any(_distance(origin, point) <= MIN_ACCESS_LENGTH for point in vertices)


def place_access_road(
    *,
    terrain: list[str],
    width: int,
    height: int,
    origin: Point,
    land: set[int],
    vertices: set[Point],
    location_id: str,
) -> WorldRoadRead | None:
    """Join an exact public registry coordinate to a persisted road vertex on land."""
    from uuid import UUID

    def clear(a: Point, b: Point) -> bool:
        return road_segment_clear(terrain, width, height, a, b)

    def tile(p: Point) -> int:
        return min(height - 1, int(p[1] * height / 100)) * width + min(width - 1, int(p[0] * width / 100))

    def center(cell: int) -> Point:
        return ((cell % width + 0.5) * 100 / width, (cell // width + 0.5) * 100 / height)

    if place_on_road(origin, vertices):
        return None
    if not clear(origin, origin):
        return None
    start = tile(origin)
    if start not in land or not clear(origin, center(start)):
        return None
    targets = sorted(
        (p for p in vertices if _distance(origin, p) <= MAX_ACCESS_LENGTH), key=lambda p: (_distance(origin, p), p)
    )
    goal = next((p for p in targets if tile(p) in land and clear(center(tile(p)), p)), None)
    if goal is None:
        return None
    path = _route(start, tile(goal), land, terrain, width)
    if not path:
        return None
    points = [origin]
    for point in [*(center(c) for c in path), goal]:
        if point != points[-1]:
            points.append(point)
    if len(points) == 1:
        points.append(goal)
    if not all(starmap(clear, pairwise(points))):
        return None
    # Short driveways need direct tangents and restrained bends, without the
    # decorative meanders used on long country roads. Reuse the rail simplifier.
    points = _rail_geometry(points, set(), clear)
    if sum(starmap(_distance, pairwise(points))) > MAX_ACCESS_LENGTH:
        return None
    if not all(starmap(clear, pairwise(points))):
        return None
    return WorldRoadRead(id=f"access-{location_id}", location_id=UUID(location_id), kind="country", points=points)
