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
from collections import deque
from dataclasses import asdict, dataclass, field
from itertools import pairwise
from random import Random
from typing import Literal

# ── Contract constants ──────────────────────────────────────────────────

# Snapshot payload/identity version. Bump for payload changes (e.g. new masks); it
# feeds the recipe fingerprint but not the RNG, so it never re-rolls the world.
GENERATOR_VERSION = 2
# Geography seed epoch. Bump only for intentional terrain/slot re-rolls.
SEED_EPOCH = 1
# World Map v3: region-layered geography. Kept explicit so v2 recipes stay byte-identical.
MAP_V3_GENERATOR_VERSION = 3
MAP_V3_SEED_EPOCH = 2
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
ROAD_EXTRA_EDGE_RATIO = 0.14
ROAD_CURVE_OFFSET = 0.28
ROAD_CURVE_LONG_EDGE = 8
ROAD_SLOT_MAX_DISTANCE = 4
TOWN_RADIUS = 4
TOWN_GRID_STEP = 2
TOWN_TEMPLATES = ("grid", "crossroads", "linear", "grid")
TOWN_RADII = (5, 4, 4, 5)
TOWN_ROTATIONS = (0.12, -0.18, 0.24, -0.1)
ROAD_COVERAGE_RADIUS = 5
ROAD_COVERAGE_TARGET = 0.75
ROAD_COVERAGE_EDGE_LIMIT = 24
ANCHOR_COUNT = 100
ANCHOR_CLUSTER_COUNT = 8
ANCHOR_CLUSTER_RADIUS = 9
ANCHOR_MIN_SPACING = 3

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


@dataclass(frozen=True)
class BiomeProfile:
    """Per-region quantile cuts, expressed as fractions of the global field distribution."""

    water: float
    hills: float
    forest: float
    ruins: float


@dataclass(frozen=True)
class RegionSpec:
    """A named area: a warped-Voronoi center plus its biome profile."""

    id: str
    name: str
    center_x: float
    center_y: float
    profile: BiomeProfile
    danger_tier: int = 1


DEFAULT_REGIONS: tuple[RegionSpec, ...] = (
    RegionSpec("green_belt", "Green Belt", 0.28, 0.30, BiomeProfile(0.05, 0.06, 0.32, 0.06), 1),
    RegionSpec("rust_basin", "Rust Basin", 0.28, 0.74, BiomeProfile(0.004, 0.10, 0.03, 0.34), 2),
    RegionSpec("broken_highlands", "Broken Highlands", 0.72, 0.30, BiomeProfile(0.01, 0.40, 0.04, 0.10), 3),
    RegionSpec("mirelands", "Mirelands", 0.74, 0.76, BiomeProfile(0.12, 0.03, 0.36, 0.04), 2),
)

REGION_CENTER_JITTER = 0.08
REGION_WARP_AMPLITUDE = 0.06


@dataclass
class WorldRecipe:
    """The full recipe: seed, config, payload version, geography epoch, public anchors."""

    seed: str
    config: WorldConfig = field(default_factory=WorldConfig)
    anchors: tuple[PublicAnchor, ...] = ()
    generator_version: int = GENERATOR_VERSION
    seed_epoch: int = SEED_EPOCH
    world_id: str = WORLD_ID

    def fingerprint(self) -> str:
        """Stable recipe fingerprint (hex); anchors are part of the hash.

        The geography epoch joins the hash only when it differs from the legacy default, so v2
        recipes keep their historical fingerprint byte-for-byte.
        """
        parts = [
            self.world_id,
            str(self.generator_version),
            self.seed,
            self._config_tuple(),
            ";".join(f"{a.id}:{a.coord_x:.6f}:{a.coord_y:.6f}" for a in self.anchors),
        ]
        if self.seed_epoch != SEED_EPOCH:
            parts.insert(2, str(self.seed_epoch))
        return _hash(*parts)

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
    """The generated snapshot (regions, terrain, slots, masks, validation, fingerprint)."""

    recipe_fingerprint: str
    generator_version: int
    width: int
    height: int
    terrain: list[TerrainType]
    slots: list[GeneratedSlot]
    roads: list[int] = field(default_factory=list)
    rivers: list[int] = field(default_factory=list)
    road_edges: list[dict] = field(default_factory=list)
    road_anchors: list[dict] = field(default_factory=list)
    towns: list[dict] = field(default_factory=list)
    regions: list[dict] = field(default_factory=list)
    region_map: list[int] = field(default_factory=list)
    validation: dict = field(default_factory=dict)


# ── Deterministic primitives ────────────────────────────────────────────


def _hash(*parts: str) -> str:
    """Stable hash of joined parts; never Python hash() (process-dependent)."""
    digest = hashlib.blake2b("\x1f".join(parts).encode("utf-8"), digest_size=16)
    return digest.hexdigest()


def _stream(recipe: WorldRecipe, namespace: str) -> Random:
    """Independent seeded PRNG per named stream, stable within a geography epoch."""
    seed_bytes = _hash(str(recipe.seed_epoch), recipe.seed, namespace)
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


# ── Regions ─────────────────────────────────────────────────────────────


