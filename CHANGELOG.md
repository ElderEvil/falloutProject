# Changelog

All notable changes to this project will be documented in this file.
See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

## [2.46.1](https://github.com/ElderEvil/falloutProject/compare/v2.46.0...v2.46.1) (2026-08-21)

### Bug Fixes

- **Discovery markers unlock immediately** — registering a discovery now links it to the exploring dweller with
  `is_unlocked=True`, so its marker is visible on that vault’s map. The race-safe link path also upgrades an
  existing locked link when a concurrent request created it first.
- **Existing discoveries can be repaired safely** — `backfill_unlock_discoveries.py` restores missing unlock links
  for historic discovery rows and reports only actual changes, so re-running it is idempotent.
- **Exploration journals load on direct navigation** — the detail view always fetches the full exploration record;
  it no longer renders blank when the vault list supplied its shorter summary schema. Loot rendering also treats
  missing item lists as empty.

## Unreleased — The Overseer's Toolkit

### Features

- **Overseer Briefing** — the Overseer’s Office now provides a live command readout with expedition, training,
  quest, staffing, capacity, and morale metrics, plus prioritized threats and resource warnings; its room-grid badge
  highlights unresolved items without displacing the vault workspace.
- **Consistent management screens** — shared responsive page rails, aligned headers, and concise terminal-green
  descriptions bring Dwellers, Quests, Objectives, Map, Training, Relationships, Storage, and Exploration into one
  operational layout while preserving the distinct Operations Overview.

### Fixed

- **AI stream and quota reliability** — structured chat output streams incrementally and shared quota-cache keys
  prevent inconsistent usage accounting across AI services.
- **Dweller UI compatibility** — restore the Build Mode icon, correct status badge glow tokens, and keep children
  previews aligned without unsafe placeholder data.
- **Exploration detail polish** — explorer portraits carry through to the detailed journal; legacy health events
  render a framed cumulative trend, healing uses theme green, and health/progress use consistent pill-shaped terminal
  meters. Long equipment names stay within exploration-card slots.

### Changed

- **Production observability** — API logs write structured, rotating files to a persistent Kubernetes volume while
  retaining stdout diagnostics; the worker remains on stdout until it has a deployment manifest. Ollama remains a
  local-development provider only.
- **Authenticated browser coverage** — the vault briefing and response flow have deterministic Playwright coverage
  that does not require production credentials or a local Ollama server.

## [2.46.0](https://github.com/ElderEvil/falloutProject/compare/v2.45.1...v2.46.0) (2026-08-21)

### Features

- **Wasteland Journal loot, vitals, and discovery deep-links** — discovery events persist their map location id
  and coordinates, and health deltas are recorded on exploration events (JSONB, no migration); the detail view
  surfaces mid-journey loot as a rarity-tinted list and a cumulative health-change trail, and discovery events
  deep-link to their map marker via `?place=`
- **Event-authoritative discovery routes** — the map API projects per-exploration discovery trails from
  exploration events (which now carry coordinates) instead of de-duplicated location rows, so repeated visits
  remain part of the journey; ordered `discovery_routes` render as dashed polylines on the WorldMap. Adds the
  World Map feature contract, delivery plan, and Wasteland Journal feature docs

### Bug Fixes

- **Consolidated exploration progress math** — one time-zone-safe elapsed-progress calculation
  (`useExplorationProgress`) now powers explorer cards, the active list, and the wasteland panel, removing three
  duplicated implementations (and fixing offset parsing in two); dead components (`ExplorationConfigModal`,
  `DwellerDropZone` duplicates) are gone, and quest party members render on quest cards
- **Map detail loading & review feedback** — address review feedback and fix map detail loading

## [2.45.1](https://github.com/ElderEvil/falloutProject/compare/v2.45.0...v2.45.1) (2026-08-21)

### Bug Fixes

- **Viewer-independent neighbor-vault signals** — temporary neighbor-vault markers were seeded from the viewer's
  vault UUID, so every player saw a different set of signals; they now derive from a fixed global constant so the
  wasteland is shared and viewer-independent, laying the foundation for async-PvP raiding

## [2.45.0](https://github.com/ElderEvil/falloutProject/compare/v2.44.0...v2.45.0) (2026-08-21)

### Features

- **Wasteland auto-equip & live exploration feed** — dwellers returning from exploration auto-equip the best
  weapon/outfit they found (old gear returns to storage) with an `exploration_update` notification; the
  exploration detail view streams events live over SSE (event log, health, radiation, and counters update in
  real time), and the obsolete `EventTimeline` was consolidated into `ExplorationEventLog`

### Fixed

- **Stale storage check constraints** — migration drops the leftover `ck_storage_radaway_bounds`/
  `ck_storage_stimpack_bounds` DB constraints (the Storage model validates bounds via Pydantic), restoring the
  `alembic check` CI gate
- **Stale production URLs** — the CORS default and deployment docs now reference the live `fallout*.evillab.tech`
  domains instead of the dead `fallout*.evillab.dev`

### Changed

- **Notification plumbing compaction** — a shared `notify_owner` helper centralizes the vault-owner lookup and
  best-effort delivery across the training, death, and incident services, and the exploration report queue now
  uses VueUse `useStorage` instead of hand-rolled localStorage sync (unused `consumePendingReport`/
  `clearPendingReports` exports removed)

## [2.44.0](https://github.com/ElderEvil/falloutProject/compare/v2.43.0...v2.44.0) (2026-08-21)

### Features

- **Overseer activity & incident outcome reports** — long-running dweller activities end in a visible outcome
  instead of a silent state change: training completion sends a persistent `training_complete` notification
  carrying the stat change, exploration completion notifications carry the full rewards payload, and resolving an
  incident sends a `combat_victory` or `combat_defeat` notification with the outcome summary so attacks and fires
  report their result

### Fixed

- **Breeding at population capacity** — `check_for_conception` no longer starts a new pregnancy when the vault
  population has reached `population_max`; already-committed pregnancies reserve their slot, and a single free
  slot can only be consumed by one new conception per game tick (regression coverage in
  `test_breeding_service.py`)

## [2.43.0](https://github.com/ElderEvil/falloutProject/compare/v2.42.0...v2.43.0) (2026-08-21)

### Features

- **Living quarters socializing** — dwellers assigned to living quarters now rest instead of idling: the new
  `RESTING` status renders as "Socializing" (heart badge plus a filter option), and the game loop raises affinity
  only between dwellers sharing living-quarters rooms rather than any shared room. Charismatic pairs bond faster
  (+`min(charisma)/10` bonus per tick). A backfill migration sets `RESTING` on dwellers already living in living
  quarters, and boosted starter vaults spawn a charisma-boosted male/female pair resting there
- **Dweller social context chat tool** — the chat agent gained `get_dweller_social_context()`, so questions about a
  dweller's mood, family, or relationships are answered from live status, room, family members, and relationship
  affinities instead of a static profile

## [2.42.0](https://github.com/ElderEvil/falloutProject/compare/v2.41.3...v2.42.0) (2026-08-20)

### Features

