# Prototype → Production Port (decision A)

> **Direction chosen 2026-10-02:** consolidate the tile prototype's value into the
> production map (`frontend/src/modules/map/`, route `/vault/:id/map`) and retire
> `/dev/map-prototype` **gradually** — feature by feature, never a big-bang rewrite.
>
> Production changes still require explicit maintainer merge approval (repo guardrail #1);
> authoritative travel/terrain stays behind D1–D8. This document supersedes the
> "prototype proves X / production proves Y" split in
> [`PRODUCTION_COMPATIBILITY_PROPOSAL.md`](PRODUCTION_COMPATIBILITY_PROPOSAL.md) where they
> disagree: the prototype is a reference, not a parallel product surface.
>
> **Backend-owned world generation (2026-10-03):** the frontend-owned generation direction is
> superseded by [`WORLD_GENERATION_CONTRACT.md`](WORLD_GENERATION_CONTRACT.md) — the backend
> owns the recipe and generated snapshot; the frontend renders it. That contract lives in the
> Python lane (`world-generation-core` → `world-snapshots`), not here.

## Branch split (current port plan)

The port is extracted from `feat/wasteland-atlas` as a **sequential map stack** plus an
independent Python stack. Each branch is one reviewable slice; later slices are **not**
implemented in earlier branches.

| Branch | Scope | Status in this branch |
| --- | --- | --- |
| `feat/map-interaction` | Interactive production map: presentation, keyboard/touch, marker selection, deep-links, discovery-only visibility | Landed |
| `feat/map-atlas` | Shared TS generator, production terrain rendering, coordinate conversion, derived fog, occupancy-independent geography | **This branch** |
| `feat/map-vault-slots` | Persisted vault slots, player/ownership markers, home placement/travel origins, atomic allocation | Not yet — later slice |
| `feat/map-scouting` | Scouting backend action + production UI | Not yet — later slice |
| `feat/world-generation-core` | Python lane: backend world-generation core | Independent stack |
| `feat/world-snapshots` | Python lane: generated world snapshots | Independent stack |

The DEV prototype (`/dev/map-prototype`, `MapDevDiagnostics.vue`) is **excluded** from every
branch in this stack; no production import points into `core/views/map-prototype`.

## Parity assessment

**Already in production in this branch:**

- Quiet CRT presentation, no grid, bright markers. `AtlasTerrain` renders the shared
  generator's terrain as a Canvas-produced image inside SVG, with SVG road paths.
- Marker labels shown on hover/focus/selection (`MapMarker` `.marker-label`), home marker,
  enlarged transparent hit area.
- Locked-place hint pins (anonymous projection: position shown, identity withheld).
- Keyboard/touch navigation: `useMapZoomPan`, `MarkerListPanel` arrow-key focus.
- Known-location index, unlock toast, Journal/discovery surfacing.
- Discovery-only visibility (`modules/map/utils/visibility.ts`) and derived fog
  (`FogLayer` + `modules/map/utils/fog.ts`) over the shared atlas geography.

**Prototype-only (to port or retire):**

- Local expedition walking/reveal simulation and known-only A\* route previews. Production
  has discovery-derived fog, but not the prototype's persisted/local walking mask.
- Strict frontier targeting + displayed coarse ETA bands. Scout submission is a later slice.
- Authoritative tile travel: roads + 0.7× discount remain prototype experiments. Shared
  generated terrain/roads render in production; backend travel does not consume them.
- Canvas atlas textures/labels are **not** ported; production keeps its SVG viewport.
- Dev read-only overlay (public-anchor diagnostic).

## Historical decisions

- **Visibility / fog contract (2026-10-02, historical):** the discovery-only rule
  (`modules/map/utils/visibility.ts`) landed in `feat/map-interaction`; the derived fog
  (`FogLayer`, `fog.ts`) landed in `feat/map-atlas`. One rule across rendering, index,
  routing/dispatch gating, the unlock toast, and the detail modal. Unknown stays as
  anonymous hints (D7 unchanged). Explored-cell **persistence** (a server-owned mask)
  remains open and gated.
- **Geography stability (2026-10-02, historical):** shared atlas geography is **stable as
  occupancy changes**: production terrain (`AtlasTerrain`) generates from the global seeded
  vault signals only. Player-vault slots are **placement markers on the fixed world**, never
  terrain shapers, so a new vault cannot reshape existing geography for other players.
  `anchorsFromPlayerVaults` / `mergeAnchors` remain available for the DEV diagnostic and any
  preview evaluation. Open: guaranteeing a vault's slot lands on **land** without mutating
  the shared world (a land-aware slot map) — slot persistence is a later slice.
- **Read-only evaluation (implemented 2026-10-02, historical):** a DEV-only diagnostic
  (`core/views/map-prototype/MapDevDiagnostics.vue`, dynamically imported from `MapView`
  behind `import.meta.env.DEV`) evaluated Option A on two worlds through one versioned
  constraint pass. It is **excluded** from this stack; the branches carry no DEV diagnostic.

## Current-state inventory (source inspection, 2026-10-03)

This is a code inventory for the `feat/map-atlas` branch, not a deployment or validation
claim. No tests, lint, typecheck, live session, or database checks were run for this
documentation update.

| Area             | Implemented in this branch                                                                                                                                                                                                                              | Remaining boundary                                                                                                                                                                                                                                                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Generator        | `modules/map/utils/atlasWorldgen.ts` is the shared generator (renamed from the prototype worldgen). Seeded value-noise/fBm fields, quantile terrain classification, L-bend river, MST + loop roads routed with A\*, constraints, reachability repair, and scavenging validation. | Continuous fields are discarded after classification; the returned world has categorical terrain/costs, not elevation/moisture exports. Generated sites/caches are not the authoritative registry.                                                                                                                                        |
| Production atlas | `AtlasTerrain.vue` uses fixed `ATLAS_SEED`, 80×80 tiles, default generator config, and global seeded vault signals. Raster terrain image + vector roads sit in the existing SVG viewport.                                                                | Not backend movement authority; not full registry-anchor compatibility. Player vault occupancy and per-vault unlocks do not shape terrain.                                                                                                                                                                                                |
| Anchors          | `anchorsFromVaultMarkers` converts scaled/rounded wire coordinates to registry units. Constraint v1 sorts IDs lexically and diagnoses invalid/co-cell/downstream conflicts.                                                                              | IDs are currently `seed-vault-${i}` (response-order dependent), not stable registry IDs. Exact public anchor identity/coordinates and a complete world recipe remain open.                                                                                                                                                                |
| Slots            | Not in this branch — `feat/map-vault-slots` (persisted `VaultSlot`, migrations, `utils/vault_slots.py`, ownership markers) is a later slice.                                                                                                             | Slot persistence, land-safe placement, and travel-origin use land in the vault-slots slice.                                                                                                                                                                                                                                              |
| Fog              | Production `FogLayer` derives explored cells from discovery/home/trails; visibility gates known/hint locations.                                                                                                                                          | Presentation mask, not server-owned explored-cell persistence or authorization. Journal trails are not navigation paths.                                                                                                                                                                                                                  |
| Scout            | Not in this branch — the scouting action and production UI land in `feat/map-scouting`.                                                                                                                                                                | Client checks revealed cells, not strict frontier adjacency. Service uses distance → `dispatch_travel_hours` → band upper bound → free-roam `send_dweller`; it does not persist the target or follow an atlas route.                                                                                                                        |
| Dispatch         | Backend uses distance from slot/fallback origin to registry destination and whole-hour `dispatch_travel_hours`.                                                                                                                                          | No terrain/road cost authority. Prototype 0.7× road discount must not silently retune production duration.                                                                                                                                                                                                                                |

## Map sizing for our needs (analysis, 2026-10-03)

**Recommendation: retain 80×80 as the baseline; do not choose 160×160 yet.** The
reported sample supports reviewing capacity and gameplay separately, not an immediate
expansion. This analysis adds no measurements or authorization for terrain/travel changes.

### Source constants versus reported measurements

- **Source-confirmed:** `frontend/src/modules/map/utils/atlasProjection.ts` defines
  `ATLAS_TILES = 80` and `MAP_UNITS = 160`; the latter is the SVG extent, not a 160×160
  tile world. `atlasWorldgen.ts` defaults to 80×80 (6,400 tiles), 10×10 generated vault
  sectors and 100 base locations. Supply caches are additional generated overlays, not
  part of `locationCount`; generated locations are not the authoritative registry.
- **Source-confirmed, separate capacity:** `backend/app/core/game_config.py` defaults
  `VaultSlotConfig` to 100 slots and 10 columns (environment-configurable).
  `backend/app/crud/vault_slot.py` allocates within that count and rejects provisioning
  when no slots remain. This is a binding provisioning limit under the default config,
  independent of terrain tile count; effective deployment config and occupancy were not checked.
- **User-reported, not independently verified here:** 5,960–6,009 land tiles
  (about 93–94%), approximately 133 generated locations including 33 caches, about
  45 land tiles per site, and average land travel cost about 1.14. The land/site ratio
  is an aggregate density estimate, not evidence of even spacing, per-vault accessible
  choices, registry density or sufficient gameplay variety. These are sample results,
  not guarantees across recipes or current production state.

### Travel arithmetic and what it does not establish

`atlasWorldgen.ts` exports `HOURS_PER_COST = 0.5`; `findPath` returns rounded hours
from routed cost. With the reported average cost, an indicative 80-tile straight span
is `80 × 1.14 × 0.5 = 45.6 h`, **not ~14 h**. A diagonal is about
`80 × √2 × 1.14 × 0.5 = 64.5 h` under a uniform-cost Euclidean approximation.
These are scale illustrations, not measured routes, actual maximum journeys or mean ETAs:
cell-center spans, terrain mix, barriers, road discounts and routing change the result.

Backend scout/dispatch timing is separate: `ExplorationService` uses registry-coordinate
Euclidean distance and `dispatch_travel_hours`, which applies configurable base plus
per-unit time, rounds up and clamps to 1–24 h. Source defaults in `DispatchConfig` are
1 h base and 0.1 h per distance unit; scouts then use the coarse band's upper bound.
The prototype arithmetic is therefore **not current backend duration evidence**.

The user-reported ~96% road route-change rate shows sensitivity in the sampled routing
comparison, not that roads change which destinations players select or that travel bands
are narrow. Establish those effects from per-vault destination ETA distributions and
player-facing choices; a route-change percentage alone cannot establish either.

### Resolution, world extent and compatibility

The registry remains normalized to 0–100 and the renderer projects it onto the tile grid
and SVG viewport. More tiles can mean finer sampling of the **same world**, not greater
physical extent. Increasing tile resolution while keeping a fixed hours-per-tile-cost
multiplier can artificially increase ETAs. Define distance scale/world extent and its
conversion to route cost before comparing sizes or adopting authoritative tile timing.

A 160×160 grid would have 25,600 tiles (four times the cells), but is only an evaluation
candidate, not a chosen requirement or a safe config-only change. Review generator scale
constants, projected anchors and slot placement, fog/simulation masks, recipe/version
identity and persistence compatibility. Changing backend slot count/columns can also
change the permutation and projected positions of existing slot indices; extra capacity
must not silently relocate existing vaults. Twice as many vaults does not universally
require twice as many tiles: capacity, spacing, destination density and physical travel
scale are distinct decisions.

### Review triggers and evidence before expansion

- **Proposed planning trigger:** review capacity around 70 occupied slots out of the
  default 100, leaving headroom before provisioning exhaustion. This is not an enforced
  threshold, an existing policy or a claim about current active vaults. Review occupied
  persisted slots and release/allocation behavior, not merely an active-player estimate.
- For representative vault origins, compare reachable destination route ETAs using the
  relevant timing authority: p10, median and p90, plus short/medium/long choice availability.
  Separate prototype route-cost experiments from shipped backend timing and scout bands.
- Agree desired short/medium/long duration targets first; none is specified by this analysis.
  Evaluate progression and whether destination/road choices are meaningful, rather than
  inferring a narrow travel range from map dimensions or average terrain cost.
- Review marker/label density and usability at production screen sizes/zoom levels, and
  generation/rendering/routing performance. More cells alone do not resolve screen crowding
  when the normalized viewport and marker population are unchanged.
- Expand only if this evidence identifies a need that placement, capacity or timing tuning
  cannot address appropriately. Follow the recipe/slot compatibility steps below; terrain
  and travel authority remain separately gated by D1–D8 and explicit approval.

## Incremental world-generation sequence (proposed, not authorization)

**Retain the existing approach:** standard coherent noise + MST with loop edges + A\* is
appropriate for this atlas. Improve reproducibility and layer semantics before expanding
geography. No replacement engine, erosion simulator, or speculative climate framework.
Option A registry ownership and occupancy-independent geography are **chosen**; the steps
below are **proposed** increments. None authorizes production timing, schema, API, discovery,
or existing-placement changes. Those require their own approved contract and rollout.

### 1. Stabilize identity and make the world recipe explicit

- Specify one reproducible recipe: seed, generator/constraint versions, effective config,
  and canonical shared public anchors (stable IDs, coordinates, requirements, source revision).
  Existing config/version fields are a starting point, not a complete recipe contract.
- Evaluate a stable identity source instead of response-index anchor IDs. Any new wire
  identity or exact-coordinate API is a separately approved API change, not assumed here.
- Decide recipe ownership: frontend may derive presentation today; a future movement
  authority must consume the same recipe/output, not independently approximate it.
- Keep private anchors and unlocked subsets out of client-visible shared geography.

**Acceptance:** identical recipe reproduces terrain, roads, placement and diagnostics;
reordering an identical anchor set changes nothing; occupancy, active vault, discovery and
UI themes do not alter geography. Co-cell conflicts stay visible and deterministic. Capture
an explicit version/output delta for generation changes; do not silently move registry pins.

### 2. Resolve land-safe real slots on the fixed world

Evaluate a deterministic slot-index → land-position map against the fixed recipe. Reuse
existing nearest-land/spacing ideas where suitable, but never carve terrain when a player
claims a slot. Prototype snapped slots are not proof that backend jittered slots are safe.
Before adopting placement changes, explicitly decide how existing persisted slot indices,
home markers, expedition origins and history remain compatible.

**Acceptance:** every configured slot is land-safe, unique and sufficiently spaced across
representative recipes; allocation/occupancy order does not change positions or geography;
capacity/failure behavior is explicit. Existing-vault relocation, if needed, has a separately
approved migration/backfill and compatibility plan. Do not rewrite slot coordinates casually.

### 3. Elevation first, as a small presentation increment

Prefer retaining/exporting the continuous normalized `baseField` already used for water/hills,
rather than generating another unrelated height field. Evaluate restrained hillshade or
contours in the production SVG atlas. Identify whether exported height represents the base
field or adjusted final terrain: rivers, constraints, dry patches and reachability repairs
currently modify categorical terrain afterward, so their mismatch must be explicit.

**Acceptance:** additive height output is deterministic and finite; the first increment
leaves existing terrain, pins, roads, costs, fog and production duration unchanged. Water
and selected markers remain legible at production zoom levels. Reclassification or terrain
reconciliation requires a versioned follow-up, not an incidental visual change.

Height does **not** imply hydrological simulation. Keep the current river/lake approach
unless observed requirements justify changing it; no drainage, flow accumulation or erosion
work is needed merely to draw relief.

### 4. Moisture second; separate natural geography from overlays

Only after elevation is useful, evaluate a deterministic moisture field (reuse the existing
forest noise stream where suitable) for coherent forest/dry-region character. Separate
natural biome/elevation/water from ruins, radiation and site overlays, and from roads/bridges
as traversal infrastructure. This is a proposed model direction, not a new persisted schema
or permission to introduce radiation gameplay. Preserve compatibility with existing
`TerrainType`/cost consumers during any incremental transition.

**Acceptance:** overlay changes do not rewrite base height/water; metadata, legend and
routing do not acquire conflicting sources of truth. Region variety improves without losing
reachability/scavenging guarantees. Temperature is deferred unless a specific biome or
player decision needs it; elevation + moisture is not a mandate for a climate engine.

### 5. Close the scout contract before adopting terrain movement

First evaluate the shipped scout path end-to-end: target selection, coordinate conversion,
backend duration, completion and discovery feedback. Decide strict frontier validation,
coarse-band presentation, and whether a scout is approximate free-roam or target-bound.
Target persistence, routed arrival or server-owned fog would be separate approved changes.
Then decide roads/bridge movement semantics and one ETA authority before porting A\* timing.

Current crossings/repair can turn water into passable terrain. **If** terrain movement is
adopted, represent bridges as traversal over preserved water, not dry-biome replacement;
make water passable only at valid crossings and keep routing/rendering consistent. This
would change simulation and therefore needs explicit versioning/approval, not a visual patch.

**Acceptance:** player sees one server-authoritative ETA contract; scout completion matches
the chosen target/free-roam semantics and discoveries surface through existing feedback.
For any approved tile movement increment, validate reachable anchors/slots, valid connected
crossings, preserved water under bridges, and road-benefit behavior using the same authority
as dispatch. Preserve registry IDs, Journal history, access checks and tick compatibility.

## Deferred future presentation — map styles and optional layers

**Future proposal only; not current scope or implementation authorization.** Retain these
presentation preferences for a later increment without delaying the foundational recipe,
identity, land-safe placement, discovery and scout-contract work above. This section
supplies no authorization for code/config changes or changes to generation, APIs or gameplay.

- **Reuse existing data and assets:** derive location marker types/filters from existing
  world-location category data; reuse the better existing dev-route icons rather than
  inventing another category/icon system. No player-facing marker numbering or device bezel.
- **Ownership and selection (proposed):** distinguish all of the user's vaults (up to three)
  from other users' vaults by consistent ownership colors. Identify the current vault with
  an outline/selection treatment, not a different ownership color; retain non-color cues
  for accessibility. Rendering never grants visibility to otherwise unauthorized vaults.
- **Styles over one world:** schematic uses minimal geography; biomes depicts existing
  environments; terrain may later show useful elevation/contours. Start the future style
  increment with schematic + biomes using existing data, not a new moisture/climate model.
  Defer the terrain style until elevation is useful and available; it is not a prerequisite
  for either initial style or the current foundational work.
- **Shared rendering data, not separate implementations:** all styles consume one world/model
  and shared rendering data/pipeline. Keep icons, ownership colors, selection identity,
  coordinates and discovery authority consistent across styles; switching style changes
  presentation only, never world positions, visibility, routing or expedition timing.
- **Independent optional overlays:** roads, location markers with category/type filters,
  vaults, discovery trails, active expeditions and labels can each be toggled independently
  of the base style. Trails remain discovery history, not navigation routes; expedition
  overlays use only authorized existing data, not new live multiplayer tracking.
- **Compact controls:** a small style selector and layers menu, with sensible defaults;
  avoid an overconfigured cartography/settings panel.

## Immediate next steps

1. Land `feat/map-atlas` (this branch), then extract `feat/map-vault-slots` (persisted
   slots, ownership markers, atomic allocation) and `feat/map-scouting` (scouting action +
   production UI) as the next stacked slices.
2. Agree the recipe/stable-public-anchor contract using existing DEV diagnostics; record
   unresolved API precision/identity choices before implementing them.
3. Evaluate backend slot positions against that fixed world and document land conflicts;
   choose compatibility treatment before any placement change.
4. Make the first terrain enhancement additive elevation for production readability, not
   a new generator or travel model. In parallel, review the real scout flow's semantic gaps.
5. Defer moisture/overlay refactoring until those increments have acceptance evidence;
   retire prototype-only code only after production replaces its distinct behavior.

Future implementation should add focused regression checks for these acceptance conditions
and perform live scout/migration verification when authorized. This update itself is
documentation-only and supplies no new runtime validation evidence.