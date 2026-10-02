"""Backend-owned world generation core (pure, deterministic, framework-free).

This is the Python replacement for frontend-owned geography: a small generator that
produces terrain and land-safe vault slots from an explicit recipe. It does **not**
attempt TypeScript parity — reproducibility is defined by this implementation and any
output change bumps ``GENERATOR_VERSION``.

Design rules (see docs/features/WORLD_GENERATION_CONTRACT.md):
- Deterministic hashing (blake2b), never Python's process-dependent ``hash()``.
- One seeded PRNG per named stream, stable call order, so adding a stream never
  shifts another.
- Terrain depends only on the recipe (seed + config + version + public anchors),
  never on vault occupancy or discoveries.
- Generation is a pure function: same recipe -> identical output.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from random import Random
from typing import Literal

# ── Contract constants ──────────────────────────────────────────────────

GENERATOR_VERSION = 1
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
    river_count: int = 1
    river_width: int = 3


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
            f"{c.noise_gain}:{c.water_quantile}:{c.hills_quantile}:{c.river_count}:{c.river_width}"
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
    """The generated snapshot (terrain + slots + fingerprint)."""

    recipe_fingerprint: str
    generator_version: int
    width: int
    height: int
    terrain: list[TerrainType]
    slots: list[GeneratedSlot]


# ── Deterministic primitives ────────────────────────────────────────────


def _hash(*parts: str) -> str:
    """Stable hash of joined parts; never Python hash() (process-dependent)."""
    digest = hashlib.blake2b("\x1f".join(parts).encode("utf-8"), digest_size=16)
    return digest.hexdigest()


def _stream(recipe: WorldRecipe, namespace: str) -> Random:
    """Independent seeded PRNG per named stream, stable across recipe versions."""
    seed_bytes = _hash(str(recipe.generator_version), recipe.seed, namespace)
    return Random(int(seed_bytes, 16))


# ── Noise (value noise + fBm) ───────────────────────────────────────────


def _value_noise_field(width: int, height: int, rng: Random, octaves: int, frequency: float, lacunarity: float, gain: float) -> list[float]:
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
        cfg.width, cfg.height, _stream(recipe, "terrain:base"),
        cfg.noise_octaves, cfg.noise_frequency, cfg.noise_lacunarity, cfg.noise_gain,
    )
    ruins = _value_noise_field(
        cfg.width, cfg.height, _stream(recipe, "terrain:ruins"),
        cfg.noise_octaves, cfg.noise_frequency, cfg.noise_lacunarity, cfg.noise_gain,
    )
    water_cut = _quantile(base, cfg.water_quantile)
    hills_cut = _quantile(base, 1 - cfg.hills_quantile)
    ruins_cut = _quantile(ruins, 1 - cfg.hills_quantile)

    terrain: list[TerrainType] = ["wasteland"] * n
    for i in range(n):
        if base[i] <= water_cut:
            terrain[i] = "water"
        elif base[i] >= hills_cut:
            terrain[i] = "hills"
        elif ruins[i] >= ruins_cut:
            terrain[i] = "ruins"
        else:
            terrain[i] = "wasteland"
    return terrain


# ── Slots (land-safe) ───────────────────────────────────────────────────


def _is_traversable(terrain: list[TerrainType], width: int, x: int, y: int) -> bool:
    return TRAVEL_COST[terrain[y * width + x]] != math.inf


def generate_slots(recipe: WorldRecipe, terrain: list[TerrainType]) -> list[GeneratedSlot]:
    """Assign slots to unique, traversable, spaced tile positions.

    Fails clearly (``RuntimeError``) when the recipe cannot place all slots rather
    than falling back to an unsafe coordinate.
    """
    cfg = recipe.config
    width, height = cfg.width, cfg.height
    rng = _stream(recipe, "slots")

    land = [(x, y) for y in range(height) for x in range(width) if _is_traversable(terrain, width, x, y)]
    if len(land) < cfg.slot_count:
        raise RuntimeError(f"terrain has {len(land)} traversable cells, fewer than {cfg.slot_count} slots")

    rng.shuffle(land)
    chosen: list[tuple[int, int]] = []
    spacing_sq = cfg.slot_min_spacing * cfg.slot_min_spacing
    for (x, y) in land:
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


def generate_world(recipe: WorldRecipe) -> GeneratedWorld:
    """Generate the full snapshot for a recipe (pure; no occupancy, no discoveries)."""
    terrain = generate_terrain(recipe)
    slots = generate_slots(recipe, terrain)
    return GeneratedWorld(
        recipe_fingerprint=recipe.fingerprint(),
        generator_version=recipe.generator_version,
        width=recipe.config.width,
        height=recipe.config.height,
        terrain=terrain,
        slots=slots,
    )


def canonical_payload(world: GeneratedWorld) -> str:
    """Canonical JSON of terrain + slots (sorted keys, fixed separators, no spaces).

    Required so the snapshot checksum is stable: "byte-identical" needs canonical
    serialization and defined numeric precision (coordinates are already rounded to
    4 dp in ``generate_slots``), not just a seeded PRNG.
    """
    return json.dumps(
        {
            "terrain": list(world.terrain),
            "slots": [asdict(slot) for slot in world.slots],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def snapshot_checksum(world: GeneratedWorld) -> str:
    """Stable checksum of the canonical snapshot payload."""
    return hashlib.blake2b(canonical_payload(world).encode("utf-8"), digest_size=16).hexdigest()