- **MARRIED relationship stage** — partners at the marriage threshold (affinity ≥ 85) can marry via
  `PUT /relationships/{id}/marry`; marriage grants a one-time happiness bonus and fires a notification, auto-marry
  triggers when affinity reaches the threshold, and `break_up` now also clears married couples
- **Lineage API** — `GET /dwellers/{id}/lineage` returns parents, children, siblings, partners, and a computed
  generation; results are vault-scoped and immune to cycles, cross-vault links, and soft-deleted ancestors
- **Family tree UI** — the dweller detail page adds a "Family" tab rendering the family tree with clickable nodes,
  a siblings row, dead/age/partner-stage+affinity labels, and error/retry + refresh states
- **Relationship UI polish** — relationship cards show milestone hints toward the next stage, couples render a
  compact family diagram, and cards share consistent backgrounds with fixed-position affinity
- **Family scenario tooling** — a `family_scenario` CLI command plus `family_scenario_service` seed test couples and
  multi-generation families (co-location, pairing, births) for balance testing

### Changed

- **Release tooling** — root `package.json`/lockfile removed; semantic-release runs from CI via a pinned `npx`
  invocation so frontend deps stay in `frontend/` (pnpm) and backend deps in `backend/` (uv)
- **Docs cleanup** — ROADMAP pruned to future plans (history lives here); TrueNAS deployment docs, examples, and
  redeploy script removed; `docs/features/FAMILY_SYSTEM.md` documents the family domain
- **Debug controls removed** — PregnancyDebugPanel and its pregnancy store slice were removed from the social UI

### Fixed

- **Migration-safety CI** — `backend-coverage.yml` now runs `alembic check` + `alembic current --check-heads` against
  a live PostgreSQL service container; migration (`b7e9f2c1a3d5`) drops two stale schema objects so `alembic check`
  passes
- **Marriage integrity** — the relationship update and happiness bonus apply atomically (bonus failure rolls back the
  whole transition, surfaced as HTTP 400), and a conditional `PARTNER→MARRIED` update makes concurrent marry requests
  single-winner so the bonus/notification can never fire twice; the enum downgrade normalizes rows back to `partner`
- **Stale detail responses** — DwellerDetailView tracks the requested dweller id with a monotonic load sequence so
  out-of-order completions cannot clobber a newer dweller's state

## [2.41.3](https://github.com/ElderEvil/falloutProject/compare/v2.41.2...v2.41.3) (2026-08-19)

### Fixed

- **Postpartum breeding cooldown** — mothers who delivered within `birth_cooldown_hours` (default 6h) are excluded
  from conception checks, so a high-affinity couple can no longer conceive again on the next game tick and produce
  a baby every pregnancy cycle (3h) indefinitely
- **Baby last-name inheritance** — newborns now take the father's last name by default, with a 20% chance of the
  mother's last name (`maternal_last_name_chance`), so a baby no longer routinely shares the mother's exact full
  name ("April Hernandez gave birth to April Hernandez!")
- **Cross-vault postpartum data leak** — `_get_postpartum_mother_ids` now joins to `Dweller` and filters by
  `Dweller.vault_id` so the cooldown only applies to the current vault

## [2.41.2](https://github.com/ElderEvil/falloutProject/compare/v2.41.1...v2.41.2) (2026-08-19)

### Fixed

- **Quest completion 500 on full storage** — `reward_service.grant_item` now raises `ResourceNotFoundException`
  (404, no storage row) and `ResourceConflictException` (409, storage full) instead of bare `ValueError`, so the
  quest completion endpoint returns the correct HTTP status code
- **Cross-thread EventBus / asyncpg InterfaceError race** — `EventBus.emit` locks are now keyed by
  `(event_type, vault_id, event_loop)` so each Dramatiq worker thread gets its own lock; objective evaluators
  use a loop-local session maker (via `set_current_session_maker`) so concurrent ticks never share a single
  asyncpg connection, eliminating the `InterfaceError: another operation is in progress` (324×/24h on Hetzner)

## [2.41.1](https://github.com/ElderEvil/falloutProject/compare/v2.41.0...v2.41.1) (2026-08-18)

### Fixed

- **Frontend audit CRITICAL/MAJOR fixes** — dead camelCase token utilities replaced with kebab-case equivalents
  across 20+ components (Tailwind v4 generates no utilities for camelCase tokens); broken `--color-terminal-green-*`
  theme vars removed and remapped to the surviving semantic tokens; hardcoded hex colors migrated to design tokens
  (happiness bands, quest palette, rarity, vault shell); router monkey-patch properly typed instead of implicit `any`

## [2.41.0](https://github.com/ElderEvil/falloutProject/compare/v2.40.0...v2.41.0) (2026-08-17)

### Features

- **Chat over WebSocket** — chat messages now stream over the existing WebSocket (`token`/`done`/`error` chunks)
  instead of punting to REST, with an automatic REST fallback when the socket is disconnected; the chat UI renders
  tokens incrementally as the AI replies
- **Vault event system** — the game loop now fires weighted random vault events (resource cache, wanderer at the
  door, raider scout) for online vaults above a minimum population, awarding caps or spawning incidents with
  configurable spawn chance and reward ranges
- **Notification navigation** — clicking a notification in the bell now routes to the relevant view (exploration,
  training, quests, dwellers, objectives) based on its type, in addition to marking it read
- **Visual equipment consistency** — generated dweller visual attributes (`accessory`, `object_held`) are now
  constrained to items the dweller actually has equipped, instead of free text chosen from anywhere
- **Resource depletion warning** — resource bars show a persistent draining indicator when a resource is critically
  low and trending downward, instead of only a transient arrow

### Changed

- **Exploration rewards via SSE** — exploration completion/recall events now publish to the vault channel the
  frontend subscribes to, so auto-completed explorations surface their rewards modal in real time

### Fixed

- **Exploration SSE channel** — the exploration coordinator published completion events to the vault owner id while
  the frontend subscribes to the vault id, so rewards never reached the client; the publish now targets the vault
  channel
- **Silent incident fetch failure** — SSE-triggered incident refreshes no longer swallow errors silently; failures
  surface through the standard error handler
- **Room relationships** — dwellers without an assigned room are now excluded from affinity pairing, and the room
  query no longer depends on a helper that fetched every dweller first

### Removed

- **Objectives debug overlay** — the floating debug button and its `console.log` patching are removed from the
  player UI

## [2.40.0](https://github.com/ElderEvil/falloutProject/compare/v2.39.4...v2.40.0) (2026-08-15)

### Features

- **Training tab UX** — training rooms now render as occupancy cards with live capacity and per-room active training
  counts; the queue groups active sessions by room, and progress cards show dweller avatars with live progress bars
  that fill even before the game-loop worker persists an update

### Changed

- **Training timestamps** — training schemas now serialize datetimes as unambiguous UTC (`Z`-suffixed ISO-8601),
  so naive-UTC and tz-aware values render consistently to the client
- **Training room capacity** — capacity is computed through a shared `getTrainingRoomCapacity` helper used by both
  the room grid drop logic and the training tab, replacing duplicated inline math

