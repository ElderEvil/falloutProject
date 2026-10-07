"""Backend-owned world generation core (pure, deterministic, framework-free).

This is the Python replacement for frontend-owned geography: a small generator that
produces terrain and land-safe vault slots from an explicit recipe. It does **not**
attempt TypeScript parity — reproducibility is defined by this implementation.
``GENERATOR_VERSION`` versions the snapshot payload (identity/fingerprint); geography
is seeded from ``SEED_EPOCH``, so a payload-only bump (new snapshot fields, display
masks) never re-rolls the world. Bump ``SEED_EPOCH`` only for intentional geography
changes. Existing rows persist by ``(world_id, generator_version)`` and stay readable.

Design rules (see docs/features/WORLD_GENERATION_CONTRACT.md):
- Deterministic hashing (blake2b), never Python's process-dependent ``hash()``.
- One seeded PRNG per named stream, stable call order, so adding a stream never
  shifts another.
- Terrain and slots derive only from seed + config + SEED_EPOCH — never on vault
-   occupancy or discoveries. Public anchors participate in the recipe
-   fingerprint (recipe versioning), not in shaping geography: slots are
-   placement markers on the fixed world, never terrain shapers.
- Generation is a pure function: same recipe -> identical output.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
from dataclasses import asdict, dataclass, field
from random import Random
from typing import Literal

# ── Contract constants ──────────────────────────────────────────────────

# Snapshot payload/identity version. Bump for payload changes (e.g. new masks); it
# feeds the recipe fingerprint but not the RNG, so it never re-rolls the world.
GENERATOR_VERSION = 2
# Geography seed epoch. Bump only for intentional terrain/slot re-rolls.
SEED_EPOCH = 1
WORLD_ID = "wasteland-atlas"

TerrainType = Literal["wasteland", "forest", "ruins", "hills", "water"]

TERRAIN_KINDS: tuple[TerrainType, ...] = ("wasteland", "forest", "ruins", "hills", "water")

# Traversability cost per terrain; water is impassable. Kept here so validation and
# reachability share one table with the snapshot.
TRAVEL_COST: dict[TerrainType, float] = {
    "wasteland": 1.0,
    "forest": 1.15,
    "ruins": 1.3,
    "hills": 1.5,
    "water": math.inf,
}

# ── Rivers ──────────────────────────────────────────────────────────────
# Ported from the retired frontend atlas generator; output is Python-authoritative.
RIVER_COUNT = 1
RIVER_WIDTH = 3  # odd width: a carve stamps a 3x3 square per step
RIVER_WANDER_STEPS = 60
RIVER_MAX_STEPS = 160
RIVER_JITTER = 0.6  # ±0.3 rad of meander per step
WATER_MIN_COMPONENT = 20  # river-mask components below this are speckle → dropped
# Chebyshev dry margin kept around every shared vault slot so a river mask can
# never paint over a persisted vault disc.
VAULT_SLOT_DRY_MARGIN = 1

_RIVER_EDGES = ("top", "bottom", "left", "right")
_RIVER_ADJACENT_EDGES: dict[str, tuple[str, str]] = {
    "top": ("left", "right"),
    "bottom": ("left", "right"),
    "left": ("top", "bottom"),
    "right": ("top", "bottom"),
}

# ── Roads (display-only mask; never gameplay authority) ─────────────────
ROAD_JUNCTION_COUNT = 12
ROAD_JUNCTION_MIN_SPACING = 8
LINE_SAMPLE_STEP = 4  # tiles between samples for MST edge weights
WATER_SAMPLE_COST = 250.0  # spanning water is costly — the MST crosses minimally
# Internal routing cost. Water is impassable so roads must detour, never bridge.
ROAD_COST: dict[TerrainType, float] = {
    "wasteland": 0.7,
    "forest": 0.8,
    "ruins": 0.9,
    "hills": 1.1,
    "water": math.inf,
}

_ROAD_MIN_COST = min(cost for cost in ROAD_COST.values() if cost != math.inf)
_ORTHO: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True)
class WorldConfig:
    """Complete generation configuration; part of the recipe fingerprint."""

    width: int = 80
    height: int = 80
    location_count: int = 100
    slot_count: int = 100
    slot_columns: int = 10
    slot_min_spacing: int = 4
    noise_octaves: int = 4
    noise_frequency: float = 0.03
    noise_lacunarity: float = 2.0
    noise_gain: float = 0.5
    water_quantile: float = 0.02
    hills_quantile: float = 0.17
    forest_quantile: float = 0.10


@dataclass(frozen=True)
class PublicAnchor:
    """A fixed public anchor baked into the recipe (stable id + registry coords)."""

    id: str
    coord_x: float
    coord_y: float


@dataclass
class WorldRecipe:
    """The full recipe: seed, config, version, public anchors."""

    seed: str
    config: WorldConfig = field(default_factory=WorldConfig)
    anchors: tuple[PublicAnchor, ...] = ()
    generator_version: int = GENERATOR_VERSION
    world_id: str = WORLD_ID

    def fingerprint(self) -> str:
        """Stable recipe fingerprint (hex); anchors are part of the hash."""
        return _hash(
            self.world_id,
            str(self.generator_version),
            self.seed,
            self._config_tuple(),
            ";".join(f"{a.id}:{a.coord_x:.6f}:{a.coord_y:.6f}" for a in self.anchors),
        )

    def _config_tuple(self) -> str:
        c = self.config
        return (
            f"{c.width}x{c.height}:{c.location_count}:{c.slot_count}:{c.slot_columns}:"
            f"{c.slot_min_spacing}:{c.noise_octaves}:{c.noise_frequency}:{c.noise_lacunarity}:"
            f"{c.noise_gain}:{c.water_quantile}:{c.hills_quantile}:{c.forest_quantile}"
        )


@dataclass
class GeneratedSlot:
    """One land-safe slot: stable index + registry coordinate + its tile."""

    slot_index: int
    tile_x: int
    tile_y: int
    coord_x: float
    coord_y: float


@dataclass
class GeneratedWorld:
    """The generated snapshot (terrain + slots + display-only roads and rivers + fingerprint)."""

    recipe_fingerprint: str
    generator_version: int
    width: int
    height: int
    terrain: list[TerrainType]
    slots: list[GeneratedSlot]
    roads: list[int] = field(default_factory=list)
    rivers: list[int] = field(default_factory=list)


# ── Deterministic primitives ────────────────────────────────────────────


def _hash(*parts: str) -> str:
    """Stable hash of joined parts; never Python hash() (process-dependent)."""
    digest = hashlib.blake2b("\x1f".join(parts).encode("utf-8"), digest_size=16)
    return digest.hexdigest()


def _stream(recipe: WorldRecipe, namespace: str) -> Random:
    """Independent seeded PRNG per named stream, stable across recipe versions."""
    seed_bytes = _hash(str(SEED_EPOCH), recipe.seed, namespace)
    return Random(int(seed_bytes, 16))


# ── Noise (value noise + fBm) ───────────────────────────────────────────


def _value_noise_field(
    width: int, height: int, rng: Random, octaves: int, frequency: float, lacunarity: float, gain: float
) -> list[float]:
    """Normalized fBm over a seeded lattice, min/max-normalized to [0, 1]."""
    field = [0.0] * (width * height)
    amplitude = 1.0
    total_amplitude = 0.0
    freq = frequency
    for _ in range(octaves):
        grid = freq
        # A deterministic lattice per octave from this stream.
        lattice_w = max(2, int(grid * width) + 2)
        lattice_h = max(2, int(grid * height) + 2)
        lattice = [rng.random() for _ in range(lattice_w * lattice_h)]
        for y in range(height):
            fy = y * grid
            y0 = int(fy)
            ty = fy - y0
            sy = ty * ty * (3 - 2 * ty)
            for x in range(width):
                fx = x * grid
                x0 = int(fx)
                tx = fx - x0
                sx = tx * tx * (3 - 2 * tx)
                i00 = min(lattice_h - 1, y0) * lattice_w + min(lattice_w - 1, x0)
                i10 = min(lattice_h - 1, y0) * lattice_w + min(lattice_w - 1, x0 + 1)
                i01 = min(lattice_h - 1, y0 + 1) * lattice_w + min(lattice_w - 1, x0)
                i11 = min(lattice_h - 1, y0 + 1) * lattice_w + min(lattice_w - 1, x0 + 1)
                top = lattice[i00] * (1 - sx) + lattice[i10] * sx
                bottom = lattice[i01] * (1 - sx) + lattice[i11] * sx
                field[y * width + x] += amplitude * (top * (1 - sy) + bottom * sy)
        total_amplitude += amplitude
        amplitude *= gain
        freq *= lacunarity
    for i in range(len(field)):
        field[i] /= total_amplitude
    lo = min(field)
    hi = max(field)
    span = (hi - lo) or 1.0
    return [(v - lo) / span for v in field]


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(q * len(ordered))))
    return ordered[idx]


# ── Terrain ─────────────────────────────────────────────────────────────


def generate_terrain(recipe: WorldRecipe) -> list[TerrainType]:
    """Classify terrain from two independent fBm fields (base + ruins)."""
    cfg = recipe.config
    n = cfg.width * cfg.height
    base = _value_noise_field(
        cfg.width,
        cfg.height,
        _stream(recipe, "terrain:base"),
        cfg.noise_octaves,
        cfg.noise_frequency,
        cfg.noise_lacunarity,
        cfg.noise_gain,
    )
    ruins = _value_noise_field(
        cfg.width,
        cfg.height,
        _stream(recipe, "terrain:ruins"),
        cfg.noise_octaves,
        cfg.noise_frequency,
        cfg.noise_lacunarity,
        cfg.noise_gain,
    )
    water_cut = _quantile(base, cfg.water_quantile) if cfg.water_quantile > 0 else None
    hills_cut = _quantile(base, 1 - cfg.hills_quantile) if cfg.hills_quantile > 0 else None
    ruins_cut = _quantile(ruins, 1 - cfg.hills_quantile)
    forest_cut = _quantile(base, cfg.water_quantile + cfg.forest_quantile) if cfg.forest_quantile > 0 else None

    terrain: list[TerrainType] = ["wasteland"] * n
    for i in range(n):
        if water_cut is not None and base[i] <= water_cut:
            terrain[i] = "water"
        elif hills_cut is not None and base[i] >= hills_cut:
            terrain[i] = "hills"
        elif ruins[i] >= ruins_cut:
            terrain[i] = "ruins"
        elif forest_cut is not None and base[i] <= forest_cut:
            terrain[i] = "forest"
        else:
            terrain[i] = "wasteland"
    return terrain


# ── Rivers ──────────────────────────────────────────────────────────────


def generate_rivers(
    recipe: WorldRecipe,
    terrain: list[TerrainType],
    protected_tiles: set[int] | None = None,
) -> list[int]:
    """Return a flat, sorted tile-index list of meandering rivers (display-only mask).

    Rivers are real meandering geometry traced by ``_trace_river`` but never written
    into *terrain*: like ``generate_road_mask`` the result is a display-only mask with
    zero gameplay impact, so a river can never alter traversal, ETA, or movement.
    ``protected_tiles`` (defaults to the shared player vault-slot tiles plus a dry
    margin) is never painted, so a river never covers a vault disc. *terrain* is
    read-only input accepted for call-shape symmetry with ``generate_road_mask``. Pure:
    same recipe + input + protected set yields identical output.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    del terrain  # read-only: accepted only to mirror generate_road_mask's (recipe, terrain) shape
    protected = _default_protected_tiles(width, height) if protected_tiles is None else protected_tiles
    mask: set[int] = set()
    rng = _stream(recipe, "rivers")
    for _ in range(RIVER_COUNT):
        _trace_river(mask, width, height, rng, protected)
    return sorted(_filter_small_mask_components(mask, width, height, WATER_MIN_COMPONENT))


