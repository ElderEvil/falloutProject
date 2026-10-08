# Map Prototype — Current vs Deferred

Throwaway PoC for a tile-based overworld. Nothing here touches real data or the
production map (`modules/map`). Route `/dev/map-prototype` lives inside the
`import.meta.env.DEV` block in `frontend/src/router/index.ts`, so it is compiled
out of production builds. Run it with `cd frontend && pnpm exec vp dev`, then open
`http://localhost:5174/dev/map-prototype` (port shifts if 5173 is taken).

Files: `worldgen.ts` (pure deterministic generator, no deps), `terrainRegions.ts`
(pure terrain → smoothed region polygons), `fog.ts` (pure fog helpers),
`MapPrototypeView.vue` (canvas view + controls), `tests/unit/views/map-prototype/`
(worldgen + regions + fog suites).

> **Contract:** cross-cutting decisions for the expedition-planning surface — the
> `isVisible()` visibility predicate, road/ETA semantics, verified gaps, and the delivery
> plan — live in
> [`docs/features/EXPEDITION_MAP_CONTRACT.md`](../../../../../docs/features/EXPEDITION_MAP_CONTRACT.md).
> Where the two differ on those topics, the contract wins.

## Current (landed and green)

Generator (`worldgen.ts`):

- 80×80 tiles, 5 terrains (wasteland 1.0, forest 1.15, ruins 1.3, hills 1.5, water impassable).
- 100 vault slots, one per 10×10 sector, snapped off water, spacing-nudged.
- Locations with archetype rules (rockets near junctions, marts near settlements,
  factories on settlement edges, towers on hills, treatment near water, raider camps
  off-road); density tunable 10–600, default 40; no overlaps, none on water/vaults.
- Roads: MST + loop edges with seeded curvature waypoints, junction detection,
  bridges where roads cross water. No forced longest-edge trunks.
- L-bend river (adjacent edges, mirrored endpoints) plus base-field lakes; high water
  costs so roads detour instead of cutting everywhere.
- Routed scavenge guarantee: every vault gets a minor `supply_cache` site
  (Supply Cache / Abandoned House / Wrecked Caravan) within a travel-time budget.
- Validation report: reachability, scavenge coverage, isolated regions, 4×4 valuable
  distribution. Deterministic per seed; vault positions stable across `locationCount`.
- Single `vaultsWithNearbyScavenge` field (duplicate budget field merged).
- One shared `labelComponents` flood-fill for road components, reachability, and
  validation regions (replaced three near-identical BFS loops).

View (`MapPrototypeView.vue`):

- Canvas render as smoothed terrain region polygons: every connected same-terrain
  component is boundary-traced (cell-edge follow), simplified (Douglas–Peucker) and
  rounded (Chaikin), then filled from `TERRAIN_META` over a wasteland base. Rivers and
  lakes are water regions, so they read smooth; no per-tile wash, no blend buffer, no
  stacked blur. Each filled region is stroked with a thin low-alpha darkened outline
  so adjacent similar biomes separate cleanly.
- Roads draw a wide dark casing under a lighter tan fill so they read as cartographic
  lines on both the light wasteland base and the darker biomes; the default density is
  40 locations (dial 10–600) so markers no longer swamp the map.
- Player-icon silhouettes per kind with a debug-markers fallback; grid hidden by default.
- Hover readout (coords/terrain/cost); selection shows name + ETA from origin.
- Click vault → click location draws the A\* route with cost + hours; claim/unclaim button.
- Seed / Random seed / Regenerate, locations control, legends, terrain counts.
- World in a `shallowRef` (replaced wholesale, never mutated).
- Single metadata tables (`TERRAIN_META`, `LOCATION_META` + `locationMeta()`) driving
  colors, legend, costs (from worldgen `TRAVEL_COST`), labels, and icons.
- Fog of war: unexplored dark; origin/claim auto-reveal; "Send expedition" animates a
  dweller along the route revealing sight radius, arrival discovers; blind targeting
  allowed, details unlock on discovery; Reset fog + Show-all (debug).
- Player preview shell (MAP.md): opaque fog with zero marker ghosting, dev controls
  hidden, hit-testing respects fog, routing restricted to known destinations with an
  explicit "No known route" (no path/cost/Send leaked for unknown); dev mode keeps
  blind routing + translucent inspection fog. Discovery via expedition arrival.