def generate_regions(recipe: WorldRecipe) -> tuple[list[dict], list[int]]:
    """Warped-Voronoi region assignment, deterministic from the ``regions`` stream.

    Returns resolved region metadata plus a row-major region-id map. v2 recipes never call
    this, so their terrain, slots and fingerprints stay unchanged.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    rng = _stream(recipe, "regions")
    centers: list[tuple[float, float]] = []
    for spec in DEFAULT_REGIONS:
        jitter_x = (rng.random() - 0.5) * REGION_CENTER_JITTER * width
        jitter_y = (rng.random() - 0.5) * REGION_CENTER_JITTER * height
        centers.append((spec.center_x * width + jitter_x, spec.center_y * height + jitter_y))
    phase_x = rng.random() * math.tau
    phase_y = rng.random() * math.tau
    warp_x = max(1.0, width * REGION_WARP_AMPLITUDE)
    warp_y = max(1.0, height * REGION_WARP_AMPLITUDE)
    freq_x = math.tau * 2 / max(1, width)
    freq_y = math.tau * 2 / max(1, height)

    region_map: list[int] = []
    for y in range(height):
        for x in range(width):
            warped_x = (
                x + math.sin(y * freq_y + phase_x) * warp_x + math.sin((x + y) * freq_x * 0.5 + phase_y) * warp_x * 0.5
            )
            warped_y = (
                y + math.sin(x * freq_x + phase_y) * warp_y + math.sin((x + y) * freq_y * 0.5 + phase_x) * warp_y * 0.5
            )
            region_map.append(
                min(
                    range(len(centers)),
                    key=lambda index: (warped_x - centers[index][0]) ** 2 + (warped_y - centers[index][1]) ** 2,
                )
            )

    regions = [
        {
            "id": spec.id,
            "name": spec.name,
            "danger_tier": spec.danger_tier,
            "center_x": round(centers[index][0] / width * 100, 4),
            "center_y": round(centers[index][1] / height * 100, 4),
            "biome": asdict(spec.profile),
        }
        for index, spec in enumerate(DEFAULT_REGIONS)
    ]
    return regions, region_map


# ── Terrain ─────────────────────────────────────────────────────────────


def _profile_thresholds(
    base: list[float], ruins: list[float], profile: BiomeProfile
) -> tuple[float | None, float | None, float, float | None]:
    water_cut = _quantile(base, profile.water) if profile.water > 0 else None
    hills_cut = _quantile(base, 1 - profile.hills) if profile.hills > 0 else None
    ruins_cut = _quantile(ruins, 1 - profile.ruins)
    forest_cut = _quantile(base, min(0.9999, profile.water + profile.forest)) if profile.forest > 0 else None
    return water_cut, hills_cut, ruins_cut, forest_cut


def _classify(
    base_value: float,
    ruins_value: float,
    thresholds: tuple[float | None, float | None, float, float | None],
) -> TerrainType:
    water_cut, hills_cut, ruins_cut, forest_cut = thresholds
    if water_cut is not None and base_value <= water_cut:
        return "water"
    if hills_cut is not None and base_value >= hills_cut:
        return "hills"
    if ruins_value >= ruins_cut:
        return "ruins"
    if forest_cut is not None and base_value <= forest_cut:
        return "forest"
    return "wasteland"


def generate_terrain(recipe: WorldRecipe, region_map: list[int] | None = None) -> list[TerrainType]:
    """Classify terrain from two independent fBm fields (base + ruins).

    With a ``region_map`` every tile uses its region's biome profile; without one the legacy
    global quantiles apply unchanged, so v2 recipes remain byte-identical.
    """
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
    if region_map is None:
        thresholds = (
            _quantile(base, cfg.water_quantile) if cfg.water_quantile > 0 else None,
            _quantile(base, 1 - cfg.hills_quantile) if cfg.hills_quantile > 0 else None,
            _quantile(ruins, 1 - cfg.hills_quantile),
            _quantile(base, cfg.water_quantile + cfg.forest_quantile) if cfg.forest_quantile > 0 else None,
        )
        return [_classify(base[i], ruins[i], thresholds) for i in range(n)]

    region_tiles: dict[int, list[int]] = {index: [] for index in range(len(DEFAULT_REGIONS))}
    for index, region_id in enumerate(region_map):
        region_tiles[region_id].append(index)
    regional_thresholds = {
        region_id: _profile_thresholds(
            [base[index] for index in tiles],
            [ruins[index] for index in tiles],
            DEFAULT_REGIONS[region_id].profile,
        )
        for region_id, tiles in region_tiles.items()
        if tiles
    }
    return [_classify(base[i], ruins[i], regional_thresholds[region_map[i]]) for i in range(n)]


# ── Rivers ──────────────────────────────────────────────────────────────


def generate_rivers(
    recipe: WorldRecipe,
    terrain: list[TerrainType],
    protected_tiles: set[int] | None = None,
) -> list[int]:
    """Return a flat, sorted tile-index list of meandering rivers (display-only mask)."""
    mask, _paths = generate_rivers_with_paths(recipe, terrain, protected_tiles)
    return mask


def generate_rivers_with_paths(
    recipe: WorldRecipe,
    terrain: list[TerrainType],
    protected_tiles: set[int] | None = None,
    *,
    carve: bool = False,
) -> tuple[list[int], list[list[int]]]:
    """Return the river mask plus its display centrelines, split around protected vault tiles.

    Rivers are real meandering geometry traced by ``_trace_river`` but never written into
    *terrain*. ``protected_tiles`` (defaults to the shared vault-slot tiles plus a dry margin)
    is never painted, so a river never covers a vault disc. *terrain* is read-only input
    accepted for call-shape symmetry with ``generate_road_mask``. Pure: same recipe + input +
    protected set yields identical output.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    protected = _default_protected_tiles(width, height) if protected_tiles is None else protected_tiles
    carved_terrain = terrain if carve else None
    mask: set[int] = set()
    paths: list[list[int]] = []
    rng = _stream(recipe, "rivers")
    for _ in range(RIVER_COUNT):
        paths.extend(
            [y * width + x for x, y in segment]
            for segment in _trace_river(mask, width, height, rng, protected, carved_terrain)
            if len(segment) >= 2
        )
    return sorted(_filter_small_mask_components(mask, width, height, WATER_MIN_COMPONENT)), paths


def _default_protected_tiles(width: int, height: int) -> set[int]:
    """The shared player vault-slot tiles with a dry margin; imported lazily to stay settings-free."""
    from app.utils.vault_slots import slot_tile_indices

    return slot_tile_indices(width, height, margin=VAULT_SLOT_DRY_MARGIN)


