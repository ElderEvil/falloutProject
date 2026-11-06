# World Generation Contract (backend-owned)

> **Status:** contract for the backend-owned world generation slice. This is the source of
> truth the backend generator, snapshot persistence, API, and the production renderer all
> consume. Supersedes the frontend export-table direction. No implementation is authorized
> by this document alone; it locks the recipe and interfaces first.

Supersedes, where they conflict: the frontend-owned generation in
[`PROTOTYPE_TO_PRODUCTION_PORT.md`](PROTOTYPE_TO_PRODUCTION_PORT.md) and the land-safe-slot
"Option C" export-table idea. Related: [`EXPEDITION_MAP_CONTRACT.md`](EXPEDITION_MAP_CONTRACT.md),
[`MAP.md`](MAP.md), [`TILE_MAP_INTEGRATION.md`](TILE_MAP_INTEGRATION.md).

## Why backend-owned

The frontend owns a ~2,200-line TS generator with no Python equivalent, so the backend cannot
know terrain. Land-safe slots, one coordinate source for markers/home/dispatch, and occupancy-
independent geography all require the backend to own the recipe. This slice replaces
frontend-owned geography with a small Python core — **not** a line-by-line port; the existing
TS generator stays as a reference and is retired only once production renders the backend world.

### Road-layer addendum (2026-11-06)

The approved [road design](MAP_ROADS_DESIGN.md) adds background highways and country
roads to this same persisted world. This supersedes the original road omission below.
The base `generator_version`, recipe fingerprint, and terrain/slots checksum retain
their existing meanings: changing that version would reseed terrain and slots.

`WorldSnapshot.roads` is one nullable JSONB payload with its own recipe `version`,
`base_checksum`, content `checksum`, and registry-coordinate centerline `segments`.
Geometry, including smoothing and water clearance for the casing, is backend-owned.
The frontend scales and clips it under fog in the existing SVG map. Occupancy,
discoveries, and player identities never enter the road recipe. Roads do not affect
travel or ETA, and remain quiet, non-interactive cartography.

New snapshots include roads in their initial write. Existing rows remain explicitly
unpopulated (`NULL`) after the schema migration until `uv run fo-cli backfill world-roads`
is run from `backend/`. That idempotent operation locks the current v1 row and commits
the entire road payload once; reads never backfill existing worlds. It preserves all
base geometry and leaves other world versions alone. No world reset or activation
catalog is introduced. Heightmaps remain deferred.

Road recipe v2 adds more local roads, broader curves through displaced control points,
and a sparse railroad trunk/feeder. Railroads use `kind: "railroad"` in the same
payload; their junctions and geometry are independent of road intersections. An
explicit `world-roads --upgrade` replaces an older recipe under the same row lock.
Same-version runs are no-ops, and mismatched bases or newer recipes are rejected.
The rail layer is cartography only, with no train service, stations or travel bonus.

## 1. World contract

### Identity and versioning

- **`world_id`**: stable identifier of one generated world (e.g. `wasteland-atlas`).
- **`generator_version`**: integer bumped on any change that alters output. Same
  `(world_id, generator_version, seed, config)` ⇒ byte-identical terrain and slots.
- A world is generated **once per `generator_version`** and persisted as a snapshot; it is
  never regenerated per request or per vault.

### Recipe (all persisted with the snapshot)

| Field | Meaning |
|---|---|
| `seed` | string seed; the only entropy source besides fixed constants |
| `config` | grid dimensions, sector layout, location/slot counts, spacing, version |
| `anchors` | fixed **public** seed anchors; part of the recipe **fingerprint** (versioning), not inputs to terrain geometry |

### Grid and coordinates