- One shared visibility predicate (`isVisible`) enforced across selection, route
  origin/destination, pathfinding, ETA, and marker culling; masked `findPath` keeps
  known-only routes off unexplored cells.
- Known Places list is the keyboard/touch access path (focus + Enter); first pick sets
  the origin, next sets the destination.
- Scout loop (contract DD4): "Scout this frontier" targets a revealed frontier tile and
  shows a **coarse ETA band** (`~low–high h`); the scout probes past the frontier and
  reveals as it walks. Arrival records newly revealed places in a Discoveries log.
- Road travel discount is **on by default in the player loop** (0.7×).
- Atlas treatment (DD6): sparse terrain textures (forest dots, ruin squares, hill
  chevrons), a crisp road casing, and home/selection/hover canvas labels. Zoom-dependent
  detail is deferred — the prototype canvas has no zoom viewport yet.
- DEV Option A increment: explicitly synthetic shared fixtures (`synthetic-public-v1`),
  constraint v1 before placement/roads, exact float marker coordinates, projected cells,
  deterministic lexical-ID co-cell precedence. Existing roads/reachability/scavenge passes
  are reused; per-anchor diagnostics report requested/final terrain, conflicts, reachability.
  Base/anchored controls, conflict scenario, and changed-tile highlighting are developer-only.
  Changes reset local simulation state. Neither unlocked places nor API vault signals
  constrain terrain. Seeded signals use scaled/rounded wire coordinates, so exact public
  registry-anchor compatibility is still unverified.
- This increment was not validated with tests, lint, or typecheck, by user instruction.
  Historical checks below apply only to earlier work; no production changes are included.

Checks: `pnpm run typecheck` clean, `pnpm run lint` clean, full frontend suite green
(220 files, 2428 tests).

### Integration v1 — read-only production overlay (wired, mock-verified)

- `PRODUCTION DATA` card reads `GET /api/v1/map/vault/{id}?unlocked_only=true` via the
  shared session client (no new endpoints, no schema changes). Requires app login;
  unauthenticated calls are blocked client-side with an inline message (no redirect).
- Renders only `is_unlocked` locations as amber diamonds (server filter = authority,
  client re-checks fail-closed); `vault_markers` never enter state.
- Registry→canvas projection is the exact inverse of tile-center mapping; per-vault
  isolation by replacing state on load (no merging).
- Verified: unit tests (projection, filtering), mocked end-to-end (locked hidden,
  markers omitted, vault switch isolates, unauth blocked), typecheck/lint green.
- Live-backend check still open (needs running backend + real login; no fake sessions).

## Deferred / proposed (not started)

Integration with existing be/fe (pivot — do not duplicate prod; define the mapping
contract in MAP.md Phase 5 BEFORE touching prod code/DB; no silent substitution):

- Viewport (pan/zoom/touch/keyboard) → reuse production `useMapZoomPan` + SVG
  `WorldMap`. Dropped from prototype plan entirely; the **prototype stays zoom-less**
  (decision 2026-10-02). Production owns navigation/readability at zoom; `useMapZoomPan`
  reuse is an SVG→Canvas adaptation (hit-testing, icon sizing), not drop-in. Minor-cache
  density is inspected with a dev toggle, not zoom.
- Markers/selection/detail UI → adapt production components/modal/selection patterns.
- Map data + discovery state → wire `map_service` / `WorldLocation` /
  `VaultLocationState` / Journal. Prototype mask stays presentation-only.
- Expedition dispatch/travel → wire production exploration endpoints +
  `dispatch_travel_hours`. Prototype timer stays a mock.
- Legends/stats presentation → follow production patterns.
- Open mapping decisions (must lock first): tile↔registry coordinates, vault-slot
  identity vs real vaults, fog authority (server source of truth), travel semantics
  (authoritative vs illustrative ETA — resurrects the road-discount question),
  road persistence, new-enum migrations, endpoint auth, frontend surface
  (extend prod SVG vs dev canvas on prod APIs vs fo-cli).

Render direction — pick one before reworking visuals:

- Heightmap layer (hillshaded elevation + crisp vector water). Best fix for terrain
  legibility and banding; needs one additive elevation export from the generator.
- CRT topology style (monochrome contours/scanlines). Most on-theme; less of a
  realistic map.