def _default_protected_tiles(width: int, height: int) -> set[int]:
    """The shared player vault-slot tiles with a dry margin; imported lazily to stay settings-free."""
    from app.utils.vault_slots import slot_tile_indices

    return slot_tile_indices(width, height, margin=VAULT_SLOT_DRY_MARGIN)


def _trace_river(mask: set[int], width: int, height: int, rng: Random, protected: set[int]) -> None:
    """Trace one meandering river from a random edge to an adjacent edge into *mask*."""
    start_edge = _RIVER_EDGES[int(rng.random() * len(_RIVER_EDGES))]
    end_edge = _RIVER_ADJACENT_EDGES[start_edge][int(rng.random() * 2)]
    x, y = _edge_position(start_edge, _edge_point(rng, start_edge, width, height), width, height)
    tx, ty = _edge_position(end_edge, _edge_point(rng, end_edge, width, height), width, height)

    # Wander toward the interior first so endpoints that happen to be close still
    # produce a long, winding waterway.
    wander_cx = width / 2 + (rng.random() - 0.5) * width * 0.3
    wander_cy = height / 2 + (rng.random() - 0.5) * height * 0.3
    for _ in range(RIVER_WANDER_STEPS):
        _carve(mask, width, height, x, y, protected)
        x, y = _step(x, y, wander_cx, wander_cy, width, height, rng, RIVER_JITTER * 2)

    if abs(x - tx) + abs(y - ty) < 70:
        if end_edge in ("top", "bottom"):
            tx = width - 1 - tx
        else:
            ty = height - 1 - ty

    max_steps = max(RIVER_MAX_STEPS, math.ceil(math.hypot(width, height) * 1.6))
    steps = 0
    while steps < max_steps:
        _carve(mask, width, height, x, y, protected)
        if _on_edge(x, y, width, height, end_edge):
            break
        x, y = _step(x, y, tx, ty, width, height, rng, RIVER_JITTER)
        steps += 1

    # If the jittered walk ran out of steps, march straight to the target edge.
    while not _on_edge(x, y, width, height, end_edge):
        _carve(mask, width, height, x, y, protected)
        length = math.hypot(tx - x, ty - y)
        if length == 0:
            break
        x = min(width - 1, max(0, round(x + (tx - x) / length)))
        y = min(height - 1, max(0, round(y + (ty - y) / length)))


