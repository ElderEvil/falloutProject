# World evolution — ready-to-post GitHub issue drafts

Documentation-only backlog, prepared 2026-10-03. Sections 1–4 were posted as issues #859–#862 (umbrella, snapshot adoption, candidate preview/activation, expedition choices); the bodies below remain the record of what was filed. These drafts do not authorize implementation, data changes, merges, or travel adoption.

Source inspection on `feat/wasteland-atlas` found a clean working tree before this documentation change. Implemented means present in source, not deployed or validated. Earlier authorized validation/delivery is reported as underway; this pass did not verify its outcome and ran no tests, lint, database checks, live playtests, or GitHub API calls. Older contract inventories/open decisions are historical where current source has overtaken them.

## 1. Umbrella: player-facing world evolution waves

**Title:** World evolution: track player-facing waves from the current atlas to a stable, explorable world

### Problem and goal

World work spans two lanes with different readiness and authorization boundaries. Track them together without discarding already extracted work, reopening implemented foundations, or presenting an attractive atlas as authoritative travel. The goal is a backend-owned, versioned shared world that players can understand, explore, and eventually use to make meaningful expedition choices.

### Current implementation versus pending work

- The map-interaction → atlas → persisted slots → scouting lane already has production viewport/selection, shared TS atlas rendering, discovery-derived fog, slot markers/origins, and scout submission. Strict frontier/target/completion semantics are not established merely by having a submit button.
- The core → snapshot lane already has Python terrain/land-safe-slot generation, `WorldSnapshot` JSONB storage, CRUD/service, authenticated map snapshot reads, and a guarded development-only reset. Production `AtlasTerrain.vue` still calls the TS generator.
- Current authorized validation and delivery of extracted work is **ongoing reported work**, not a new implementation milestone in this issue. Record actual outcomes when available; do not mark it passed from historical notes.
- Explicit active-world selection, stored candidate preview/activation, production snapshot adoption, and authoritative terrain/road travel remain follow-ups.

### Dependencies and context

Read `docs/features/PROTOTYPE_TO_PRODUCTION_PORT.md` for authoritative port sequencing; `docs/features/WORLD_GENERATION_CONTRACT.md` for world ownership and guarantees; `docs/features/EXPEDITION_MAP_CONTRACT.md` for visibility, scouting, roads and ETA; `docs/features/TILE_MAP_INTEGRATION.md` for D1–D8/sign-off; and `docs/backend/GAME_MECHANICS.md` for progression feedback and tick compatibility. Link the three child issues below after posting; do not invent issue numbers.

### Player-facing waves and guarantees

1. **Current delivery/validation:** retain and validate both extracted lanes. Players keep map interaction, atlas, discovery feedback, slot identity, and existing expedition behavior; record limitations rather than creating duplicate implementation tickets.
2. **Stable backend world (issue 2):** players see the persisted world, with consistent home/marker/dispatch coordinates and geography that does not change with occupancy or discovery.
3. **Safe world evolution (issue 3):** operators can inspect stored candidates and explicitly activate a compatible transition while preserving playtest progress. Players remain on one shared active world until that decision.
4. **Expedition choices (issue 4):** after separate travel approval, players can make meaningful terrain/road-aware choices with one authoritative estimate and honest scout semantics.
5. **Later readability/presentation:** evaluate additive elevation, then moisture only when useful. Start optional styles with schematic + biomes using existing data; terrain style waits for useful elevation. Reuse existing dev-route icons and category data. Distinguish the user's owned vaults (up to three) from other users' vaults, with current selection outlined and non-color cues. No device bezel or player-facing marker numbers. All styles/layers share one world and cannot change visibility, positions, routing, or timing.

### Acceptance criteria

