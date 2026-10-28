# World Map v3 — regions, authored places, roads and bridges

Status: **steps 0–1 complete 2026-10-28**. Step 2 (regions) is next.

Implemented so far: this contract; additive migration `b7c9e1f3a5d2` for the v3 payload columns
(empty defaults, no backfill); `FEATURE_MAP_V3` (default off) exposed through
`GET /system/features` and the frontend feature-flags store. No generator behavior changed; v2
production remains byte-identical.

Supersedes the stale parts of [`WORLD_GENERATION_CONTRACT.md`](WORLD_GENERATION_CONTRACT.md)
that describe rivers as deferred, roads as non-authoritative decoration, and slots as the only
generated placement source. The contract’s determinism rules still apply.

## Direction

The map is a **region-layered, authored-first hybrid** on the backend-owned world snapshot:

```
WorldBlueprint (authored JSON, versioned)
   regions[]   → named areas + biome profile + boundary
   places[]    → authored POI anchors (type, name, region, position)
   corridors[] → optional authored road/river polylines
        │
        ▼
Generator v3 (procedural fill for everything not authored)
   region field → terrain → hydrology → roads + bridges → places → slots → validation
        │
        ▼
Snapshot v3 (one row per world/version/seed)
        │
        ▼
Production map (flag-gated) + /dev/map-lab inspector
```

Anything authored wins; the generator fills the rest. A fully handcrafted map is therefore just a
blueprint that authors all three layers, with the same pipeline still producing terrain and slots.

## Decisions

| # | Decision |
|---|---|
| A | The fixed shared 10×10 vault-slot grid is canonical. Terrain must guarantee land at every slot tile plus a dry margin. The snapshot’s `slots` is derived from that grid, not a second placement system. |
| B | Roads may cross water only as **bridge tiles**. Bridges are persisted, rendered distinctly, and traversable. Detour-only is not enough for the reference map. |
| C | Road mechanics are phased: first dispatch A* on the shared cost field + road speed for free roam; later unify free roam onto routes. |
| D | Places are generated into the snapshot from a deterministic pool, with authored anchors first and procedural fill later. The place registry syncs from the snapshot. |
| E | Dev regeneration is dev-only. Previews are ephemeral by default; pinning a preview to a persisted row is an explicit action. Production keeps one canonical world per version. |
| F | Biome blending is a rendering control (`3×3`, `5×5`, bilinear), not part of the snapshot. |

## Snapshot v3

Additive fields on `worldsnapshot`; every field has a legitimate empty default so v2 rows stay
readable and pinned explorations keep resolving.

| Field | Type | Meaning |
|---|---|---|
| `regions` | JSONB `[]` | Resolved region specs: id, name, order, biome profile, palette, danger |
| `region_map` | JSONB `[]` | Per-tile region id, row-major over `width × height` |
| `bridges` | JSONB `[]` | Flat sorted bridge tile indices (subset of `roads` crossings) |
| `places` | JSONB `[]` | Resolved POIs: id, name, type/group, region, coordinates, authored flag |
| `validation` | JSONB `{}` | Reachable slots, isolated regions, per-region site counts, road connectivity |
| `blueprint` | JSONB `{}` | Authored input used for this world (empty for procedural worlds) |
| `blueprint_hash` | string | Canonical hash of `blueprint`, empty when unauthored |
| `blueprint_version` | int | Authored content version, `0` when unauthored |

Versioning rules:

- `GENERATOR_VERSION` versions the snapshot payload/schema (v3 = 3).
- `SEED_EPOCH` versions geography. Region-aware terrain intentionally changes geography, so v3
  starts at epoch 2 while v2 rows remain pinned and readable.
- `blueprint_version` versions authored content independently; any authored change bumps it and the
  hash, producing a new snapshot identity.
- Existing rows are never rewritten. There is no backfill: empty defaults mean “v2 world / no
  authored layer”, which is a legal state for readers.

Feature flag:

- `FEATURE_MAP_V3` (default **off**) selects the v3 recipe in the backend. It is exposed through
  `GET /system/features` so the client can hide v3-only UI.