def _edge_point(rng: Random, edge: str, width: int, height: int) -> int:
    """A middle-biased position along *edge* in tiles."""
    span = width if edge in ("top", "bottom") else height
    return int(span * 0.2 + rng.random() * span * 0.6)


def _edge_position(edge: str, point: int, width: int, height: int) -> tuple[int, int]:
    """Tile coordinate of *point* along *edge*."""
    if edge == "top":
        return point, 0
    if edge == "bottom":
        return point, height - 1
    if edge == "left":
        return 0, point
    return width - 1, point


def _step(
    x: int, y: int, target_x: float, target_y: float, width: int, height: int, rng: Random, jitter: float
) -> tuple[int, int]:
    """One jittered unit step toward a target, clamped to the grid."""
    dx, dy = target_x - x, target_y - y
    length = math.hypot(dx, dy)
    if length < 1:
        return x, y
    nx, ny = dx / length, dy / length
    angle = (rng.random() - 0.5) * jitter
    sx, sy = nx - ny * angle, ny + nx * angle
    scale = math.hypot(sx, sy)
    step_x = sx / scale if scale > 0 else 0
    step_y = sy / scale if scale > 0 else 0
    return min(width - 1, max(0, round(x + step_x))), min(height - 1, max(0, round(y + step_y)))