- [ ] Track current delivery and validation evidence separately from pending implementation; carry forward unresolved failures/limitations and distinct regression coverage.
- [ ] Link child issues and record wave dependencies, sign-off, player-visible capability, and what remains deferred at each completion.
- [ ] Both lanes converge without a parallel player renderer or duplicate world authority; retire prototype-only behavior only after production replaces it.
- [ ] Every wave preserves registry/vault identity, authorization, Journal history, and progression pop-up/toast feedback in addition to bell entries.
- [ ] Later elevation is deterministic/additive and leaves categorical terrain, coordinates, costs, fog, and duration unchanged initially. Reclassification needs an explicit versioned follow-up.
- [ ] Moisture/overlay work does not create conflicting geography sources; overlays do not rewrite base height/water. Temperature/climate work needs a demonstrated player need.
- [ ] Later styles and independent layer controls preserve the restrained CRT hierarchy and accessibility; presentation switches never switch worlds.

### Non-goals / still deferred

No new engine, climate/erosion simulator, automatic world upgrades, active-duration rewrites, multiplayer live tracking, or wholesale prototype/test deletion. This tracker does not authorize travel, reset execution, new schemas/APIs, or merges. Later presentation must not block foundational adoption or safe migration.

---

## 2. Production adoption of the implemented backend snapshot

**Title:** Adopt the backend world snapshot in production map rendering and coordinate consumers

### Problem and goal

Backend terrain and land-safe slots exist, but production `frontend/src/modules/map/components/AtlasTerrain.vue` still calls `generateWorld` from `atlasWorldgen.ts` and draws that world's roads. Finish adoption so players see the same stable backend-owned world used for placement, rather than a second independently generated geography.

### Current implementation versus pending work

Implemented source includes `backend/app/services/world_generation.py`, `backend/app/models/world_snapshot.py`, `backend/app/crud/world_snapshot.py`, `backend/app/services/world_snapshot_service.py`, and authenticated snapshot reads in `backend/app/api/v1/endpoints/map.py`. Existing slots/markers/origins and visibility/fog remain reusable. This is **not** a request to implement another core, snapshot table, or API.

Pending: consume that snapshot through the frontend Store → Service → API layers, reconcile coordinate consumers and registry compatibility, and replace production geography generation safely. The current API calls `get_or_generate`, which can generate when a row is absent; its read-only docstring is not proof that reads never generate. Snapshot serialization also currently stores only a subset of `WorldConfig` fields: verify full recipe reproducibility before calling adoption complete.

### Dependencies and context

Depends on actual results from current authorized core/snapshot validation and delivery, plus a reviewed initial-world transition using issue 3 when persisted placements/progress are affected. Consult `docs/features/WORLD_GENERATION_CONTRACT.md`, `docs/features/PROTOTYPE_TO_PRODUCTION_PORT.md`, `docs/features/EXPEDITION_MAP_CONTRACT.md`, and `docs/features/VAULT_SLOT_MIGRATION.md` (historical design, not a live vault count). Coordinate/version/API changes require their own approval and generated frontend types.

### Players can / world guarantees

Players can inspect and navigate the existing production atlas with backend terrain and consistent land-safe home/marker/origin positions. Occupancy, active vault, discoveries, and theme do not reshape geography. Private discoveries, ownership, and expedition state stay outside the shared public snapshot; fog remains presentation, not authorization.

### Acceptance criteria

- [ ] Production renders the selected persisted backend snapshot through existing map architecture/viewport; no independent TS geography generation or parallel player route remains in this path.
- [ ] Persist/read the complete effective recipe and identify world/version/fingerprint/checksum; verify reproducibility and stable public-anchor identity/order with focused evidence.
- [ ] Snapshot reads do not regenerate or activate another world; missing/unavailable data has explicit safe behavior, never silent TS fallback or latest-version activation. Coordinate this lifecycle boundary with issue 3.
- [ ] Slots are unique, in bounds, traversable, sufficiently spaced and reachable; capacity/placement failure is explicit. Home markers, player markers and dispatch origins use one coordinate source and agree.
- [ ] Preserve exact registry identity/compatibility, discovery authorization, selection, keyboard/touch interaction, Journal and feedback. Do not assume projection proves anchor compatibility.
- [ ] Omit unrelated TS roads when rendering Python terrain. Any later roads must belong to the same versioned world; decoration must not masquerade as movement authority.
- [ ] Record focused integration/live-map validation and limitations; regenerate API types for approved API changes. Retire obsolete generation only after replacement behavior is proven, preserving distinct tests.