- Icon sprites / offscreen pre-rendering (review #1). Do after the render locks,
  not before — avoids reworking icons twice.
- Layered canvas / rAF batching (review #6). Only with measured hover jank; none seen.

Code health — the rest landed (see Current):

- Road travel discount (review #3): implemented as an **opt-in prototype experiment**
  (`ROAD_TRAVEL_DISCOUNT = 0.7`, "Road discount (experiment)" toggle in LAYERS). Measured
  across 5 seeds / 600 journeys: route choice changed in 96.0% of cases, average ETA
  −12.6%. Technically clears the contract's DD3 bar; the keep-or-remove product call is
  still open. See `docs/features/EXPEDITION_MAP_CONTRACT.md` DD3.

Product map (`modules/map`, real-user code — out of this spike, backlog separately):

- Single selection owner, unified refresh with in-flight guard, one countdown clock,
  stable vault IDs.

Later decisions:

- Python port / server-authoritative generator (the original endgame question).
- Location density default (currently 40; dial 10–600 to taste).

## Tried and reverted (do not redo without new evidence)

- Forced longest-edge trunk routes → laser-straight diagonals. Removed.
- Pre-placed bridge plugs + cross-river waypointing → plugs were islands (3×3 in wider
  water) that severed without sharing; deleted in favor of an L-river roads can detour around.
- Fully splitting river (opposite edges) → forced many bridges and fragmentation.
  Now an L-bend (adjacent edges) so land stays connected around its ends.
- Vault access paths → invisible (never drawn) and redundant with reachability repair;
  deleted outright.
- Smooth blur stacked on biome blend → mud. Removed; blending later replaced by
  smoothed region polygons (see Current), which also removed the tile-block wash.
- 200-location default → clutter; dialed down (100, then 40 for legibility) with the guarantee as backstop.
- Base-field lake removal → user wants lakes; restored. Water is river + a couple of lakes.
- Displayed-value drift (legend vs hover rounding) → fixed by exact cost labels.

## Known contract gaps (fix before adding visual features)

The player-fog contract below is stronger than the current implementation enforces. All
verified in `MapPrototypeView.vue`; the fix is one shared visibility predicate, not
per-consumer checks. See `EXPEDITION_MAP_CONTRACT.md`:

- `:1096` — fog is paint-only (drawn after markers), so it culls nothing; no shared
  visibility rule feeds selection, routing, ETA, or detail.
- `:873` — click resolves hidden vaults/locations before a visibility check; a hidden
  location becomes `selectedLocation`, a hidden vault sets `routeStart` (origin gated in
  player mode, destination not).
- `:905` — player routing checks the destination is explored, but `findPath()` still
  searches the full terrain, so a known destination can route through unknown cells.
- `:682` — the selected-location ETA independently uses full-world pathfinding.
- `:1200` — canvas input is mouse-only; needs a known-location list or keyboard/touch path.

## Measurements

Terrain-composition baseline (scratch diagnostic: seeds `vault-111`, `alpha`, `beta`,
`gamma`, `delta`, `epsilon`; default 80×80, `locationCount` 100; settings unchanged):

- Generation time 19–69 ms.
- Composition: wasteland ~55–60%, ruins ~11–15%, hills ~15–17%, water ~4–7%.
- Components: water 3–5 (largest 89–171), hills 2–5 (356–962), ruins 2–4 (347–717).
- Reachability 100/100 across all six seeds.

The scratch test asserted nothing and printed `scavenge=undefined` (it referenced a removed
`vaultsWithinScavengeBudget` field), so it was deleted after recording this. The permanent
suite retains generation, reachability, and scavenge assertions.

Road-discount comparison (5 seeds × 120 origin→target pairs = 600 journeys):

- Enabling the 0.7× discount changed the chosen route in 96.0% of cases (cost changed
  99.2%, average ETA −12.6%). See `docs/features/EXPEDITION_MAP_CONTRACT.md` DD3.

## Open questions

- Render direction (heightmap vs CRT vs current canvas) — blocks any visual rework.
- Whether roads should discount travel by default (measured: changes 96% of route
  choices) — keep-or-remove call pending; blocks freezing the ETA.
- Density default (40 after the legibility polish) and forest share — tune by looking,
  not by theory.
- Fog tuning (origin/claim/sight radii, expedition speed, blind targeting, re-fogging?)
  and whether fog should ever lift permanently once real dwellers exist.
- Live-backend verification of the prod overlay (real login + own vault): unlocked render,
  locked hidden, vault switch isolates. (Mocked proof done; live needs credentials/session.)