## [2.39.4](https://github.com/ElderEvil/falloutProject/compare/v2.39.3...v2.39.4) (2026-08-14)

### Fixed

- **Resource production rate** — bump `base_production_rate` from 0.01 to 0.1 (another ~10x) for a livelier resource
  economy

## [2.39.3](https://github.com/ElderEvil/falloutProject/compare/v2.39.2...v2.39.3) (2026-08-14)

### Fixed

- **Dweller thumbnails** — thumbnails now resolve through `getStaticImageUrl`, which prepends the API base URL so
  images load from the backend directly; root-relative `/static/` paths previously 404'd on deployments where the
  frontend and backend are separate origins

## [2.39.2](https://github.com/ElderEvil/falloutProject/compare/v2.39.1...v2.39.2) (2026-08-14)

### Changed

- **Release housekeeping** — changelog cleanup; no functional changes in this release

## [2.39.1](https://github.com/ElderEvil/falloutProject/compare/v2.39.0...v2.39.1) (2026-08-14)

### Fixed

- **Resource production rate** — bump `base_production_rate` from 0.0003 to 0.01 (~33x) so vaults produce usable
  resources instead of trickling at ~0.36 units per tick

## [2.39.0](https://github.com/ElderEvil/falloutProject/compare/v2.38.0...v2.39.0) (2026-08-14)

### Changed

- **Resource production rate** — bump `base_production_rate` from 0.0003 to 0.1 (~333x) so vaults produce usable
  resources instead of trickling at ~0.36 units per tick

## [2.38.0](https://github.com/ElderEvil/falloutProject/compare/v2.37.0...v2.38.0) (2026-08-14)

### Features

- **Safer room construction** — room builds now use server-owned templates, so costs, sizes, categories, formulas,
  and upgrades cannot be supplied or manipulated by the client; the build menu now includes room artwork.
- **Visual equipment inventory** — outfits and weapons now display their artwork in storage and combat equipment views.
- **Legendary starter team** — boosted vaults include legendary dwellers with themed weapons and outfits for easier
  high-level testing.

### Fixed

- **Legendary portraits** — legendary dwellers now receive thumbnails in dweller lists and grids, including existing
  vault records after migration.

### Changed

- **Asset coverage** — new rewards, exploration finds, and starter items receive their matching artwork automatically;
  existing outfit, weapon, and legendary-dweller records are backfilled on upgrade.

## [2.37.0](https://github.com/ElderEvil/falloutProject/compare/v2.36.0...v2.37.0) (2026-08-14)

## [2.36.0](https://github.com/ElderEvil/falloutProject/compare/v2.35.1...v2.36.0) (2026-08-14)

### Features

- **Resource economy feedback** — show per-minute resource rates and capacity forecasts, with a calibrated
  60-second-tick production baseline for play-testing

## [2.35.1](https://github.com/ElderEvil/falloutProject/compare/v2.35.0...v2.35.1) (2026-08-14)

### Fixed

- **Quest reward settlement** — reward delivery now completes atomically, rolling back deferred changes when a reward
  cannot be applied

## [2.35.0](https://github.com/ElderEvil/falloutProject/compare/v2.34.3...v2.35.0) (2026-08-14)

### Features

- **Release automation** — synchronize versions, tagged images, and integrity validation from Conventional Commits

---

## [2.34.3] - 2026-08-13

### Fixed

- **Quest chain visibility** — vault quest responses now derive prerequisite links from their requirements, hiding
  locked chain quests by default while Show All reveals them; existing quest chains are backfilled by migration

### Changed

- **Version alignment** — backend and frontend are both v2.34.3

---

## [2.34.2] - 2026-08-13

### Fixed

- **Dweller activity safety** — generated recruits are adults; children cannot fight incidents, explore the wasteland,
  or join quest parties
- **Explorer activity safety** — active explorers cannot be reassigned to rooms or quest parties until they return
- **Quest party validation** — validate replacement parties before unassigning the current party, preventing invalid
  child or explorer requests from changing existing assignments

### Changed

- **Version alignment** — backend and frontend are both v2.34.2

---

## [2.34.1] - 2026-08-13

### Fixed

- **Exploration supplies** — preserve supplies funded by vault storage instead of deducting them from the explorer a
  second time
- **Exploration completion** — expeditions can only complete after their timer expires; early returns use recall

### Changed

- **Version alignment** — backend and frontend are both v2.34.1

---

## [2.34.0] - 2026-08-13

### Added

- **Grounded dweller activity suggestions** — chat agents can inspect active training and exploration, trainable room
  capacity, available medical supplies, and a bounded exploration pack before recommending a training, exploration,
  or recall action
- **Pydantic AI Gateway configuration** — supports Gateway API keys, custom provider/routing-group routes, and
  regional proxy URLs; includes a local authenticated API smoke-test script and setup guide for local and Hetzner use

### Changed

- **Pydantic AI observability and contracts** — Logfire now instruments Pydantic AI without prompt content; stateless
  agents use instructions, and chat action payloads are validated with bounded retries before gameplay consumes them
- **AI service naming** — renamed the provider-neutral AI service from `open_ai` to `ai_service`

### Fixed

- **Optional RustFS startup** — an unavailable S3-compatible RustFS endpoint now degrades detailed storage health
  rather than blocking backend startup; startup skips its optional probe and diagnostics use bounded timeouts
- **Hetzner deployment health-check heredoc** — quote the remote heredoc delimiter so retry variables expand on the
  Hetzner host rather than in the GitHub Actions runner

---

## [2.33.3] - 2026-08-13

### Fixed

- **Auto-assign status guard** — automatic room assignment now only selects `IDLE` dwellers,
  preventing exploring or otherwise busy dwellers from being pulled into production/training rooms
- **Training cancellation on unassign** — removing a dweller from a training room now cancels the
  active training session, keeping dweller status and the training queue consistent
- **Navbar dropdown theming** — user menu hover and focus states now use the terminal-primary
  surface instead of generic grey backgrounds

### Added

- **Auto-assign production bulk action** — dweller bulk toolbars now expose a dedicated
  "Auto-Assign Production" action for assigning workers to production rooms only

### Changed

- **Profile editor terminal styling** — profile form rebuilt with terminal-black surfaces,
  theme-primary borders, and improved spacing/accessibility labels

---

## [2.33.2] - 2026-08-13

### Fixed

- **Training queue after automatic assignment** — bulk room assignment now creates active training sessions for
  dwellers placed in training rooms, keeping the `training` dweller status, progression timer, and Training Queue in
  sync; regression coverage protects the invariant

---

## [2.33.0] - 2026-08-13

### Changed

- **Type-aware frontend linting** — enabled Vite+/Oxlint type-aware analysis while retaining the existing `vue-tsc`
  typecheck gate; fixed all 15 newly reported promise-safety and redundant-type findings without adding standalone Oxc
  dependencies or upgrading TypeScript/Pinia
- **Stale async requests** — dweller filters, modal room loads, and dead-dweller queries now only apply their latest
  response; regression tests protect against obsolete responses overwriting current state