### Non-goals / still deferred

No duplicate core/API implementation, terrain/road travel adoption, new scout-target guarantees, server-owned explored mask, height/moisture/styles, destructive reset, or existing expedition duration/history rewrites. Current distance-based backend travel remains authoritative until separately approved.

---

## 3. Candidate preview and explicit world activation

**Title:** Preview stored candidate worlds and explicitly activate progress-preserving migrations

### Problem and goal

Generator evolution must not force a local reset or silently move players onto the newest snapshot. Add a reviewed lifecycle for one shared active world and stored candidates, with a read-only compatibility preview and explicit activation that preserves playtest progress.

### Current implementation versus pending work

`WorldSnapshot` stores versioned terrain/slots; `CRUDWorldSnapshot.get_active` currently fetches a specified world/version, not an explicit active-world pointer. `WorldSnapshotService.get_or_generate` is version-keyed and can create a missing snapshot. There is no demonstrated candidate/activation lifecycle in these inspected paths.

`backend/app/services/dev_world_reset_service.py` is an existing guarded **local-only** reset for snapshot/slots/home placement; it documents preservation of users, vault identities, discoveries and expeditions. Keep that tool distinct: resetting/replacing development placement is not a migration preview, compatibility policy, or progress-safe activation workflow. Older contracts calling dev data disposable do not justify deleting progress for this future workflow.

### Dependencies and context

Build on the implemented snapshot/core and coordinate adoption with issue 2. Relevant contracts: `docs/features/WORLD_GENERATION_CONTRACT.md`, `docs/features/PROTOTYPE_TO_PRODUCTION_PORT.md`, `docs/features/VAULT_SLOT_MIGRATION.md`, `docs/features/WORLD_MAP.md`, `docs/features/WASTELAND_JOURNAL.md`, and `docs/backend/GAME_MECHANICS.md`. Decide active-expedition policy and the permitted relocation/registry treatment before implementation; schema/API/operator actions need explicit approval.

### Players can / world guarantees

Players continue playing on one active shared world while candidates are stored and evaluated. Operators can see what would change before approving activation. Preserve users, vault IDs/numbers, slot identity/mapping where compatible, dwellers, inventory/resources, discoveries/unlocks, Journal, and unrelated progress. Candidate generation/preview never changes active positions or player state.

### Acceptance criteria

- [ ] Persist an explicit active-world selection and independently stored candidates with complete recipe/version/fingerprint/checksum; creating a candidate or deploying a newer generator never activates it.
- [ ] Preview reports terrain/slot/home/origin differences, registry-anchor conflicts, land safety/spacing/reachability/capacity, affected vaults and active expeditions, and preservation/relocation requirements. Report incompatibility instead of silently repairing identity.
- [ ] Activation names the exact candidate and expected active revision, requires explicit authorized confirmation, rechecks compatibility, and atomically switches shared selection plus approved mappings. Concurrent/stale activation fails without partial movement.
- [ ] Product explicitly chooses active-expedition handling. **Recommended simplest policy: block activation while affected expeditions are active**, with a clear reason and later retry. Any alternative must define version pinning/completion/origins before adoption; never drop expeditions or silently rewrite durations/routes.
- [ ] Preservation assertions cover playtest progress and authorization; any unavoidable relocation is listed, approved, deterministic and auditable. Normal migrations never wipe application data.
- [ ] Failure before commit leaves the active world and progress unchanged. Document operational recovery limits: retaining old snapshots is not a promise of rollback after players make new progress.
- [ ] Provide focused preview/no-side-effect, stale/concurrent activation, incompatibility, expedition-policy and preservation validation, with honest live evidence/limitations. Keep local reset guards/scope separate.