def _trace_river(
    mask: set[int],
    width: int,
    height: int,
    rng: Random,
    protected: set[int],
    terrain: list[TerrainType] | None = None,
) -> list[list[tuple[int, int]]]:
    """Trace one meandering river into *mask*; return its centreline segments."""
    segments: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []

    def record(x: int, y: int) -> None:
        nonlocal current
        point = (x, y)
        if current and current[-1] == point:
            return
        current.append(point)

    start_edge = _RIVER_EDGES[int(rng.random() * len(_RIVER_EDGES))]
    end_edge = _RIVER_ADJACENT_EDGES[start_edge][int(rng.random() * 2)]
    x, y = _edge_position(start_edge, _edge_point(rng, start_edge, width, height), width, height)
    tx, ty = _edge_position(end_edge, _edge_point(rng, end_edge, width, height), width, height)

    # Wander toward the interior first so endpoints that happen to be close still
    # produce a long, winding waterway.
    wander_cx = width / 2 + (rng.random() - 0.5) * width * 0.3
    wander_cy = height / 2 + (rng.random() - 0.5) * height * 0.3
    for _ in range(RIVER_WANDER_STEPS):
        _carve(mask, width, height, x, y, protected, terrain)
        record(x, y)
        x, y = _step(x, y, wander_cx, wander_cy, width, height, rng, RIVER_JITTER * 2)

    if abs(x - tx) + abs(y - ty) < 70:
        if end_edge in ("top", "bottom"):
            tx = width - 1 - tx
        else:
            ty = height - 1 - ty

    max_steps = max(RIVER_MAX_STEPS, math.ceil(math.hypot(width, height) * 1.6))
    steps = 0
    while steps < max_steps:
        _carve(mask, width, height, x, y, protected, terrain)
        record(x, y)
        if _on_edge(x, y, width, height, end_edge):
            break
        x, y = _step(x, y, tx, ty, width, height, rng, RIVER_JITTER)
        steps += 1

    # If the jittered walk ran out of steps, march straight to the target edge.
    while not _on_edge(x, y, width, height, end_edge):
        _carve(mask, width, height, x, y, protected, terrain)
        record(x, y)
        length = math.hypot(tx - x, ty - y)
        if length == 0:
            break
        x = min(width - 1, max(0, round(x + (tx - x) / length)))
        y = min(height - 1, max(0, round(y + (ty - y) / length)))

    if len(current) >= 2:
        segments.append(current)
    return segments


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


def _carve(
    mask: set[int],
    width: int,
    height: int,
    x: int,
    y: int,
    protected: set[int],
    terrain: list[TerrainType] | None = None,
) -> None:
    """Stamp a RIVER_WIDTH square into *mask*, skipping protected vault tiles; v3 also carves water."""
    half = RIVER_WIDTH // 2
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                idx = ny * width + nx
                if idx not in protected:
                    mask.add(idx)
                    if terrain is not None:
                        terrain[idx] = "water"


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


def _ensure_slot_land(terrain: list[TerrainType], width: int, height: int) -> None:
    """Keep the fixed vault-slot tiles and their dry margin on land (v3 geography guarantee)."""
    from app.utils.vault_slots import slot_tile_indices

    for index in slot_tile_indices(width, height, margin=VAULT_SLOT_DRY_MARGIN):
        if terrain[index] == "water":
            terrain[index] = "wasteland"