- **Consistent back navigation** — active in-app routes now share one labelled terminal back control in a standard
  top-left page position; Profile returns to the active vault rather than the vault list
- **Exploration Detail shell** — added the shared vault sidebar and corrected the explorer toolbar stacking order so
  the global navbar remains above route-level controls
- **Terminal surface consistency** — Profile, Exploration Detail, and dweller revival panels now use terminal-black
  surfaces instead of competing grey/warm-grey backgrounds
- **Profile, Training, and Dweller Detail layouts** — Profile prioritizes the personnel file over secondary statistics;
  Training now uses the shared vault shell with a full-width queue and collapsible reference; Dweller Detail has a
  responsive profile rail and stacks before its record panel becomes cramped
- **UI regression coverage** — added focused tests for shared back navigation, Profile’s vault return, Exploration
  Detail sidebar, full-width Training layout/reference disclosure, and the revival card’s terminal surface
- **Version bump** — backend/frontend aligned at v2.33.0

### Measurement

- `env -C frontend ./node_modules/.bin/vp lint src` increased checked rules from **95** to **110** (**+15; 15.8%**)
  while retaining **0 warnings and 0 errors**. The baseline and final commands ran with Vite+ 0.2.7 on the locked
  frontend environment; final lint wall time was **0.84s**.

---

## [2.32.1] - 2026-08-12

### Fixed

- **AI chat availability** — exhausted OpenAI provider credits now return a clear HTTP 503 response without a
  redundant fallback request
- **Game ticks** — corrected high-SPECIAL production XP configuration and serialized overlapping same-vault event
  handling to prevent async database-operation collisions

---

## [2.32.0] - 2026-08-12

### Changed

- **Backend lint quality** — expanded Ruff coverage for performance, eradicated-comment, modernisation,
  type-checking, security, and Google-style docstring rules; resolved the newly enabled findings while preserving
  intentional project-specific exceptions
- **Version bump** — backend/frontend aligned at v2.32.0

---

## [2.31.0] - 2026-08-12

### Added

- **Bio-to-map registration reliability** — `map_service.register_bio_places` now retries once after a transient
  failure; if both attempts fail, it emits a durable `MAP_REGISTRATION_FAILED` notification instead of logging
  silently
- **Active-vault bio place backfill** — new `BioPlaceBackfillService` with
  `backfill_bio_places_for_vault` and `backfill_bio_places_for_active_vaults`; CLI script
  `scripts/backfill_dweller_bio_places.py` gained `--all-active`, `--max-dwellers`, and `--max-vaults` flags
- **Coverage threshold** — backend coverage is now 82.44%; new `--cov-fail-under=80` guard prevents regression
- **Frontend coverage reporting** — added Vitest coverage config via `@vitest/coverage-v8`; run with
  `pnpm run test:coverage` (current baseline: ~50% lines, ~49.5% statements)

### Changed

- **Service separation** — backfill logic and bio place extraction moved out of `map_service.py` into
  `app/services/bio_place_backfill_service.py`, keeping `MapService` focused on runtime registration and map
  assembly
- **CI/coverage split** — PR/push CI runs tests without coverage for speed; coverage reporting, badge generation,
  and the 80% floor now live in a separate nightly/master `backend-coverage.yml` workflow
- **Version bump** — backend/frontend aligned at v2.31.0

### Fixed

- **Per-dweller backfill isolation** — each dweller is committed independently during backfill so one
  registration failure cannot roll back earlier successful registrations in the same vault

---

## [2.30.0] - 2026-08-11

### Changed

- **Async action migration** — `docs/frontend/ASYNC_ACTION_MIGRATION.md` executed: loading and error actions centralized into Pinia stores for radio, notifications, chat, happiness, storage, equipment, relationships, dweller filter, training, and login; view-local loading duplication removed
- **Error surfacing** — replaced silent `console` diagnostics with surfaced store errors for room, vault, training, storage, unassign, profile, incident, and objective request failures
- **Polling → SSE fallback migrations** — exploration, combat modal, profile statistics, social/training, and incident polling migrated to SSE fallback patterns
- **Frontend type contract alignment** — shared UI variant contracts (`UButton`/`UInput`), accessibility attributes, dweller/room status contracts, exploration/quest views, room training/grid interactions, card clicks, map SVG attributes, chat and room actions, storage tab rendering, dweller appearance form, and vault contracts typed to pass truthful `vue-tsc` typecheck
- **View decomposition** — dwellers view decomposed into focused sub-components; chat message presentation split from chat logic
- **Exploration view refactor** — `WastelandPanel`/`ExplorationDetailView` split into `ExplorerNavbar`, `ExplorerSummaryCard`, `ExplorerStatsGrid`, `ExplorerEquipmentSlots`, `ExplorerActions`, `WastelandDropzone`, `ExplorationDurationModal`, and `ExplorationEventLog` components
- **Docs reorganization** — project docs moved under `docs/` (frontend README/STYLEGUIDE, ROADMAP, EXPLORATION_SYSTEM, TEST_COVERAGE_ANALYSIS, migration guides); added `docs/DEVELOPMENT.md`; repo guidance updated for the new layout
- **Version bump** — backend/frontend aligned at v2.30.0

### Fixed

- **NotificationBell reactivity** — fixed stale `shallowRef` ticking from the notification store; added regression test

---

## [2.29.0] - 2026-08-10

### Added

- **Dweller-location `is_unlocked` schema** — `DwellerLocationBase` gained `is_unlocked` boolean with Alembic migration and index; propagated through `DwellerRef`/`WastelandLocationWithDwellers` schemas and `map_service` with an optional `unlocked_only` filter plus a matching map endpoint query param
- **Unlock places on chat** — `chat_service` unlocks a dweller's wasteland places after 3+ user messages (new `unlock_places_for_dweller` CRUD and `count_user_messages_to_dweller` helper), applied in both `process_text_message` and `stream_response`
- **Frontend map unlock UI** — `MapMarker` locked state (lock icon, dashed outline, 50% opacity, "Unknown Location" label), `MarkerDetailModal` locked placeholder with chat hint, map store `unlockedPlacesCount` getter + `refreshMap` action, and chat-to-map refresh on send with a toast on newly unlocked locations
- **Phase 1 UI polish** — Login loading state (disabled button, AUTHENTICATING text, error-pulse animation), Dwellers `HappinessDashboard` loading skeleton + 480px single-column grid, Map marker hover glow, top-right zoom controls, responsive legend, and empty-state Recruit CTA

### Changed

- **Frontend dependency audit** — `pnpm-workspace.yaml` gained audit overrides for transitive CVEs (nanoid, undici, js-yaml, postcss, brace-expansion, esbuild, dompurify)

### Fixed

- **Playwright e2e config** — removed unsupported `--skip-types-generate` flag from the `webServer` command; updated side-panel nav expectations in `interaction.spec.ts` (Happiness removed, Map added)

---

## [2.28.0] - 2026-08-09

### Added