### Non-goals / still deferred

No latest-snapshot autoactivation, per-player active worlds, unconditional data wipe, reset-as-migration, implicit relocation, automatic rollback after progress, historical trail rewrites, or terrain travel adoption. Read-only preview does not authorize activation execution.

---

## 4. Terrain/road-aware expedition decisions

**Title:** Make terrain and roads meaningful expedition choices under one approved travel authority

### Problem and goal

Players can submit scouts and inspect the atlas, but production dispatch is distance-based and does not consume terrain/roads. A network that looks authoritative while having no production effect is misleading. Close scouting semantics, then introduce meaningful route/destination decisions on the stable world only after an explicit travel contract is approved.

### Current implementation versus pending work

Production scout submission is wired, but the documented service path converts target distance into a band upper bound and free-roam dispatch; target-bound arrival/reveal is not established. Discovery-derived fog is not a server-owned walking mask. Prototype known-only A* and 0.7× road experiments are reference evidence, not production policy or newly verified measurements. Python terrain/snapshot foundations exist; production still renders TS geography pending issue 2.

### Dependencies and context

Depends on issue 2's adopted stable world and issue 3's explicit version/transition policy. First settle the end-to-end scout contract; **separate approval for authoritative travel is mandatory**, including road/crossing semantics and calibration. Read `docs/features/EXPEDITION_MAP_CONTRACT.md` DD2–DD5, `docs/features/TILE_MAP_INTEGRATION.md` D1–D8, `docs/features/PROTOTYPE_TO_PRODUCTION_PORT.md` scouting/movement sequence, `docs/features/EXPLORATION_SYSTEM.md`, and `docs/backend/GAME_MECHANICS.md`.

### Players can / world guarantees

Players can intentionally scout a permitted frontier and understand whether that action is approximate free-roam or target-bound. After approved movement adoption, they can choose reachable known destinations/routes with meaningful road/terrain effects and one server-authoritative ETA. Hidden destinations/costs are not leaked; discoveries surface through toast/card or modal plus Journal and bell entry.

### Acceptance criteria

- [ ] Explicitly choose and implement frontier validation, coarse-band presentation, target persistence/arrival semantics if needed, completion/discovery feedback, and failure behavior. Free-roam must be labeled honestly; submitting coordinates is not proof of target arrival.
- [ ] Approve one server-owned travel model/calibration before adoption. The player sees one known-destination ETA; scouting has its own explicitly approximate band, not a competing destination estimate.
- [ ] Routing and rendered roads consume the same backend-owned world/version and traversal rules. No TS roads from an unrelated world; no automatic import of the prototype 0.7× discount.
- [ ] Demonstrate representative cases where terrain/roads change useful route or destination choices, not just a cosmetically smaller number. If roads remain decorative, communicate/restyle them accordingly.
- [ ] Water remains impassable except approved valid connected crossings; bridges preserve underlying water, and rendering, reachability checks and dispatch agree.
- [ ] Visibility gates selection, details, routing, ETA, lists and dispatch; no hidden location identity/path leak. Journal trails remain discovery history, not computed routes.
- [ ] Existing active expedition durations/routes and historical trails are not rewritten. Define world-version behavior for new dispatch and candidate activation; preserve ownership/access checks and tick-session compatibility.
- [ ] Validate scout → discover → inspect → dispatch → revisit, route/crossing boundaries, authorization, feedback and timing calibration; record real evidence and unresolved limitations before retiring distinct prototype behavior/tests.

### Non-goals / still deferred

No exposure/risk system, climate/erosion simulation, new live multiplayer tracking, generic route-engine rewrite, exact hidden scout endpoint, automatic travel rollout, or active-duration retuning. Server-owned explored persistence, elevation/moisture and optional map styles require separate scoped decisions; none is prerequisite for closing honest scout semantics.