- Tile grid: `width × height` (default **80×80**), integer tiles `[0..width) × [0..height)`.
- **Registry space** stays `0–100` float (the production map's coordinate space).
- **Wire/SVG space** is registry × 1.6 (`0–160`), unchanged.
- **Tile ↔ registry** (single conversion source):
  - `tile → registry: (tile + 0.5) * (100 / width)`
  - `registry → tile: floor(registry / (100 / width))` (clamped)
- Every consumer (slots, home markers, dispatch origin, fog, anchors) uses **one** conversion
  helper. No module re-derives it.

### Terrain

- Reuse the existing categorical terrain set: `wasteland | forest | ruins | hills | water`.
- `water` is impassable; the rest are traversable with per-type cost (costs live in config).
- Terrain is generated from the recipe only — **independent of vault occupancy and per-vault
  discoveries**.

### Slots (stable identities)

- `slot_index`: stable integer id, one per configured slot.
- Each slot resolves to one **land-safe registry coordinate** (see §3).
- A slot is placement, not identity: `Vault.number` remains global identity.

### Public vs private

- The **base-world snapshot** (terrain, roads, slots, public anchors) is public and shared.
- **Private** data — ownership, per-vault discoveries, expedition state — stays in existing
  per-vault tables and is never part of the snapshot.

## 2. Python terrain core

- Deterministic hashing (e.g. `blake2b`/`sha256` of `f"{version}:{seed}:{namespace}"`) — **not**
  Python `hash()` (process-dependent).
- Seeded PRNG (e.g. `random.Random(seed)`) with **separate named streams** (terrain,
  slots, …) and stable iteration order, so adding a stream never shifts another.
- Terrain derives from **seed + config + version only**. Public anchors version the recipe
  (`fingerprint()`) but do not shape geometry — consistent with the map-side decision that
  slots are placement markers on a fixed world, never terrain shapers.
- Small pipeline: value-noise/fBm → quantile terrain classification (water/forest/hills/ruins)
  → slots placed inside the largest traversable component; **no** rendering, icons, prototype
  timers, claims UI, or climate/hydrology. Rivers are **deferred** (no carving pass yet) and
  are intentionally absent from `WorldConfig` rather than carried as dead config.
- Reproducibility is defined by the Python implementation, not TS parity. A divergence is
  absorbed by a new `generator_version`.
- Generation is a pure function of the recipe; the same inputs recompute identically.

## 3. Land-safe slots

Generated **after** terrain, then vaults are assigned.

Required guarantees (each validated, tests added but reported as not run):

1. **Stable** slot indices.
2. **Unique, in-bounds, traversable** positions (never water).
3. **Explicit minimum spacing** between slots (config).
4. **Reachability** under the same traversal rules used for validation.
5. **One coordinate source** for player markers, home markers, and dispatch origins.
6. On placement failure, **fail clearly** — never silently fall back to an unsafe coordinate.

Existing dev vaults: disposable. Prefer an explicit, development-only reset over a relocation
migration (see §6). No deletion happens during implementation without separate execution approval.

## 4. Production map integration

- Expose the snapshot through existing authenticated read APIs / service + CRUD patterns; thin
  endpoints, schemas in `schemas/`, queries in `crud/`.
- The frontend **renders** backend terrain (reusing the existing viewport, selection, icons,
  discovery filtering). It holds **no generation rules**.
- Regenerate frontend API types after API changes; if the backend is unavailable, **report it**
  rather than hand-editing generated types.
- No new prototype route or parallel renderer.

## 5. Explicitly deferred

- Terrain/road-aware production travel.
- Full road-generator port (roads may be omitted or kept as clearly non-authoritative decoration;
  never mix roads from an unrelated TS world with the new terrain).
- Height/moisture/temperature expansion.
- Rendering styles and layer controls.
- Historical trail rewrites; changes to active expedition durations.

## 6. Development-data transition

- Existing vaults are dev data; preservation is not required.
- Provide an explicit **development-only** reset path (scoped; never deletes users or unrelated
  data; normal migrations never unconditionally wipe application data).
- Deletion requires separate execution approval.

## 7. Completion criteria

- Production map renders backend-generated terrain.
- Same recipe ⇒ identical terrain and slots (reproducible).
- Every generated slot satisfies the placement guarantees.
- Vault occupancy changes do not change geography.
- Markers, home positions, and dispatch origins agree (one coordinate source).
- Frontend geography no longer independently determines the world.
- Existing discovery authorization remains intact.
- Validation limitations reported honestly (tests added but not run under the current instruction).

## 8. Delivery order

1. Lock this contract (done).
2. Python terrain core + reproducibility tests.
3. Land-safe slot generation + guarantees.
4. Snapshot persistence + authenticated read API.
5. Frontend renders the backend snapshot; retire superseded TS generation only after parity of
   behavior in production, keeping distinct tests.

## Open decisions (need sign-off)

1. **Snapshot storage:** new `world` table (recipe + version) vs on-disk generated JSON artifact
   loaded/cached. (Recommend a lightweight persisted recipe row + generated snapshot artifact.)
2. **Slot count / grid:** keep 80×80 / 100 slots for this slice? (Recommend yes.)
3. **Roads:** omit for the slice, or keep existing decoration? (Recommend omit — non-authoritative.)
4. **Reset tooling:** `fo-cli` dev command scope (vault slots/home markers/world snapshot only).

Road recipe v3 changes only railway geometry: long land-visible straight runs with
short, roughly 10–15 degree transition steps where bends are needed. Junctions stay
fixed and water clearance still takes precedence. The v2 road seed remains fixed,
so upgrading does not redraw highways or country roads.

Road recipe v4 increases local branches from 30 to 70 and allows their endpoints
within three registry units of the map edge. Spaced endpoints are chosen by distance
from the existing network, filling empty regions first. The highway hub recipe and
rail alignments remain fixed; additional road junctions retain exact shared points.