- **Template-based dweller bio filler** — `backend/scripts/fill_dweller_bios_templates.py`: one-off local script that fills empty dweller bios using SPECIAL-stat-driven templates, mentions an origin place and visited places in each bio, and registers those places on the vault world map via `map_service.register_bio_places`
- **Retro-active bio place backfill** — `backend/scripts/backfill_dweller_bio_places.py`: local script that scans dwellers whose bios contain place names but who have no map locations yet, extracts origin/visited places via word-boundary regex against the known place lists, and registers them via `map_service.register_bio_places`; supports `--vault` and `--max-dwellers` CLI args

### Changed

- **Rarity-scaled visited counts** — `backend/scripts/fill_dweller_bios_templates.py` now reads visited counts from `game_config.bio.visited_by_rarity` (common=2, rare=4, legendary=5) instead of hardcoded 1–2, and joins 3+ visited places with an Oxford comma
- **Sidebar consolidation** — Happiness nav item removed from `SidePanel.vue`; the aggregate `HappinessDashboard` now renders inside the Dwellers view above the filter panel, and the Map nav item gained hotkey `8`; the `/vault/:id/happiness` route is retained for deep links
- **Script layout & Typer standardization** — all backend Python scripts now live in `backend/scripts/` and are Typer CLIs (create_admin, backfill, bio filler, fix image URLs, set RustFS policies, quest migration, room-image downloader); `backend/initial_data.py` and `app/scripts/` were removed, `backend/scripts/README.md` documents each tool, and root `scripts/` is now shell-only (`dev-up.sh`, `backup-db.sh`, `redeploy-truenas.sh`)

---

## [2.27.0] - 2026-08-08

### Added

- **Balance simulator scripts** — exploration, happiness, and room balance simulation scripts for tuning game parameters
- **AI usage service tests** — full coverage for `AIUsageService` token aggregation, quota reporting, and edge cases (default/custom/zero/exceeded quotas, error logging)
- **Game loop tests** — expanded coverage for game tick processing, pause/resume, and tick orchestration
- **Vault service tests** — coverage for vault initialization, resource updates, and medical transfers
- **Dweller AI service tests** — comprehensive coverage for dweller AI decision-making and map interactions
- **Room CRUD tests** — coverage for room creation, validation, coordinate constraints, and vault attribute recalculation
- **Item base CRUD tests** — coverage for item listing, filtering, and CRUD operations
- **Relationship endpoint tests** — coverage for relationship CRUD and compatibility checks
- **Training endpoint tests** — coverage for training lifecycle endpoints
- **Objective assignment service tests** — coverage for objective assignment logic
- **Dweller assignment service tests** — coverage for room-based dweller assignment
- **Health check service tests** — expanded coverage for RustFS, Ollama, and infrastructure health checks
- **OpenAI service tests** — coverage for provider initialization (gateway/direct/ollama/disabled), image generation, and audio generation
- **pytest-xdist** — parallel test execution support with test markers and coverage exclusions

### Changed

- **Shared fakeredis client** — tests now share a single fakeredis instance across requests, reducing setup overhead and improving test reliability

### Fixed

- **Lint compliance in test files** — fixed FBT003 (boolean positional args in `patch.object`), SIM117 (nested `with` statements), RUF036 (`None` union ordering), E501 (line length), and I001 (import sorting) across test files

---

## [2.26.0] - 2026-08-07

### Added

- **PG enum drift regression tests** — `backend/app/tests/test_db/test_enum_drift.py`: CI-safe golden-snapshot test (`PG_ENUM_LABELS_SNAPSHOT` over 24 enum types) catching Python-side StrEnum member drift (added/removed/renamed), plus a live-PostgreSQL test comparing `pg_enum` catalog labels against model metadata to catch unapplied migrations (auto-skips on SQLite CI)

### Changed

- **AGENTS.md "DB Enums & Alembic Migrations"** — corrected the stale "offline-only `compare_type=True`" claim (commit `a252adab` enabled it in both offline and online modes); documented the manual enum-migration procedure and the regression-guard requirement (snapshot must be updated in the same commit as any enum migration)

### Fixed

- **Enum drift regression coverage gap** — the `DWELLER_DIED` production outage (Python enum member added without a PG migration → `InvalidTextRepresentationError` → poisoned pool) can no longer ship undetected; both drift directions (Python-side and DB-side) are now locked by tests
- **Random common dweller age coherence** — `create_random_common_dweller` rolled `is_adult` randomly but never set `age_group` (fell back to the `ADULT` model default) or `birth_date` (stayed `NULL`), and hardcoded `max_health=50` (the model default / child-level baseline) instead of the 100 used by every other creation path; now `age_group` + `birth_date` are derived coherently from the `is_adult` roll and health matches the adult baseline (regression from Andrea Freeman, vault 444)

---

## [2.25.0] - 2026-08-07

### Added

- **Marker list panel** — `MarkerListPanel` component with grouped marker list (home vault, origin, visited, discovery, vault signals), toggle button, total count, selected-row highlight
- **Map legend & terrain** — `MapLegend` (5 marker types), `TerrainLayer` procedural terrain (seeded `feTurbulence`), `spreadMarkers` deterministic layout utility
- **Map interactions** — `useMapZoomPan` zoom/pan composable with clamp + focus-pan, zoom controls overlay in `WorldMap`

### Changed

- **World map declutter** — low-value single-dweller `VISITED` locations hidden from the SVG map (kept in marker list panel + detail modal)
- **160×160 render world** — `WORLD_SCALE = 1.6` applied read-time in backend map paths (`map_service.py`), no DB migration; frontend world grid 0–160 with matching `viewBox`
- **Pregen service extraction** — bio/map seeding moved from CLI into `PregenService` (service layer); `fo-cli pregen-dwellers` + `fo-cli dweller-bios` are thin wrappers; deterministic `seed` threaded through `crud.dweller.create_random` / `create_random_common_dweller`
- **Map overlay tokens** — translucent overlay backgrounds use the `--color-surface` design token via `color-mix` instead of hardcoded `rgba(17,17,17,*)`

### Fixed

- **DwellerBio linkify** — place-name linkification now works on entity-encoded text (e.g. `R&amp;D Labs`); DOM-fragment TreeWalker linkifier, 27 tests
- **Map error handling** — DwellerDetailView routes map-fetch errors through `handleStoreError`; MapView `?place=` watcher covered by a reactive route-mock test

---

## [2.24.0] - 2026-08-07

### Added

- **World Map** — new `src/modules/map/` schematic map view (`GET /vault/:id/map`): SVG wasteland map with dweller bio-derived origin/visited markers, procedural exploration "discovery" markers, seeded "other vault" markers, marker detail modal, 30s polling store, SidePanel nav entry
- **Wasteland location domain** — `wasteland_location` + `dweller_location` tables, `locationtype` + `dwellerlocationrelation` PG enums, race-safe location CRUD (`crud/wasteland_location.py`), hand-written Alembic migration `edb924d8dbeb`
- **Map service** — `services/map_service.py`: bio place registration (origin + up to 5 visited), discovery registration, idempotent home marker at (50.0, 50.0), computed 3–7 seeded other-vault markers, `GET /api/v1/map/vault/{id}` + `GET /api/v1/map/locations/{id}` endpoints
- **Dweller bio places** — `DwellerBackstory`/`ExtendedBio` schemas now expose `origin_place` + `visited_places`; `dweller_ai.py` extracts them from generated bios; newborn dwellers get origin places on creation
- **Procedural discovery event** — new `discovery` exploration event type (flat 10% independent roll in `EventGenerator`, `discovery_names.json` data, existing event weights untouched)