def _on_edge(x: int, y: int, width: int, height: int, edge: str) -> bool:
    """True when (x, y) lies on the named grid edge."""
    if edge == "top":
        return y == 0
    if edge == "bottom":
        return y == height - 1
    if edge == "left":
        return x == 0
    return x == width - 1


def _carve(mask: set[int], width: int, height: int, x: int, y: int, protected: set[int]) -> None:
    """Stamp a RIVER_WIDTH square of river tiles into *mask*, skipping protected (vault) tiles."""
    half = RIVER_WIDTH // 2
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                idx = ny * width + nx
                if idx not in protected:
                    mask.add(idx)


def _filter_small_mask_components(mask: set[int], width: int, height: int, min_size: int) -> set[int]:
    """Return *mask* with 4-connected components below *min_size* removed."""
    remaining = set(mask)
    seen: set[int] = set()
    for start in mask:
        if start in seen:
            continue
        component: list[int] = []
        stack = [start]
        seen.add(start)
        while stack:
            idx = stack.pop()
            component.append(idx)
            cx, cy = idx % width, idx // width
            for dx, dy in _ORTHO:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < width and 0 <= ny < height:
                    nidx = ny * width + nx
                    if nidx in mask and nidx not in seen:
                        seen.add(nidx)
                        stack.append(nidx)
        if len(component) < min_size:
            remaining.difference_update(component)
    return remaining


# ── Slots (land-safe) ───────────────────────────────────────────────────


def _is_traversable(terrain: list[TerrainType], width: int, x: int, y: int) -> bool:
    return TRAVEL_COST[terrain[y * width + x]] != math.inf