- With the flag off, production serves the current v2 snapshot byte-identically.
- `/dev/map-lab` always previews v3 regardless of the flag.

## Generation pipeline

1. **Blueprint load** — validate authored regions/places/corridors; empty is legal.
2. **Region field** — seeded centers plus fBm domain warp (warped Voronoi); authored polygons
   override. Each tile gets a stable region id.
3. **Terrain** — per-region biome profiles (terrain weights/quantiles), blended across region
   borders. Terrain is generated once and never mutated afterwards.
4. **Hydrology** — region-aware lakes and rivers; rivers remain display-only geometry unless a
   bridge/road crosses them.
5. **Roads** — region-aware junctions, inter-region corridors, Prim MST spanning, A* routing at the
   shared travel cost. Water is crossable only as recorded bridge tiles.
6. **Places** — authored anchors first, then procedural fill (land, spacing, near roads), typed by
   region.
7. **Slots** — fixed shared grid, land guaranteed, mutual reachability validated.
8. **Validation** — the same cost/traversal rules movement will use.
9. **Persist** — fingerprint, checksum, version, blueprint hash.

### Shared cost model

One function owns traversal semantics for generation, validation and movement:

```
step_cost(tile) = TRAVEL_COST[terrain] × (road ? ROAD_MULTIPLIER : 1)
                  water: impassable unless the tile is a bridge
                  bridge: traversable at TRAVEL_COST[road/bridge]
```

`TRAVEL_COST` is currently used only by generation; v3 makes it the movement authority too.

## Authored content

`WorldBlueprint` is JSON stored verbatim in the snapshot (plus a canonical hash):

- **Places first** (lowest cost, highest value): 20–30 named POIs with type, region and position.
- **Region polygons next**: replace generated borders where the authored shape matters.
- **Corridors last**: authored highways/rivers where specific bridges/landmarks are required.

The procedural path never requires authored content; a world with `blueprint = {}` is valid.

## Phases

| Step | Scope | Acceptance |
|---|---|---|
| **0. Contract** | This document; reconcile the old contract’s deferred/non-authoritative wording. | Agreed, no behavior change |
| **1. Skeleton** | Additive migration for v3 columns; `FEATURE_MAP_V3` in config, `/system/features`, frontend store and generated types. No generator change. | Flag off = v2 production identical; single Alembic head; defaults empty; tests |
| **2. Regions** | `RegionSpec` config (start with 4), warped-Voronoi `region_map`, region-biased terrain, persistence, validation. | 4 deterministic non-empty regions, per-region terrain mix within profile, v2 still served off |
| **3. Dev lab** | `/dev/map-lab`: seed/config, ephemeral regenerate, layer toggles (terrain, regions, slots, roads, rivers, bridges, places, grid, origin, route), counts, validation, biome blend. | Iterate a world without touching production |
| **4. Authored places** | Blueprint schema + 20–30 anchors; place validation; registry sync. | Authored POIs appear in the lab and production map |
| **5. Bridges** | Bridge-aware A*, persisted/renderable/traversable bridge tiles. | Roads cross rivers; bridges visible and walkable |
| **6. Mechanics** | Shared cost field; dispatch A* route + ETA; free-roam road speed; tests. | Roads measurably change arrival times |
| **7. Rollout** | Enable the flag, docs, retire the dual slot model and display-only wording. | v3 default, v2 retained for pinned runs |

Steps 1–3 are the first milestone: v3 exists and is inspectable in dev while production is
untouched.

## Validation report

The reference prototype’s panel becomes persisted/generated data, not a client-side mock:

- reachable vault slots / total
- slots with nearby scavenge
- isolated regions
- valuable sites per region
- road network connectivity and bridge count
- place counts per region

## Non-goals (for now)

- Runtime world mutation; worlds stay generated-once and versioned.
- Server-side route finding for every free-roam tick (phase 6 decides the final model).
- Editing authored content through the game UI (blueprints are files in phase 4).
- Changing the vault-slot grid or moving existing vaults.