### Changed

- **`exploration_event.py`** — `Exploration.add_event()` and coordinator `process_event()` accept optional `location_name`
- **`breeding_service.py`** — newborn dwellers linked to origin place markers
- **`api.generated.ts`** — regenerated with new map endpoints and types

### Fixed

- **API changelog staleness** — `CHANGELOG.md` restored as the source of truth for `GET /api/v1/system/changelog[/latest]` (it had lagged at 2.21.0 while the app was at 2.23.3; backfilled 2.22.0, 2.23.0, 2.23.1, 2.23.2, 2.23.3 sections from `docs/ROADMAP.md` and git history)

---

## [2.23.3] - 2026-07-13

### Changed

- **ABILITY_CONFIG reuse** — `RoomGridCell.vue` now imports shared `ABILITY_CONFIG` map (DRY consolidation; previously duplicated ability lookups in-grid and in-detail)
- **Dependency updates** — routine production dependency bumps across backend and frontend

---

## [2.23.2] - 2026-07-13

### Added

- **Shared `SpecialKey` type** — extracted `SpecialKey` union type and `ABILITY_CONFIG` constant map into a shared location, enabling reuse across `RoomGridCell`, `RoomGrid`, and dweller stats components

### Changed

- **RoomGridCell extraction** — `RoomGridCell.vue` extracted from `RoomGrid.vue` (928→548 lines), standalone component with typed props
- **`utils/image.ts` relocation** — moved from module-local to `core/utils/`, fixed 3 `any`-type violations

### Fixed

- **`DwellerStats.vue` type safety** — eliminated `as any` cast with typed `statValue` accessor

---

## [2.23.1] - 2026-07-13

### Changed

- **Vue 3.5 reactive destructure migration** — 30 components migrated from `withDefaults()` to Vue 3.5 reactive destructure pattern across core UI, vault, dweller, progression, social, storage, combat, profile, and rooms modules
- **Inline defaults** — all default values moved inline in destructure; factory defaults (`() => []`) replaced with `?? []` fallbacks
- **`props.X` references cleaned** — all `props.X` references in migrated files rewritten to direct variable access

---

## [2.23.0] - 2026-07-01

### Added

- **Chat WebSocket endpoint** — dedicated WebSocket endpoint for real-time dweller chat, replacing the previous POST-SSE streaming approach

### Changed

- **Axios→fetch migration** — executed 6-phase HTTP client migration from `docs/frontend/HTTP_CLIENT_MIGRATION.md`: fetch adapter, call-site migration, interceptor/token-refresh migration, dropped axios dependency (~14KB gzip bundle saving)
- **Version bump** — backend/frontend aligned at v2.23.0

### Removed

- **Chat SSE stub** — removed POST-SSE chat streaming endpoint from `stream.py` (superseded by WebSocket)

---

## [2.22.0] - 2026-06-28

### Added

- **UInput `variant="terminal"` prop** — transparent background styling option (`bg-transparent`, no border on non-hover) added to core UInput component
- **VaultNumberField component** — extracted vault-number-input logic from HomeView into a reusable component

### Changed

- **Auth form cleanup** — applied `variant="terminal"` to `LoginFormTerminal`, `RegisterForm`, `ForgotPasswordView`, and `ResetPasswordView` (removed grey surface backgrounds from auth forms)
- **HomeView simplification** — replaced inline UInput with `VaultNumberField`; removed dead duplicates
- **Version bump** — backend/frontend aligned at v2.22.0

---

## [2.21.0] - 2026-06-24

### Added

- **Incident SSE publishing** — `incident_service` now publishes SSE events (`incident_spawned`, `incident_resolved`, `incident_spreading`) on spawn, state transition, and resolution (3 TDD tests)
- **Incidents SSE endpoint** — `GET /stream/incidents/{vault_id}` with vault ownership check, heartbeat keepalive
- **Incident store SSE subscription** — `incident.ts` store replaces `setInterval` polling with SSE subscription; REST polling falls back after 30s SSE disconnect
- **Vault store game-tick SSE** — `vault.ts` store subscribes to `GET /stream/game/{vault_id}/ticks` for live resource updates; SSE auto-starts on vault load, stops on vault tab close
- **SSE auto-reconnect** — `useSseBase` now has exponential backoff reconnect (1s→2s→4s→...→30s max) on connection loss (10 tests)
- **`useSseBase` startPolling/stopPolling SSE integration** — Both incident and vault stores manage SSE lifecycle alongside existing polling

### Fixed

- **Radio recruitment PostgreSQL crash** — Replaced `datetime.now(UTC)` (timezone-aware) with `datetime.utcnow()` (naive UTC) in 3 locations in `dweller_recycling_service.py`; asyncpg no longer throws `DataError` on `TIMESTAMP WITHOUT TIME ZONE` columns
- **SSE heartbeat interval** — Moved hardcoded `_HEARTBEAT_INTERVAL = 30` to `Settings.SSE_HEARTBEAT_INTERVAL: int = 30`; game ticks stream uses `game_config.game_loop.tick_interval`
- **Removed dead `/stream/chat/{dweller_id}` POST-SSE endpoint** — 18 lines + 4 unused imports deleted from `stream.py`

### Changed

- **`dweller_recycling_service.py`** — All 3 `datetime.now(UTC)` calls replaced with `datetime.utcnow()`; import simplified
- **`stream.py`** — Added `stream_incidents` endpoint following exploration pattern; heartbeat now uses settings-driven value
- **`config.py`** — Added `SSE_HEARTBEAT_INTERVAL: int = 30` to `Settings`
- **`incident.ts` store** — Added `startSseSubscription`/`stopSseSubscription` with SSE event watcher (incident_spawned, incident_resolved, incident_spreading) and 30s disconnect fallback
- **`vault.ts` store** — Added `startGameTickSse`/`stopGameTickSse`; `loadVault`, `refreshVault`, `resumeVault` auto-bind SSE; `closeVaultTab` stops SSE

### Removed

- **Dead `/stream/chat/{dweller_id}` endpoint** — POST-based SSE endpoint removed from `stream.py` (chat migration to WebSocket pending)

---

## [2.20.0] - 2026-06-22

### Added

- **6-step YAGNI heuristic** — Added to AGENTS.md governing all FE work

### Changed

- **FE LOC reduction ~1500+ lines** — Deleted ~1000 LOC dead code (43 files: barrel re-exports, dead composables, unused UI components, aspirational infra)
- **DRY consolidation** — Merged useSse/usePostEventStream into useSseBase; merged WeaponCard/OutfitCard into EquipmentCard; consolidated room-destroy logic; CSS variables replace hardcoded hex colors
- **Barrel migration** — All legacy barrel imports (@/stores/_, @/models/_) migrated to @/modules/\* paths; 8 empty directories removed
- **Dweller store split** — dweller.ts (796 LOC) split into 5 focused stores (filter, generation, management, medical, death) with backward-compat facade
- **Component simplification** — DwellerCard: extracted DwellerCardActions + HappinessModifierPopover sub-components, dead-CSS cleanup