def _largest_traversable_component(terrain: list[TerrainType], width: int, height: int) -> set[int]:
    """Tile indices in the biggest 4-connected traversable region.

    Restricting slots (and thus vaults) to one component keeps every pair mutually
    reachable under TRAVEL_COST; island clusters would otherwise satisfy the
    land/spacing checks while being unreachable from each other.
    """
    seen: set[int] = set()
    largest: set[int] = set()
    for start in range(width * height):
        if start in seen or not _is_traversable(terrain, width, start % width, start // width):
            continue
        component: set[int] = set()
        stack = [start]
        seen.add(start)
        while stack:
            idx = stack.pop()
            component.add(idx)
            x, y = idx % width, idx // width
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    nidx = ny * width + nx
                    if nidx not in seen and _is_traversable(terrain, width, nx, ny):
                        seen.add(nidx)
                        stack.append(nidx)
        if len(component) > len(largest):
            largest = component
    return largest


def generate_slots(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[GeneratedSlot]:
    """Assign slots to unique, traversable, spaced, mutually reachable positions.

    Fails clearly (``RuntimeError``) when the recipe cannot place all slots rather
    than falling back to an unsafe coordinate.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    rng = _stream(recipe, "slots")

    main_component = _largest_traversable_component(terrain, width, height)
    land = [(x, y) for y in range(height) for x in range(width) if y * width + x in main_component]
    if len(land) < cfg.slot_count:
        raise RuntimeError(f"terrain has {len(land)} reachable cells, fewer than {cfg.slot_count} slots")

    rng.shuffle(land)
    chosen: list[tuple[int, int]] = []
    spacing_sq = cfg.slot_min_spacing * cfg.slot_min_spacing
    for x, y in land:
        if len(chosen) == cfg.slot_count:
            break
        if all((x - cx) ** 2 + (y - cy) ** 2 >= spacing_sq for cx, cy in chosen):
            chosen.append((x, y))
    if len(chosen) < cfg.slot_count:
        raise RuntimeError(f"only placed {len(chosen)} of {cfg.slot_count} slots at spacing {cfg.slot_min_spacing}")

    slots: list[GeneratedSlot] = []
    for index, (x, y) in enumerate(chosen):
        coord_x = round((x + 0.5) * (100 / width), 4)
        coord_y = round((y + 0.5) * (100 / height), 4)
        slots.append(GeneratedSlot(slot_index=index, tile_x=x, tile_y=y, coord_x=coord_x, coord_y=coord_y))
    return slots


# ── Roads (display-only mask) ───────────────────────────────────────────


def generate_road_mask(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[int]:
    """A flat, sorted tile-index list of roads spanning deterministic in-recipe junctions.

    Junctions come from the ``roads:junctions`` stream; spanning order is a Prim MST
    weighted by straight-line sampled terrain cost; each edge is routed with 4-connected
    A* at ROAD_COST, detouring around water (no bridge tiles). Unroutable edges are
    skipped, never raised. Display-only: it never mutates *terrain* and does not touch
    travel cost, ETA, or movement.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    junctions = _road_junctions(recipe, terrain)
    if len(junctions) < 2:
        return []

    count = len(junctions)
    weights = [[0.0] * count for _ in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            weights[i][j] = weights[j][i] = _sample_line_cost(terrain, width, height, junctions[i], junctions[j])

    mask: set[int] = set()
    for a, b in _prim_mst(weights):
        path = _astar_tiles(terrain, width, height, junctions[a], junctions[b])
        if path is not None:
            mask.update(path)
    return sorted(mask)


def _road_junctions(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[int]:
    """Spaced land junctions drawn from the largest traversable component, seeded by ``roads:junctions``."""
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    rng = _stream(recipe, "roads:junctions")
    candidates = sorted(_largest_traversable_component(terrain, width, height))
    rng.shuffle(candidates)
    chosen: list[tuple[int, int]] = []
    spacing_sq = ROAD_JUNCTION_MIN_SPACING * ROAD_JUNCTION_MIN_SPACING
    for idx in candidates:
        if len(chosen) >= ROAD_JUNCTION_COUNT:
            break
        x, y = idx % width, idx // width
        if all((x - cx) ** 2 + (y - cy) ** 2 >= spacing_sq for cx, cy in chosen):
            chosen.append((x, y))
    if len(chosen) < 2:
        chosen = [(idx % width, idx // width) for idx in candidates[:2]]
    return [y * width + x for x, y in chosen]


def _sample_line_cost(terrain: list[TerrainType], width: int, height: int, a: int, b: int) -> float:
    """Straight-line sampled ROAD_COST between two tiles (water priced high, not impassable)."""
    ax, ay = a % width, a // width
    bx, by = b % width, b // width
    dx, dy = bx - ax, by - ay
    steps = max(1, math.ceil(math.hypot(dx, dy) / LINE_SAMPLE_STEP))
    cost = 0.0
    for s in range(steps + 1):
        t = s / steps
        x = min(width - 1, max(0, round(ax + dx * t)))
        y = min(height - 1, max(0, round(ay + dy * t)))
        kind = terrain[y * width + x]
        cost += WATER_SAMPLE_COST if kind == "water" else ROAD_COST[kind]
    return cost


def _prim_mst(weights: list[list[float]]) -> list[tuple[int, int]]:
    """Prim MST over a dense weight matrix; ties break by lowest index."""
    count = len(weights)
    in_tree = [False] * count
    key = [math.inf] * count
    parent = [-1] * count
    key[0] = 0.0
    edges: list[tuple[int, int]] = []
    for _ in range(count):
        u = -1
        best = math.inf
        for i in range(count):
            if not in_tree[i] and key[i] < best:
                best, u = key[i], i
        if u == -1:
            break
        in_tree[u] = True
        if parent[u] != -1:
            edges.append((parent[u], u))
        for v in range(count):
            if not in_tree[v] and weights[u][v] < key[v]:
                key[v] = weights[u][v]
                parent[v] = u
    return edges


def _astar_tiles(terrain: list[TerrainType], width: int, height: int, start: int, goal: int) -> list[int] | None:
    """4-connected A* at ROAD_COST; water is impassable. Returns tile indices, or None if unroutable."""
    if start == goal:
        return [start]
    size = width * height
    g_score = [math.inf] * size
    came_from = [-1] * size
    closed = [False] * size
    g_score[start] = 0.0
    heap: list[tuple[float, int]] = [(0.0, start)]
    while heap:
        _, current = heapq.heappop(heap)
        if current == goal:
            return _reconstruct_tiles(came_from, goal)
        if closed[current]:
            continue
        closed[current] = True
        cx, cy = current % width, current // width
        for dx, dy in _ORTHO:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbor = ny * width + nx
            tile_cost = ROAD_COST[terrain[neighbor]]
            if tile_cost == math.inf:
                continue
            tentative = g_score[current] + tile_cost
            if tentative < g_score[neighbor]:
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                heapq.heappush(heap, (tentative + _manhattan_cost(neighbor, goal, width, _ROAD_MIN_COST), neighbor))
    return None


def _manhattan_cost(idx: int, goal: int, width: int, min_cost: float) -> float:
    """Admissible 4-connected lower bound from *idx* to *goal*."""
    return (abs(idx % width - goal % width) + abs(idx // width - goal // width)) * min_cost


def _reconstruct_tiles(came_from: list[int], goal: int) -> list[int]:
    """Walk predecessor links back from *goal* and return the path start→goal."""
    path: list[int] = []
    current = goal
    while current != -1:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def generate_world(recipe: WorldRecipe) -> GeneratedWorld:
    """Generate the full snapshot for a recipe (pure; no occupancy, no discoveries).

    Order matters: terrain is generated once and never mutated; rivers and roads are
    display-only masks derived from that terrain (rivers traced directly, roads routed
    around terrain water), and slots are placed on the terrain's land-safe component.
    """
    terrain = generate_terrain(recipe)
    rivers = generate_rivers(recipe, terrain)
    slots = generate_slots(recipe, terrain)
    roads = generate_road_mask(recipe, terrain)
    return GeneratedWorld(
        recipe_fingerprint=recipe.fingerprint(),
        generator_version=recipe.generator_version,
        width=recipe.config.width,
        height=recipe.config.height,
        terrain=terrain,
        slots=slots,
        roads=roads,
        rivers=rivers,
    )


def canonical_payload(world: GeneratedWorld) -> str:
    """Canonical JSON of terrain + slots + display masks (sorted keys, fixed separators, no spaces).

    Required so the snapshot checksum is stable: "byte-identical" needs canonical
    serialization and defined numeric precision (coordinates are already rounded to
    4 dp in ``generate_slots``), not just a seeded PRNG.
    """
    return json.dumps(
        {
            "terrain": list(world.terrain),
            "slots": [asdict(slot) for slot in world.slots],
            "roads": list(world.roads),
            "rivers": list(world.rivers),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def snapshot_checksum(world: GeneratedWorld) -> str:
    """Stable checksum of the canonical snapshot payload."""
    return hashlib.blake2b(canonical_payload(world).encode("utf-8"), digest_size=16).hexdigest()