def _connect_slots(terrain: list[TerrainType], width: int, height: int) -> None:
    """Keep every fixed vault slot inside the main traversable component.

    A slot can be land yet isolated by a water ring; carve a straight land causeway to the
    nearest tile of the main component. Deterministic and v3-only.
    """
    from app.utils.vault_slots import slot_tile_indices

    for _ in range(2):
        main = _largest_traversable_component(terrain, width, height)
        missing = [index for index in sorted(slot_tile_indices(width, height)) if index not in main]
        if not missing:
            return
        main_tiles = sorted(main)
        if not main_tiles:
            return
        for slot in missing:
            slot_x, slot_y = slot % width, slot // width
            nearest = min(
                main_tiles,
                key=lambda index: (index % width - slot_x) ** 2 + (index // width - slot_y) ** 2,
            )
            _carve_land_line(terrain, width, height, (slot_x, slot_y), (nearest % width, nearest // width))


def _carve_land_line(
    terrain: list[TerrainType], width: int, height: int, start: tuple[int, int], end: tuple[int, int]
) -> None:
    """Carve a 4-connected L-shaped land path between two tiles (v3 slot connectivity)."""
    x, y = start
    end_x, end_y = end
    while x != end_x:
        x += 1 if end_x > x else -1
        if 0 <= x < width and terrain[y * width + x] == "water":
            terrain[y * width + x] = "wasteland"
    while y != end_y:
        y += 1 if end_y > y else -1
        if 0 <= y < height and terrain[y * width + x] == "water":
            terrain[y * width + x] = "wasteland"


def _shared_grid_slots(width: int, height: int, slot_count: int) -> list[GeneratedSlot]:
    """Derive snapshot slots from the canonical shared vault grid used for real vault placement."""
    from app.core.game_config import game_config
    from app.utils.vault_slots import slot_coords
    from app.utils.world_terrain import tile_from_registry

    count = min(slot_count, game_config.vault_slots.count)
    slots: list[GeneratedSlot] = []
    for index in range(count):
        coord_x, coord_y = slot_coords(index)
        tile_x, tile_y = tile_from_registry(width, height, coord_x, coord_y)
        slots.append(
            GeneratedSlot(
                slot_index=index,
                tile_x=tile_x,
                tile_y=tile_y,
                coord_x=round(coord_x, 4),
                coord_y=round(coord_y, 4),
            )
        )
    return slots


def build_validation(
    regions: list[dict], region_map: list[int], terrain: list[TerrainType], width: int, height: int
) -> dict:
    """Region and slot reachability report using the same traversal rules as movement."""
    if not regions or not region_map:
        return {}
    from app.utils.vault_slots import slot_tile_indices

    main_component = _largest_traversable_component(terrain, width, height)
    counts: dict[str, dict] = {spec["id"]: {"tiles": 0, "terrain": {}, "in_main_component": 0} for spec in regions}
    for index, region_id in enumerate(region_map):
        data = counts[regions[region_id]["id"]]
        data["tiles"] += 1
        kind = terrain[index]
        data["terrain"][kind] = data["terrain"].get(kind, 0) + 1
        if index in main_component:
            data["in_main_component"] += 1
    slot_tiles = slot_tile_indices(width, height)
    return {
        "regions": counts,
        "isolated_regions": [region_id for region_id, data in counts.items() if data["in_main_component"] == 0],
        "slot_tiles": len(slot_tiles),
        "reachable_slot_tiles": sum(1 for index in slot_tiles if index in main_component),
    }


def generate_slots(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[GeneratedSlot]:
    """Assign slots to unique, traversable, spaced, mutually reachable positions.

    v3 derives the snapshot slots from the canonical shared vault grid; v2 keeps the
    legacy land-safe placement so existing worlds and their tests stay unchanged.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    if recipe.generator_version >= MAP_V3_GENERATOR_VERSION:
        return _shared_grid_slots(width, height, cfg.slot_count)
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


# ── Road anchors (locations-lite) ───────────────────────────────────────


def generate_road_anchors(
    recipe: WorldRecipe, terrain: list[TerrainType], regions: list[dict] | None = None
) -> list[dict]:
    """Seeded clustered anchors that give the road graph JS-prototype density.

    Anchors are topology only, never gameplay locations. Region centres join the set so
    inter-region highways emerge naturally.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    rng = _stream(recipe, "anchors")
    land = sorted(_largest_traversable_component(terrain, width, height))
    if not land:
        return []
    protected = _default_protected_tiles(width, height)
    nodes: list[tuple[int, int]] = []
    occupied: set[int] = set()
    region_centers: set[tuple[int, int]] = set()

    def add(x: int, y: int) -> bool:
        x = min(width - 1, max(0, x))
        y = min(height - 1, max(0, y))
        index = y * width + x
        if terrain[index] == "water" or index in protected or index in occupied:
            return False
        if any((x - nx) ** 2 + (y - ny) ** 2 < ANCHOR_MIN_SPACING**2 for nx, ny in nodes):
            return False
        nodes.append((x, y))
        occupied.add(index)
        return True

    if regions:
        for region in regions:
            center_x = round(region["center_x"] / 100 * width)
            center_y = round(region["center_y"] / 100 * height)
            for radius in range(ANCHOR_CLUSTER_RADIUS + 1):
                placed = False
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if max(abs(dx), abs(dy)) != radius:
                            continue
                        if add(center_x + dx, center_y + dy):
                            region_centers.add(nodes[-1])
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break

    candidates = land[:]
    rng.shuffle(candidates)
    centers: list[tuple[int, int]] = []
    min_center = max(8, round(min(width, height) * 0.22))
    for index in candidates:
        if len(centers) >= ANCHOR_CLUSTER_COUNT:
            break
        x, y = index % width, index // width
        if all((x - cx) ** 2 + (y - cy) ** 2 >= min_center**2 for cx, cy in centers):
            centers.append((x, y))

    per_cluster = max(1, (ANCHOR_COUNT - len(nodes)) // max(1, len(centers)))
    for center_x, center_y in centers:
        placed = 0
        attempts = 0
        while placed < per_cluster and attempts < per_cluster * 30:
            attempts += 1
            x = center_x + round((rng.random() - 0.5) * 2 * ANCHOR_CLUSTER_RADIUS)
            y = center_y + round((rng.random() - 0.5) * 2 * ANCHOR_CLUSTER_RADIUS)
            if (x - center_x) ** 2 + (y - center_y) ** 2 > ANCHOR_CLUSTER_RADIUS**2:
                continue
            if add(x, y):
                placed += 1

    for index in candidates:
        if len(nodes) >= ANCHOR_COUNT:
            break
        add(index % width, index // width)

    return [
        {
            "id": f"anchor-{index}",
            "tile_x": x,
            "tile_y": y,
            "kind": "region" if (x, y) in region_centers else "anchor",
        }
        for index, (x, y) in enumerate(nodes)
    ]


def _town_offsets(template: str, radius: int) -> list[int]:
    if template == "grid":
        return sorted({-radius, -radius + 2, -1, 1, radius - 1})
    return sorted({-radius, -2, 2, radius})


def _point_in_polygon(x: float, y: float, points: list[list[float]]) -> bool:
    """Ray casting for the small town footprint polygons (points are tile coords + 0.5)."""
    inside = False
    for index in range(len(points)):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % len(points)]
        if (y1 > y) != (y2 > y):
            cross_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < cross_x:
                inside = not inside
    return inside


def _town_blocks(
    terrain: list[TerrainType],
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    radius: int,
    rotation: float,
    template: str,
    rng: Random,
    polygon: list[list[float]] | None = None,
) -> list[list[list[float]]]:
    """Low-rise block parcels between the main streets; skipped over water."""
    offsets = _town_offsets(template, radius)
    ux, uy = math.cos(rotation), math.sin(rotation)
    vx, vy = -uy, ux
    blocks: list[list[list[float]]] = []
    for x_index in range(len(offsets) - 1):
        for y_index in range(len(offsets) - 1):
            left, right = offsets[x_index], offsets[x_index + 1]
            top, bottom = offsets[y_index], offsets[y_index + 1]
            if left < 0 < right or top < 0 < bottom:
                continue
            if rng.random() < 0.14:
                continue
            local_x = (left + right) / 2
            local_y = (top + bottom) / 2
            if polygon is not None and not _point_in_polygon(
                center_x + local_x + 0.5, center_y + local_y + 0.5, polygon
            ):
                continue
            half_x = max(0.3, (right - left) / 2 - 0.22)
            half_y = max(0.3, (bottom - top) / 2 - 0.22)
            corners: list[tuple[float, float]] = []
            for dx, dy in ((-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)):
                px = center_x + local_x + dx * ux + dy * vx
                py = center_y + local_y + dx * uy + dy * vy
                tile_x, tile_y = round(px), round(py)
                if not (0 <= tile_x < width and 0 <= tile_y < height) or terrain[tile_y * width + tile_x] == "water":
                    corners = []
                    break
                corners.append((px, py))
            if corners:
                blocks.append([[round(px + 0.5, 3), round(py + 0.5, 3)] for px, py in corners])
    return blocks


def generate_towns(
    recipe: WorldRecipe,
    terrain: list[TerrainType],
    anchors: list[dict],
    regions: list[dict],
) -> list[dict]:
    """Seed varied town footprints around the region hubs.

    Towns are metadata plus an irregular polygon; their streets are generated by
    ``_add_town_streets`` once the road graph exists. Keeping the footprint separate lets
    the renderer paint a soft urban ground patch under the orthogonal grid, without
    adding a second gameplay mask.
    """
    hubs = [anchor for anchor in anchors if anchor.get("kind") == "region"]
    towns: list[dict] = []
    for index, (anchor, region) in enumerate(zip(hubs, regions, strict=False)):
        center_x = int(anchor["tile_x"])
        center_y = int(anchor["tile_y"])
        radius = TOWN_RADII[index % len(TOWN_RADII)]
        template = TOWN_TEMPLATES[index % len(TOWN_TEMPLATES)]
        rng = _stream(recipe, f"town-shape:{index}")
        points: list[list[float]] = []
        for step in range(10):
            angle = (2 * math.pi * step) / 10
            distance = radius * (0.78 + 0.22 * rng.random())
            x = center_x + math.cos(angle) * distance * 1.08
            y = center_y + math.sin(angle) * distance * 0.82
            points.append([round(x + 0.5, 3), round(y + 0.5, 3)])
        block_rng = _stream(recipe, f"town-blocks:{index}")
        towns.append(
            {
                "id": f"town-{index}",
                "region_id": str(region["id"]),
                "template": template,
                "rotation": TOWN_ROTATIONS[index % len(TOWN_ROTATIONS)],
                "center_x": center_x,
                "center_y": center_y,
                "radius": radius,
                "points": points,
                "blocks": _town_blocks(
                    terrain,
                    recipe.config.width,
                    recipe.config.height,
                    center_x,
                    center_y,
                    radius,
                    TOWN_ROTATIONS[index % len(TOWN_ROTATIONS)],
                    template,
                    block_rng,
                    points,
                ),
            }
        )
    return towns


def _road_distance_map(roads: set[int], terrain: list[TerrainType], width: int, height: int) -> list[int]:
    """4-connected distance from every tile to the nearest road tile (-1 for water)."""
    distance = [-1] * (width * height)
    queue: deque[int] = deque()
    for index in roads:
        if terrain[index] != "water":
            distance[index] = 0
            queue.append(index)
    while queue:
        current = queue.popleft()
        cx, cy = current % width, current // width
        for dx, dy in _ORTHO:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbor = ny * width + nx
            if terrain[neighbor] == "water" or distance[neighbor] != -1:
                continue
            distance[neighbor] = distance[current] + 1
            queue.append(neighbor)
    return distance


def _nearest_road_tile(source: int, roads: set[int], width: int) -> int:
    """Deterministic nearest road tile by squared tile distance, then tile index."""
    source_x, source_y = source % width, source // width
    return min(
        roads,
        key=lambda index: ((index % width - source_x) ** 2 + (index // width - source_y) ** 2, index),
    )


def _compact_path(path: list[int], width: int) -> list[int]:
    """Drop collinear/duplicate tiles before smoothing; keeps corners and bends."""
    compact: list[int] = []
    for index in path:
        if compact and compact[-1] == index:
            continue
        if len(compact) >= 2:
            first, second = compact[-2], compact[-1]
            dx1, dy1 = second % width - first % width, second // width - first // width
            dx2, dy2 = index % width - second % width, index // width - second // width
            if (dx1, dy1) == (dx2, dy2):
                compact[-1] = index
                continue
        compact.append(index)
    return compact


def _smooth_road_points(path: list[int], width: int) -> list[list[float]]:
    """Three Chaikin passes over a compact path: rounded, non-rectilinear bends.

    Do not simplify afterwards: RDP collapses a smoothed staircase back to a near-90°
    corner, which is exactly the blocky look this renderer is replacing.
    """
    points = [((index % width) + 0.5, (index // width) + 0.5) for index in _compact_path(path, width)]
    for _ in range(4):
        if len(points) < 3:
            break
        smoothed = [points[0]]
        for first, second in pairwise(points):
            smoothed.extend(
                (
                    (0.75 * first[0] + 0.25 * second[0], 0.75 * first[1] + 0.25 * second[1]),
                    (0.25 * first[0] + 0.75 * second[0], 0.25 * first[1] + 0.75 * second[1]),
                )
            )
        smoothed.append(points[-1])
        points = smoothed
    return [[round(x, 3), round(y, 3)] for x, y in points]


def _add_oriented_street(
    terrain: list[TerrainType],
    width: int,
    height: int,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    roads: set[int],
    edges: list[dict],
    polygon: list[list[float]] | None = None,
) -> None:
    """Add contiguous land runs of a straight street at any angle."""
    dx, dy = end_x - start_x, end_y - start_y
    length = math.hypot(dx, dy)
    if length < 1:
        return
    steps = max(1, math.ceil(length * 2))
    run: list[tuple[float, float]] = []
    run_indices: list[int] = []
    seen: set[int] = set()

    def flush() -> None:
        nonlocal run, run_indices
        if len(run) >= 2:
            _add_path_tiles(roads, run_indices, terrain, width)
            edges.append(
                {"class": "town", "points": [[round(x + 0.5, 3), round(y + 0.5, 3)] for x, y in (run[0], run[-1])]}
            )
        run = []
        run_indices = []
        seen.clear()

    for step in range(steps + 1):
        t = step / steps
        x = start_x + dx * t
        y = start_y + dy * t
        tile_x, tile_y = round(x), round(y)
        if (
            not (0 <= tile_x < width and 0 <= tile_y < height)
            or terrain[tile_y * width + tile_x] == "water"
            or (polygon is not None and not _point_in_polygon(x + 0.5, y + 0.5, polygon))
        ):
            flush()
            continue
        index = tile_y * width + tile_x
        if index in seen:
            continue
        run.append((x, y))
        run_indices.append(index)
        seen.add(index)
    flush()


def _add_town_streets(
    town: dict,
    terrain: list[TerrainType],
    width: int,
    height: int,
    roads: set[int],
    edges: list[dict],
) -> None:
    """Rotated town blocks: a full grid, a crossroad with a ring, or a linear street."""
    center_x, center_y = int(town["center_x"]), int(town["center_y"])
    radius = int(town["radius"])
    template = town["template"]
    rotation = float(town.get("rotation", 0.0))
    ux, uy = math.cos(rotation), math.sin(rotation)
    vx, vy = -uy, ux

    def along_u(offset: float, extent: int = radius) -> None:
        cx, cy = center_x + offset * vx, center_y + offset * vy
        _add_oriented_street(
            terrain,
            width,
            height,
            cx - ux * extent,
            cy - uy * extent,
            cx + ux * extent,
            cy + uy * extent,
            roads,
            edges,
            town["points"],
        )

    def along_v(offset: float, extent: int = radius) -> None:
        cx, cy = center_x + offset * ux, center_y + offset * uy
        _add_oriented_street(
            terrain,
            width,
            height,
            cx - vx * extent,
            cy - vy * extent,
            cx + vx * extent,
            cy + vy * extent,
            roads,
            edges,
            town["points"],
        )

    def add_intersections(offsets: list[int]) -> None:
        for u_offset in offsets:
            for v_offset in offsets:
                x = center_x + u_offset * ux + v_offset * vx
                y = center_y + u_offset * uy + v_offset * vy
                tile_x, tile_y = round(x), round(y)
                if 0 <= tile_x < width and 0 <= tile_y < height:
                    index = tile_y * width + tile_x
                    if terrain[index] != "water":
                        roads.add(index)

    if template == "grid":
        offsets = _town_offsets(template, radius)
        for offset in offsets:
            along_u(offset)
            along_v(offset)
        add_intersections(offsets)
    elif template == "crossroads":
        offsets = _town_offsets(template, radius)
        along_u(0)
        along_v(0)
        for offset in offsets:
            along_u(offset, max(2, radius - 1))
            along_v(offset, max(2, radius - 1))
        add_intersections(offsets)
    else:  # linear main street with short side roads
        along_u(0)
        for offset in (-radius + 1, radius - 1):
            along_v(offset, max(2, radius - 2))


def _road_waypoints(
    recipe: WorldRecipe | None,
    terrain: list[TerrainType],
    width: int,
    height: int,
    start: int,
    goal: int,
    kind: str,
    edge_key: str,
) -> list[int]:
    """Seeded perpendicular via-points so roads bend instead of forming an L grid."""
    if recipe is None:
        return []
    ax, ay = start % width, start // width
    bx, by = goal % width, goal // width
    dx, dy = bx - ax, by - ay
    distance = math.hypot(dx, dy)
    if distance < 4:
        return []
    count = 2 if distance >= ROAD_CURVE_LONG_EDGE else 1
    offset_scale = ROAD_CURVE_OFFSET if kind == "country" else ROAD_CURVE_OFFSET * 0.8
    rng = _stream(recipe, f"road-curve:{edge_key}")
    ux, uy = dx / distance, dy / distance
    waypoints: list[int] = []
    for index in range(count):
        t = (index + 1) / (count + 1)
        offset = (rng.random() - 0.5) * 2 * offset_scale * distance
        for _ in range(8):
            x = round(ax + ux * t * distance - uy * offset)
            y = round(ay + uy * t * distance + ux * offset)
            if 0 <= x < width and 0 <= y < height and terrain[y * width + x] != "water":
                waypoints.append(y * width + x)
                break
            offset *= 0.5
    return waypoints


def _add_path_tiles(roads: set[int], path: list[int], terrain: list[TerrainType], width: int) -> None:
    """Mark path tiles and bridge diagonal steps so the road mask is 4-connected."""
    for first, second in pairwise(path):
        roads.add(first)
        roads.add(second)
        first_x, first_y = first % width, first // width
        second_x, second_y = second % width, second // width
        if first_x == second_x or first_y == second_y:
            continue
        horizontal = first_y * width + second_x
        vertical = second_y * width + first_x
        if terrain[horizontal] != "water":
            roads.add(horizontal)
        elif terrain[vertical] != "water":
            roads.add(vertical)


def _add_road_edge(
    recipe: WorldRecipe | None,
    edge_key: str,
    terrain: list[TerrainType],
    width: int,
    height: int,
    start: int,
    goal: int,
    kind: str,
    roads: set[int],
    edges: list[dict],
) -> bool:
    """Route one land-only edge through seeded via-points; append its vector form."""
    chain = [start, *_road_waypoints(recipe, terrain, width, height, start, goal, kind, edge_key), goal]
    path: list[int] = []
    for first, second in pairwise(chain):
        segment = _astar_tiles_8(terrain, width, height, first, second)
        if segment is None:
            path = []
            break
        path.extend(segment if not path else segment[1:])
    if not path or len(path) < 2:
        return False
    _add_path_tiles(roads, path, terrain, width)
    edges.append({"class": kind, "points": _smooth_road_points(path, width)})
    return True


def _road_coverage(
    terrain: list[TerrainType],
    region_map: list[int],
    regions: list[dict],
    roads: set[int],
    distance: list[int],
    slots: list[GeneratedSlot],
    width: int,
) -> dict:
    """Coverage and per-region access statistics used by the fairness gate."""
    land = [index for index, kind in enumerate(terrain) if kind != "water"]
    within_5 = sum(1 for index in land if 0 <= distance[index] <= ROAD_COVERAGE_RADIUS)
    within_10 = sum(1 for index in land if 0 <= distance[index] <= 10)
    slot_tiles = [slot.tile_y * width + slot.tile_x for slot in slots]
    slot_distance = [distance[index] for index in slot_tiles]
    per_region: dict[str, dict] = {}
    for region_index, region in enumerate(regions):
        tiles = [
            index
            for index, kind in enumerate(terrain)
            if kind != "water" and region_map and region_map[index] == region_index
        ]
        region_slots = [
            slot
            for slot, tile in zip(slots, slot_tiles, strict=True)
            if region_map and region_map[tile] == region_index
        ]
        region_slot_distance = [distance[slot.tile_y * width + slot.tile_x] for slot in region_slots]
        region_within_5 = sum(1 for index in tiles if 0 <= distance[index] <= ROAD_COVERAGE_RADIUS)
        per_region[str(region["id"])] = {
            "land_tiles": len(tiles),
            "road_tiles": sum(1 for index in tiles if index in roads),
            "coverage_within_5": round(region_within_5 / len(tiles), 3) if tiles else 0.0,
            "slots": len(region_slots),
            "max_slot_road_distance": max(region_slot_distance) if region_slot_distance else None,
        }
    return {
        "land_tiles": len(land),
        "road_tiles": len(roads),
        "coverage_within_5": round(within_5 / len(land), 3) if land else 0.0,
        "coverage_within_10": round(within_10 / len(land), 3) if land else 0.0,
        "slots_with_road": sum(1 for value in slot_distance if 0 <= value <= ROAD_SLOT_MAX_DISTANCE),
        "unreachable_slots": sum(1 for value in slot_distance if value < 0),
        "max_slot_road_distance": max(slot_distance) if slot_distance else None,
        "regions": per_region,
    }


def _hub_edges(
    weights: list[list[float]],
    mst: list[tuple[int, int]],
    hubs: list[int],
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """MST plus the cheapest edges that give every region hub degree >= 2."""
    selected = list(mst)
    selected_set = {(min(a, b), max(a, b)) for a, b in selected}
    degrees = [0] * len(weights)
    for a, b in selected:
        degrees[a] += 1
        degrees[b] += 1
    added: list[tuple[int, int]] = []
    for hub in hubs:
        while degrees[hub] < 2:
            candidates = [
                (weights[a][b], a, b)
                for a in range(len(weights))
                for b in range(a + 1, len(weights))
                if (a, b) not in selected_set and (a == hub or b == hub)
            ]
            if not candidates:
                break
            candidates.sort(
                key=lambda item: (0 if item[1] in hubs and item[2] in hubs else 1, item[0], item[1], item[2])
            )
            _weight, a, b = candidates[0]
            selected.append((a, b))
            selected_set.add((a, b))
            added.append((a, b))
            degrees[a] += 1
            degrees[b] += 1
    return selected, added


def _highway_backbone_edges(mst: list[tuple[int, int]], roots: list[int]) -> set[tuple[int, int]]:
    """The MST subtree spanning the region centres: one connected asphalt backbone."""
    if len(roots) < 2:
        return set()
    adjacency: dict[int, list[int]] = {}
    for a, b in mst:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    parent: dict[int, int] = {roots[0]: -1}
    stack = [roots[0]]
    while stack:
        node = stack.pop()
        for neighbor in adjacency.get(node, []):
            if neighbor not in parent:
                parent[neighbor] = node
                stack.append(neighbor)
    edges: set[tuple[int, int]] = set()
    for root in roots[1:]:
        node = root
        while node in parent and parent[node] != -1:
            upstream = parent[node]
            edges.add((min(node, upstream), max(node, upstream)))
            node = upstream
    return edges


def _highway_components(edges: set[tuple[int, int]], count: int) -> int:
    """Number of connected components in the highway node graph."""
    if not edges:
        return 0
    adjacency: dict[int, list[int]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    seen: set[int] = set()
    components = 0
    for start in range(count):
        if start in seen or start not in adjacency:
            continue
        components += 1
        stack = [start]
        seen.add(start)
        while stack:
            node = stack.pop()
            for neighbor in adjacency.get(node, []):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
    return components


def generate_road_graph(
    recipe: WorldRecipe,
    terrain: list[TerrainType],
    anchors: list[dict],
    region_map: list[int] | None = None,
    regions: list[dict] | None = None,
    slots: list[GeneratedSlot] | None = None,
    towns: list[dict] | None = None,
) -> tuple[list[int], list[dict], dict]:
    """Fair road graph: connected hub backbone, country spurs, and vector edges.

    Lakes are hard obstacles. The flood-filled ``roads`` mask is derived from the routed
    paths for gameplay; ``road_edges`` is the display source of truth: smoothed float
    polylines with a class on each edge.
    """
    width, height = recipe.config.width, recipe.config.height
    nodes = [(int(anchor["tile_x"]), int(anchor["tile_y"])) for anchor in anchors]
    if len(nodes) < 2:
        return [], [], {}
    count = len(nodes)
    weights = [[0.0] * count for _ in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            i_idx = nodes[i][1] * width + nodes[i][0]
            j_idx = nodes[j][1] * width + nodes[j][0]
            weights[i][j] = weights[j][i] = _sample_line_cost(terrain, width, height, i_idx, j_idx)

    mst = _prim_mst(weights)
    hubs = [index for index, anchor in enumerate(anchors) if anchor.get("kind") == "region"]
    selected, added_hub_edges = _hub_edges(weights, mst, hubs)
    selected_set = {(min(a, b), max(a, b)) for a, b in selected}
    non_mst = sorted(
        (weights[a][b], a, b) for a in range(count) for b in range(a + 1, count) if (a, b) not in selected_set
    )
    extra_count = max(1, round(len(mst) * ROAD_EXTRA_EDGE_RATIO))
    for _weight, a, b in non_mst[:extra_count]:
        selected.append((a, b))
        selected_set.add((a, b))

    highway_edges = _highway_backbone_edges(mst, hubs)
    highway_edges.update(added_hub_edges)
    for a, b in selected:
        if a in hubs and b in hubs:
            highway_edges.add((a, b))

    roads: set[int] = set()
    edges: list[dict] = []
    for a, b in selected:
        start = nodes[a][1] * width + nodes[a][0]
        goal = nodes[b][1] * width + nodes[b][0]
        _add_road_edge(
            recipe,
            f"edge:{a}:{b}",
            terrain,
            width,
            height,
            start,
            goal,
            "highway" if (min(a, b), max(a, b)) in highway_edges else "country",
            roads,
            edges,
        )

    for town in towns or []:
        _add_town_streets(town, terrain, width, height, roads, edges)

    if not roads:
        return [], edges, {}

    if slots:
        for _ in range(2):
            distance = _road_distance_map(roads, terrain, width, height)
            changed = False
            for slot in slots:
                start = slot.tile_y * width + slot.tile_x
                if 0 <= distance[start] <= ROAD_SLOT_MAX_DISTANCE:
                    continue
                goal = _nearest_road_tile(start, roads, width)
                changed = (
                    _add_road_edge(
                        recipe,
                        f"slot:{slot.slot_index}:{goal}",
                        terrain,
                        width,
                        height,
                        start,
                        goal,
                        "country",
                        roads,
                        edges,
                    )
                    or changed
                )
            if not changed:
                break

    if slots and regions and region_map:
        for _ in range(ROAD_COVERAGE_EDGE_LIMIT):
            distance = _road_distance_map(roads, terrain, width, height)
            stats = _road_coverage(terrain, region_map, regions, roads, distance, slots, width)
            if stats["coverage_within_5"] >= ROAD_COVERAGE_TARGET:
                break
            region_index = min(
                range(len(regions)),
                key=lambda index: stats["regions"][str(regions[index]["id"])]["coverage_within_5"],
            )
            candidates = [
                index
                for index, kind in enumerate(terrain)
                if kind != "water" and region_map[index] == region_index and distance[index] >= 0
            ]
            if not candidates:
                break
            start = max(candidates, key=lambda index: (distance[index], -index))
            goal = _nearest_road_tile(start, roads, width)
            if not _add_road_edge(
                recipe, f"coverage:{start}:{goal}", terrain, width, height, start, goal, "country", roads, edges
            ):
                break

    distance = _road_distance_map(roads, terrain, width, height)
    coverage = _road_coverage(terrain, region_map or [], regions or [], roads, distance, slots or [], width)
    degrees = [0] * count
    for a, b in selected:
        degrees[a] += 1
        degrees[b] += 1
    coverage.update(
        {
            "edges": len(edges),
            "highway_edges": sum(1 for edge in edges if edge["class"] == "highway"),
            "country_edges": sum(1 for edge in edges if edge["class"] == "country"),
            "town_edges": sum(1 for edge in edges if edge["class"] == "town"),
            "access_edges": sum(1 for edge in edges if edge["class"] == "access"),
            "highway_components": _highway_components(highway_edges, count),
            "hub_degrees": {str(anchors[index]["id"]): degrees[index] for index in hubs},
        }
    )
    return sorted(roads), edges, coverage


def generate_road_mask(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[int]:
    """A flat, sorted tile-index list of roads spanning deterministic in-recipe junctions."""
    return sorted({tile for path in generate_road_paths(recipe, terrain) for tile in path})


def generate_road_paths(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[list[int]]:
    """A* centreline paths for the span between deterministic in-recipe junctions.

    Junctions come from the ``roads:junctions`` stream; spanning order is a Prim MST weighted
    by straight-line sampled terrain cost; each edge is routed with 4-connected A* at
    ROAD_COST, detouring around water (no bridge tiles). Unroutable edges are skipped, never
    raised. The flat mask stays authoritative; these paths exist for smooth rendering.
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

    paths: list[list[int]] = []
    for a, b in _prim_mst(weights):
        path = _astar_tiles(terrain, width, height, junctions[a], junctions[b])
        if path is not None:
            paths.append(path)
    return paths


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


def _astar_tiles(
    terrain: list[TerrainType],
    width: int,
    height: int,
    start: int,
    goal: int,
    *,
    water_cost: float | None = None,
) -> list[int] | None:
    """4-connected A* at ROAD_COST; water is impassable unless a ``water_cost`` is supplied."""
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
                if water_cost is None:
                    continue
                tile_cost = water_cost
            tentative = g_score[current] + tile_cost
            if tentative < g_score[neighbor]:
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                heapq.heappush(heap, (tentative + _manhattan_cost(neighbor, goal, width, _ROAD_MIN_COST), neighbor))
    return None


def _astar_tiles_8(
    terrain: list[TerrainType],
    width: int,
    height: int,
    start: int,
    goal: int,
) -> list[int] | None:
    """8-connected A* for v3 roads; water is impassable and corners stay uncut.

    Four-connected routing makes every inter-anchor road an L staircase. Diagonal moves
    with octile distance produce the gentle, non-grid geometry the vector renderer needs.
    """
    if start == goal:
        return [start]
    size = width * height
    g_score = [math.inf] * size
    came_from = [-1] * size
    closed = [False] * size
    g_score[start] = 0.0
    heap: list[tuple[float, int]] = [(0.0, start)]
    diagonal_cost = math.sqrt(2)
    while heap:
        _, current = heapq.heappop(heap)
        if current == goal:
            return _reconstruct_tiles(came_from, goal)
        if closed[current]:
            continue
        closed[current] = True
        cx, cy = current % width, current // width
        for dx, dy in (*_ORTHO, (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbor = ny * width + nx
            if terrain[neighbor] == "water":
                continue
            if dx != 0 and dy != 0 and (terrain[cy * width + nx] == "water" or terrain[ny * width + cx] == "water"):
                continue
            step = diagonal_cost if dx != 0 and dy != 0 else 1.0
            tentative = g_score[current] + step
            if tentative < g_score[neighbor]:
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                goal_x, goal_y = goal % width, goal // width
                adx, ady = abs(goal_x - nx), abs(goal_y - ny)
                heuristic = (adx + ady) + (diagonal_cost - 2) * min(adx, ady)
                heapq.heappush(heap, (tentative + heuristic, neighbor))
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

    v3 assigns regions first, classifies terrain per region, guarantees land under the fixed
    vault grid, then derives slots from that grid. v2 skips every region step, so its terrain,
    slots, masks, fingerprint and checksum stay byte-identical.
    """
    is_v3 = recipe.generator_version >= MAP_V3_GENERATOR_VERSION
    regions: list[dict] = []
    region_map: list[int] = []
    if is_v3:
        regions, region_map = generate_regions(recipe)
    terrain = generate_terrain(recipe, region_map if is_v3 else None)
    road_anchors: list[dict] = []
    road_edges: list[dict] = []
    roads: list[int] = []
    towns: list[dict] = []
    if is_v3:
        # Lakes only: river tracing and crossings are deliberately deferred. Terrain water
        # remains the single water feature, and roads treat it as a hard obstacle.
        rivers: list[int] = []
        _ensure_slot_land(terrain, recipe.config.width, recipe.config.height)
        _connect_slots(terrain, recipe.config.width, recipe.config.height)
        road_anchors = generate_road_anchors(recipe, terrain, regions)
        towns = generate_towns(recipe, terrain, road_anchors, regions)
        slots = generate_slots(recipe, terrain)
        roads, road_edges, road_validation = generate_road_graph(
            recipe, terrain, road_anchors, region_map, regions, slots, towns
        )
    else:
        rivers = generate_rivers(recipe, terrain)
        roads = generate_road_mask(recipe, terrain)
        slots = generate_slots(recipe, terrain)
        road_validation = {}
    validation = (
        build_validation(regions, region_map, terrain, recipe.config.width, recipe.config.height) if is_v3 else {}
    )
    if road_validation:
        validation["roads"] = road_validation
    return GeneratedWorld(
        recipe_fingerprint=recipe.fingerprint(),
        generator_version=recipe.generator_version,
        width=recipe.config.width,
        height=recipe.config.height,
        terrain=terrain,
        slots=slots,
        roads=roads,
        rivers=rivers,
        road_edges=road_edges,
        road_anchors=road_anchors,
        towns=towns,
        regions=regions,
        region_map=region_map,
        validation=validation,
    )


def canonical_payload(world: GeneratedWorld) -> str:
    """Canonical JSON of the world payload (sorted keys, fixed separators, no spaces).

    Required so the snapshot checksum is stable: "byte-identical" needs canonical
    serialization and defined numeric precision (coordinates are already rounded to
    4 dp in ``generate_slots``), not just a seeded PRNG.
    """
    payload = {
        "terrain": list(world.terrain),
        "slots": [asdict(slot) for slot in world.slots],
        "roads": list(world.roads),
        "rivers": list(world.rivers),
    }
    if world.regions:
        payload["regions"] = list(world.regions)
    if world.region_map:
        payload["region_map"] = list(world.region_map)
    if world.validation:
        payload["validation"] = world.validation
    if world.road_edges:
        payload["road_edges"] = [dict(edge) for edge in world.road_edges]
    if world.road_anchors:
        payload["road_anchors"] = [dict(anchor) for anchor in world.road_anchors]
    if world.towns:
        payload["towns"] = [dict(town) for town in world.towns]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def snapshot_checksum(world: GeneratedWorld) -> str:
    """Stable checksum of the canonical snapshot payload."""
    return hashlib.blake2b(canonical_payload(world).encode("utf-8"), digest_size=16).hexdigest()