### Removed

- **Dead composables** — useTerminalAudio (326 LOC), useAuth, useFlickering, composables/index.ts barrel
- **Unused UI components** — ComingSoonBadge, UDropdown (104 LOC)
- **Aspirational infra** — api.ts wrapper (116 LOC), core/types/index.ts barrel, api/incident.ts dead duplicate

---

## [2.19.0] - 2026-06-21

### Added

- **SSE streaming infrastructure** — `SSEManager` singleton with per-user pub/sub queues. 4 SSE endpoints: notifications (`GET /stream/notifications`), game ticks (`GET /stream/game/{vault_id}/ticks`), AI chat tokens (`POST /stream/chat/{dweller_id}`), exploration events (`GET /stream/exploration/{vault_id}`).
- **Heartbeat keepalive** — `_with_heartbeat` wrapper yields comments every 30s of inactivity on GET SSE endpoints, preventing proxy timeouts.
- **Dual notification broadcast** — `NotificationService.send_notification` now publishes via both WebSocket and SSE. Frontend `NotificationBell.vue` replaced 30s polling with live SSE subscription (`useSse`).
- **Streaming AI chat** — `chat_service.stream_response()` yields token-by-token via `run_stream()`. Chat SSE endpoint streams tokens with `event: token`, then `event: done` with dweller_message_id and happiness_impact.
- **Game tick SSE publishing** — `process_vault_tick()` publishes tick results to SSE after each game tick. Duplicate SSE publish bug fixed with 3 regression tests.
- **Exploration SSE publishing** — `ExplorationCoordinator.process_event()`, `complete_exploration()`, and `recall_exploration()` publish live events to the `exploration` SSE topic.
- **Frontend SSE composables** — `useEventStream` (GET, wraps VueUse `useEventSource` with safe JSON parsing), `usePostEventStream` (POST, fetch-based with proper SSE protocol parser handling event/data/id fields), `useSse` (GET with Authorization headers for authenticated streams).
- **Stream manager tests** — 11 unit tests covering subscribe/publish, multi-subscriber, disconnect cleanup, queue full (best-effort), close/shutdown, broadcast_to_vault, and heartbeat passthrough/timeout.
- **Response schemas** — Added `GameBalanceResponse`, `HappinessModifiersResponse`, `DeathStatsResponse`, `UnassignResponse`, `AutoAssignResponse`, `DwellerAssignmentItem`, `QuestPartyMemberRead`, `EligibleDwellerRead` schemas.
- **`unequip_outfit`/`unequip_weapon` return types** — Added `response_model=None` and `-> None` type annotations.

### Fixed

- **Duplicate SSE publish in game loop** — `process_game_tick` no longer publishes SSE after `process_vault_tick` (which already publishes). Fixed with TDD (3 regression tests in `test_game_loop_sse.py`).
- **`usePostEventStream` SSE parsing** — Rewrote to properly parse `event:`, `data:`, `id:` fields, safe JSON parsing with fallback to raw text, and no hardcoded `[DONE]` sentinel (metadata preserved).
- **Lint warnings** — `stream_manager.py`: unused `after_id`/`vault_id` parameters renamed, unused loop variables prefixed. `stream.py`: `asyncio.TimeoutError` → `TimeoutError`, removed stale `noqa`.
- **Password validation** - Added `min_length=8` to `UserCreate.password` schema. Added client-side password length and email format validation to RegisterForm.
- **Game balance endpoint** — Added missing `dweller` and `exploration` fields to `GameBalanceResponse` construction.

### Changed

- **Dict → Pydantic schema refactoring** — Replaced `dict` return types with typed Pydantic schemas in 8+ endpoints: `get_game_balance_settings` (`GameBalanceResponse`), `get_happiness_modifiers` (`HappinessModifiersResponse`), `get_death_statistics` (`DeathStatsResponse`), vault auto-assign endpoints (`UnassignResponse`/`AutoAssignResponse`), quest party/eligible dweller endpoints (`QuestPartyMemberRead`/`EligibleDwellerRead`).
- **Schema unpacking** — 4 pregnancy endpoints switched from manual field mapping to `PregnancyRead.model_validate()`.
- **Service layer relocation** — Radio mode vault mutation moved from `radio.py` endpoint to `radio_service.set_radio_mode()`. CRUD exploration `get_by_vault`/`get_active_by_vault` consolidated into single `get_by_vault(active_only=False)`.
- **Auth endpoint return types** — 5 auth endpoints wired to existing `MessageResponse` schema.
- **Game control return type annotations** — Added `-> dict[str, Any]` to `get_game_state`, `manual_tick`, `resolve_incident`.
- **UI component accessibility** — Added `role=button`, `tabindex`, keyboard Enter/Space handlers to UDropdown. Added `role=dialog` and `aria-modal=true` to UModal. Added auto-generated `id` + label `for` association to UInput. Replaced inline `:style` color with `text-theme-primary` class on UCard.
- **Admin password** - Updated `backend/.env.example` password to meet `min_length=8` requirement.

---

## [2.18.0] - 2026-06-21

### Added

- **Library skills** — Added FastAPI, Typer, and Pydantic AI compliance skills from `uvx library-skills`. Added `.agents/skills/fastapi/SKILL.md`, `.agents/skills/typer/SKILL.md`, `.agents/skills/building-pydantic-ai-agents/SKILL.md`.
- **Router prefix/tags in APIRouter constructors** — Moved `prefix` and `tags` from `include_router()` into individual `APIRouter()` definitions across all 22 router files. Cleans up `api.py` router registration.
- **`ChatMessage` schema** — Moved request model from `chat.py` endpoint to `schemas/chat.py`.
- **`ChatService.send_chat_notification()`** — Moved `_send_chat_notification` helper from endpoint to service layer as a static method.

### Changed

- **Annotated dependency style** — Standardized 12 endpoint params and 6 shared deps to `Annotated[Type, Depends()]` pattern in `deps.py` and 9 endpoint files.
- **Return type annotations** — Added explicit return type annotations to ~108 endpoint functions across all 22 endpoint files.
- **Nested try-except extraction** — Extracted `_extract_usage()` helpers in `chat_service.py` and `conversation_service.py`. Extracted `_send_chat_notification()` in `chat.py`.
- **Async safety** — Wrapped sync S3/storage/OpenAI calls with `asyncio.to_thread()` in `open_ai.py`, `dweller_ai.py`, `conversation_service.py`, and `exploration/coordinator.py`.
- **Version bump** — Backend 2.17.0 → 2.18.0, frontend 2.17.0 → 2.18.0.

### Fixed

- **Chat endpoint nested try-except** — `_send_chat_notification` was nested inside the main `try` block in `voice_chat_with_dweller`; extracted to a helper called after the try block.

### Removed

- **Stale documentation** — Deleted `docs/archive/` (8 outdated planning docs from v2.4–v2.6) and `docs/TWELVE_FACTOR_COMPLIANCE.md` (Jan 2026 one-time audit).
- **Irrelevant skills** — Removed `tsdown/` (library bundler, not used) and `zod-v4/` (leftover).
- **Duplicate skills** — Removed `backend/.agents/skills/` copies of fastapi, typer, and building-pydantic-ai-agents (exact duplicates of root copies).

---

## [2.17.0] - 2026-06-19

### Added

- **Storage model medical fields** — Added `stimpack` and `radaway` fields to `StorageBase`. Alembic migration `abc123def456` copies existing data from vault to storage and drops the 4 legacy vault columns.
- **Medical production config** — Added `MEDICAL_ROOM_PRODUCTION` mapping (medbay→stimpak, science lab→radaway) and `compute_medical_capacity()` to `game_config.py`. Capacity is now computed dynamically from rooms instead of stored on the vault.
- **StorageView medical display** — Added `stimpack`/`radaway` fields to `StorageSpaceResponse` endpoint. StorageView now reads stimpak/radaway counts from storage API instead of removed vault fields.

### Changed

- **Resource manager** — Medical production (`_apply_room_production`) uses `MEDICAL_ROOM_PRODUCTION` config mapping instead of string matching. Writes stimpaks/radaways to Storage, capped by `compute_medical_capacity`.
- **Vault service** — Room build no longer updates `stimpack_max`/`radaway_max` on vault. Vault init writes initial medical supplies to Storage. `transfer_medical_supplies` reads/writes Storage instead of vault fields.
- **Exploration service** — `send_dweller` deducts stimpaks/radaways from Storage. Unused supplies returned on recall are written to Storage, capped by computed capacity.
- **Vault CRUD** — Removed `stimpack_max`/`radaway_max` special-casing in `_handle_production_room`.
- **Vault model** — Removed `stimpack`, `stimpack_max`, `radaway`, `radaway_max` fields.
- **Version bump** — Backend 2.16.0 → 2.17.0, frontend 2.16.0 → 2.17.0.

### Removed

- **Legacy vault medical fields** — `stimpack`, `stimpack_max`, `radaway`, `radaway_max` no longer exist on the Vault model. Stimpack/radaway data lives exclusively on Storage.

---

## [2.16.0] - 2026-06-18

### Added

- **UModal focus trap** — Hand-rolled (no new deps) with Tab cycling, Escape close, focus restore.
- **`role="button"`/`tabindex`/keyboard handlers** — Added to 13 clickable elements across 8 files.
- **`aria-label` attributes** — Added to 8 icon-only buttons in dwellers and rooms modules.
- **ARIA on inline modals** — Added `role="dialog"`, `aria-modal`, escape-key close to DwellerEquipment and RoomMenu.
- **Module READMEs** — Added 12 `README.md` files in `frontend/src/modules/` (auth, vault, dwellers, rooms, etc.).
- **Nuxt UI migration plan** — Added `.omo/drafts/nuxt-ui-migration-plan.md`.

### Changed

- **Auth forms migrated to UButton/UInput** — `LoginFormTerminal`, `RegisterForm`, `ForgotPassword`, `ResetPassword`, `VerifyEmail` now use home-grown UI components instead of raw `<button>`/`<input>`.
- **HomeView vault creation form** — Migrated to `UButton`/`UInput`.
- **CSS variable migration** — ~45 files: hardcoded hex colors in scoped CSS replaced with CSS variables (`--color-theme-primary`, `--color-danger`, etc.).
- **UButton `type` prop** — Added `type` prop (`button`/`submit`/`reset`) for form submit support.

### Fixed

- **12 skipped backend tests** — Fixed and now passing (quest datetime, 6 bare-skips, 3 incident assertions, 2 room session-race).
- **VerifyEmailView theme color** — Replaced nonstandard `--theme-color` with canonical `--color-theme-primary`.
- **LoginForm.vue dead code** — Deleted (route uses `LoginFormTerminal.vue`).
- **`fix-changelog-freeze.md` dropped** — Superseded; fix shipped in v2.14.4.

---

## [2.15.0] - 2026-06-18

### Added

- **Dweller Visual Unification** — Merged `DwellerVisualAttributesInput` (user-facing), `DwellerVisualAttributes` (AI output), and `VisualAttributes` (frontend) into a single 22-field schema with canonical field names (`hair_style`, `build`).
- **Race/Faction-aware AI agent** — The visual attributes agent now receives race and faction context, generating lore-appropriate appearances (ghoul skin/scarring, super mutant builds, synth metallic features).
- **Race/faction display in frontend** — `DwellerAppearance.vue` now shows Race, Faction, State of Being, plus all new fields.
- **Default visual attributes** — New dwellers get `{race: human, faction: vault_dweller}` on creation.
- **Manual appearance editor** — `DwellerAppearanceEditor.vue` modal with race-filtered dropdowns for all 22 visual fields, plus a Randomize button.
- **Portrait regeneration** — `POST /dwellers/{id}/generate_photo/?force=true` allows regenerating portraits after editing appearance.
- **Options data module** — Added `backend/app/options/` with race/faction/appearance/item/scene data ported from `fallout-avatar` project.

### Changed

- **Schema unification** — Removed duplicate `DwellerVisualAttributes` from `schemas/dweller_ai.py`; all usages now import from `schemas/dweller.py`. `DwellerVisualAttributesInput` kept as backward-compat alias.
- **AI enrichment flow** — `_has_substantial_visual_attributes()` helper allows AI generation to enrich minimal identity defaults without blocking.
- **Generate/Edit button logic** — "Generate" button only appears when AI can still enrich; "Edit" appears once any attributes exist.
- **Frontend types regenerated** — OpenAPI types now include `DwellerVisualAttributes` with all 22 fields.

### Fixed

- **RustFS bucket policies** — Ran `set_rustfs_bucket_policies.py` to enable public read on `dweller-images`, `dweller-thumbnails`, `dweller-audio`.
- **Editor theming** — Replaced hardcoded green colors with CSS theme variables.
- **Editor field backgrounds** — Changed from semi-transparent to solid black with `appearance: none` on selects.

---

## [2.14.4] - 2026-06-17

### Security

- **Frontend dep bumps** - Bumped `dompurify` to 3.4.11, `form-data` to 4.0.6, `js-yaml` to 4.2.0 to fix Dependabot advisories:
  - dompurify: multiple sanitization bypasses, Trusted Types poisoning, IN_PLACE mode issues
  - form-data: CRLF injection via unescaped multipart field names
  - js-yaml: Quadratic-complexity DoS in merge key handling

- **Backend dep bumps** - Bumped `python-multipart` to 0.0.32, `aiohttp` to 3.14.1 to fix Dependabot advisories:
  - python-multipart: CVE-2025-22140 (header leading to unlimited buffer copy)
  - aiohttp: CVE-2024-52304, CVE-2024-52303, CVE-2024-52302 (request smuggling, x-xss-protection bypass, DOS via empty multipart)
