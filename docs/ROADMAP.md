# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:**

- [x] **v2.32.0 planning** — Ruff lint cleanup + Google-style docstring convention enforcement.
- [x] **v2.33.0 released** — Frontend type-aware linting and stale-request safety.
- [x] **v2.33.2 patch released** — Automatic training-room assignments now create queue-visible training sessions.
- [x] **v2.34.0 released** — Pydantic AI observability and structured-output reliability.
- [x] **v2.35.0 released** — Automated release-version synchronization and Conventional Commit enforcement.

---

## Planned

### Next Gameplay Balance Iteration — Resource Economy Baseline

**Focus**: Make the existing 60-second resource tick create understandable staffing pressure before tuning broader
economy systems.

- ✅ **Define a starter-vault baseline** — two matching production workers are safe; reassigning one creates a
  recoverable deficit on the next tick. See `docs/features/RESOURCE_ECONOMY_BALANCE.md` for the targets and tuning
  sequence.
- 🔄 **Calibrate production first** — reduce only the base production rate for the first pass; preserve room output
  formulas, consumption, capacity, prices, thresholds, and rewards until live play-testing identifies the next lever.
- 🔄 **Tune in isolated passes** — evaluate starter staffing, then population bands, then room tiers; change one
  economic input per cycle and record the observed outcome.

**Success criteria:** a player can see a resource trade-off within one 60-second tick, restore a healthy vault by
staffing matching rooms, and identify the next expansion or training decision from the resource-rate feedback.

---

### v2.34.0 — Pydantic AI Reliability & Observability (Target: TBD)

**Focus**: Make existing dweller agents easier to debug and more reliable at the boundary between structured model
output and gameplay actions. Keep this as one backend/AI release instead of splitting several small library adoptions.

**In progress:**

- ✅ **Trace Pydantic AI runs in Logfire**
  - When Logfire is configured, instrument Pydantic AI in addition to the existing application setup so agent runs,
    tool calls, retry counts, latency, and token usage are visible in one trace.
  - The disabled/no-token path remains a no-op; instrumentation explicitly uses `include_content=False` so prompt
    content is excluded from traces. Unit coverage verifies both paths without using a provider token.
- ✅ **Harden the dweller chat output contract**
  - Migrate agents that do not pass message history from `system_prompt` to static/dynamic `instructions`; preserve
    `system_prompt` only where history retention is intentional.
  - Add output validation/retry rules for action-field combinations before gameplay code consumes them (for example,
    required room data for room assignment and no action payload for `no_action`).
  - Added deterministic `TestModel` coverage for instructions, room-recommendation tool execution, invalid structured
    output retries, and recorded token usage; existing chat-service coverage protects fallback behaviour.
- ✅ **Keep optional RustFS from delaying backend startup**
  - Skip the optional S3 probe during startup; detailed health checks still report RustFS availability.
  - Treat unreachable Botocore endpoints as degraded storage health, with short single-attempt diagnostic probes.
  - Allow core gameplay to run without RustFS configuration and cover the endpoint-connection path with regression tests.
- ✅ **Ground dweller activity suggestions in live gameplay state**
  - Add a read-only activity briefing tool that reports active training/exploration, trainable rooms and capacity,
    available medical supplies, and a bounded exploration pack before the agent suggests a training or wasteland action.
- 🔄 **Activate Pydantic AI Gateway for chat and agents**
  - Configure the deployment-only `PYDANTIC_AI_GATEWAY_API_KEY`; the existing gateway model path becomes active without
    changing agent code.
  - Retain `OPENAI_API_KEY` for native image, TTS, and transcription APIs, which remain direct OpenAI integrations.
- 🔄 **Measure before/after**
  - Baseline and report deterministic agent-contract test count, output-validation retry coverage, and Logfire trace
    completeness for one normal chat and one tool-using chat.
  - Guardrails: no agent framework major-version migration, no gameplay-rule change, and no real-provider calls in the
    unit test suite.

---

### v2.35.0 — Release Version Integrity (Released 2026-08-14)

**Focus**: Make the SemVer Git tag the single release authority. Eliminate manual, separately committed backend and
frontend version bumps, and make release eligibility deterministic from validated Conventional Commit metadata.

**Engineering constraint (v2.35 onward):** Every update must reduce net source LOC. Features that require new code
must first offset it by removing or compacting existing code, favoring DRY reusable extraction over duplication. The
reduction excludes generated files, lockfiles, and formatting-only changes, and must retain behavior under relevant
tests.

**Completed:**

- ✅ **One automated release version**
  - Have Semantic Release calculate the next version, synchronize `backend/pyproject.toml`, `backend/uv.lock`, and
    `frontend/package.json` in its prepare phase, then commit those generated release artifacts before creating the
    `vX.Y.Z` tag.
  - Reconcile the existing manual-release history by validating and tagging the current `v2.34.3` state as the
    migration baseline; do not retroactively invent missing release versions.
  - Remove manual version-bump commits from the normal feature workflow; agents must not choose a release number.
- ✅ **Enforce release intent at merge time**
  - Require Conventional Commit PR titles and squash merges; the resulting `master` commit is the sole input to
    SemVer calculation.
  - Map `feat` to minor, `fix`/`perf`/`refactor` to patch, and `!`/`BREAKING CHANGE` to major; keep
    `docs`, `test`, `chore`, `ci`, and `style` non-releasing.
  - Use human-readable, lower-kebab branch names such as `feat/ai-observability`; branch names provide context only
    and must not encode or determine a version.
- ✅ **Build and verify the release pair**
  - Build and publish both backend and frontend Docker images from the release tag, using the tag's version for both
    image families rather than independently reading manifests on ordinary `master` pushes.
  - Add a CI guard that fails when the release tag, backend package version, frontend package version, or newest
    changelog heading disagree.

**Success criteria:** a release creates exactly one versioned commit and tag, both deployable images carry that same
version, and CI rejects divergent metadata before publication.

---

### Next Automated Release — Container Build Efficiency (Target: TBD)

**Focus**: Make release image builds faster and measure runtime-image size without changing deployment behavior.

**Planned:**

- 🔄 **Maximize reusable build cache** — replace the inline cache with a per-image registry cache in `mode=max` so
  dependency and intermediate multi-stage layers are reusable across ephemeral GitHub Actions builders.
- 🔄 **Measure before changing runtimes** — record cold and warm frontend/backend build-and-push durations plus
  published image sizes; `v2.35.0` is the initial timing baseline (26s frontend and 51s backend build-and-push).
- 🔄 **Reduce only demonstrated runtime overhead** — assess direct ownership on `COPY` for the backend and a minimal
  static frontend server only after smoke tests prove unchanged SPA routing and container behavior.

**Success criteria:** record exact before/after frontend and backend build-and-push durations plus published image
bytes, with the CI run or command used for each measurement; improve at least one metric without weakening tag
validation, cache isolation, or runtime behavior.

---

### Deferred Library Adoption (Reassess During a Related Feature)

- **FastAPI** — native SSE is already used; do not introduce `app.frontend()` for the separately deployed Vue SPA.
- **Pydantic / SQLModel** — the current PATCH flow already uses `exclude_unset=True`; consider `MISSING` only when an
  API genuinely needs to distinguish omitted values from explicit `null`, and use `sqlmodel_update()` only when
  touching the shared CRUD update path for another reason.
- **Tailwind CSS** — use newer semantic utilities such as native text shadows, safe alignment, pointer variants, or
  `@source inline()` only in the component that needs them. Avoid a formatting-only CRT-style rewrite.

## Latest Release

### Measurable Release Policy (v2.31.0+)

Each release has one or two focused improvement areas and publishes the measured result. A release must improve at
least one of the following without regressing features, readability, accessibility, or correctness:

- startup/load time, endpoint latency, throughput, or test runtime;
- memory footprint or bundle size;
- code quality, including meaningful LOC reduction, complexity reduction, coverage, or static-analysis findings;
- security, such as a remediated vulnerability, a hardened trust boundary, or new automated security coverage.

Release notes must state the baseline, the after value, the measurement method/environment, and the absolute and
percentage change. Claims must be reproducible from committed commands or CI artifacts. Do not report LOC reduction
as an improvement unless the release retains equivalent behaviour and test coverage. If the release is primarily a
feature delivery, record its measurable non-functional impact rather than inventing an optimization claim.

### v2.33.2 — Training Queue Assignment Repair (Released 2026-08-13)

**Fixed:** Auto-assigning dwellers to training rooms previously set their status to `training` without creating an
active training session. Assignment now delegates to `TrainingService`, keeping progression, duration, and the Training
Queue synchronized. `test_auto_assign_training_room_sets_training_status` protects this invariant.

### v2.33.0 — Frontend Type Safety & Async Correctness (Released 2026-08-13)

**Focus**: Enable compatible type-aware frontend linting and make filter-driven dweller requests safe against stale
responses without changing gameplay behaviour.

**Completed:**

- ✅ **Type-aware Vite+/Oxlint** — enabled bundled type-aware linting with the pinned TypeScript 6.x toolchain;
  retained the independent `vue-tsc` gate and added no standalone Oxc dependencies or TypeScript/Pinia upgrades.
- ✅ **Promise-safety cleanup** — resolved all 15 type-aware findings (13 `no-floating-promises` and 2
  `no-redundant-type-constituents`), leaving the type-aware lint gate at zero warnings/errors.
- ✅ **Async watcher cleanup** — dweller filter/sort watcher requests now use `AbortController` cleanup; filtered,
  modal-room, and dead-dweller stores accept only the most recent response. Regression coverage proves late obsolete
  responses cannot replace newer results.
- ✅ **Navigation consistency** — Profile, Dweller Detail, and exploration navigation share one labelled terminal
  back control.
- ✅ **Measurement** — `env -C frontend ./node_modules/.bin/vp lint src` increased active rules from **95** to
  **110** (**+15; 15.8%**) while retaining **0 warnings and 0 errors**. Final lint wall time was **0.84s** with
  Vite+ 0.2.7 in the locked frontend environment. `vue-tsc` and the frontend suite passed (93 files; 1,180 passed,
  1 skipped).

### v2.32.0 — Ruff Lint Cleanup & Google-Style Docstrings (Released 2026-08-12)

**Focus**: Strengthen backend static analysis while adopting Google-style docstrings for the public API surface.

**Completed:**

- ✅ **Higher-signal Ruff coverage** — enabled `PERF`, `ERA`, `FURB`, `TC`, `S`, and `D`; removed no-longer-needed
  suppressions and fixed the newly actionable findings while retaining explicit, documented project exceptions.
- ✅ **Google-style docstrings** — configured Ruff's Google convention and documented public API interfaces; code areas
  not yet migrated are explicitly excluded through scoped per-file ignores.
- ✅ **Release alignment** — backend/frontend versions and the changelog are aligned at v2.32.0.
- ✅ **Measurement** — `cd backend && uv run ruff check . --select ALL --statistics` reduced findings from **11,081**
  (baseline: commit `f97e2597a58426f6fa3a4ce498ec000e7e4a62bf`) to **6,416**: **4,665 fewer findings (42.1%)**. Both
  measurements used `uv 0.11.24`, the locked project environment on Python 3.13.13, and Ruff 0.16.2 with the command
  above. The final configured gate, `cd backend && uv run ruff check .`, passes.
- ✅ **Completed scope** — merged #419, #411, and #410; retained TypeScript 6.x / Pinia 3.x after deferring Pinia
  4.0.2; enabled higher-signal Ruff rules and Google-style docstrings in scoped phases; and kept tests, CLI, Alembic,
  and unmigrated modules under explicit per-file policy until their migration is complete.

### v2.31.0 — Bio-to-Map Registration Reliability (Released 2026-08-12)

**Focus**: Ensure a dweller's bio places are never silently absent from the world map after a registration failure, and
provide a way to retroactively fill gaps for existing active vaults.

**Completed:**

- ✅ **Retry + durable failure signal** — `map_service.register_bio_places` now retries once and emits a
  `MAP_REGISTRATION_FAILED` notification when both attempts fail; no longer log-only.
- ✅ **Retroactive active-vault backfill** — New `BioPlaceBackfillService` with
  `backfill_bio_places_for_vault` and `backfill_bio_places_for_active_vaults`; CLI script supports
  `--all-active`, `--max-dwellers`, and `--max-vaults`.
- ✅ **Service separation** — Backfill logic lives in its own service so `map_service.py` remains focused on
  runtime registration and map assembly.
- ✅ **Tests** — `test_bio_place_backfill_service.py` covers place extraction, single-vault backfill,
  max-dwellers limit, and deleted-vault exclusion; script CLI tests updated.
- ✅ **Coverage 80%+ achieved and enforced** — Current backend coverage is 82.44%. The fast PR/push CI
  no longer runs coverage; a separate nightly/master coverage workflow runs with `--cov-fail-under=80`.

### v2.30.0 — Frontend Refactor (August 11, 2026)

**Focus**: Simplify and harden the Vue frontend without changing backend runtime behavior.

**Completed:**

- ✅ **Truthful frontend checks** — typecheck and module-boundary checks are enforced in CI
- ✅ **Shared async behavior** — polling and async actions centralize loading and error handling
- ✅ **View simplification** — major dweller, chat, exploration, and room views use focused components
- ✅ **UX polish** — user-facing errors surface through toasts; loading and empty states are consistent
- ✅ **Version bump** — backend/frontend aligned at v2.30.0

### v2.26.0 — Alembic Enum Sync & Regression Coverage (August 7, 2026)

**Focus**: Close the enum-drift gap that caused the `DWELLER_DIED` production outage — verify no drift exists today, then lock it with regression tests

**Completed:**

- ✅ **Zero-drift audit** — `alembic check` clean (no pending operations); live `pg_enum` catalog matches model metadata exactly (24 enum types); `compare_type=True` confirmed active in both offline and online modes
- ✅ **Enum regression tests** — `backend/app/tests/test_db/test_enum_drift.py`: CI-safe golden-snapshot test (`PG_ENUM_LABELS_SNAPSHOT`) catching Python-side StrEnum drift + live-PG test (auto-skips without PostgreSQL) querying `pg_enum` to catch unapplied migrations; drift-detection proven by negative test
- ✅ **AGENTS.md docs fix** — Corrected stale "offline-only `compare_type=True`" claim (commit `a252adab` enabled it in both modes); documented the manual enum-migration procedure + regression guard requirement
- ✅ **Dweller age-coherence fix** — `create_random_common_dweller` now derives `age_group` + `birth_date` from the `is_adult` roll (was: random `is_adult` with `age_group` falling back to `ADULT` and `birth_date` `NULL`) and uses `max_health=100` (adult baseline, matching the breeding path) instead of the hardcoded 50; regression tests in `test_crud/test_dweller.py`
- ✅ **Version bump** — Backend/frontend aligned at v2.26.0

### v2.25.0 — Map Declutter & Dweller Data Integrity (August 7, 2026)

**Focus**: Hide low-value single-dweller visited markers from the wasteland map, widen the render world to 160×160 via read-time scaling, and harden dweller bio/map seeding

**Completed:**

- ✅ **Map declutter** — Low-value single-dweller `VISITED` locations hidden from the SVG map (kept in the new marker list panel + detail modal); `MarkerListPanel`, `MapLegend`, `TerrainLayer` components, marker spread/zoom-pan/terrain utilities
- ✅ **160-world read-time scaling** — `WORLD_SCALE = 1.6` applied in backend map read paths (`map_service`), no DB migration; frontend world grid 0–160 with matching `viewBox`
- ✅ **Pregen service extraction** — Bio/map seeding moved from CLI into `PregenService` (service layer); `fo-cli pregen-dwellers` + `fo-cli dweller-bios` are thin wrappers; deterministic `seed` threaded through `crud.dweller.create_random` / `create_random_common_dweller` (`random.Random` + `Faker.seed_instance`)
- ✅ **DwellerBio linkify fix** — Place-name linkification now works on entity-encoded text (e.g. `R&amp;D Labs`); DOM-fragment TreeWalker linkifier, 27 tests
- ✅ **Review fixes** — DwellerDetailView routes map-fetch errors through `handleStoreError`; MapView `?place=` watcher covered by a reactive route-mock test

### v2.24.0 — World Map (August 7, 2026)

**Focus**: Schematic wasteland map with dweller bio-derived markers, procedural exploration discoveries, and seeded vault locations

**Completed:**

- ✅ **Map domain models** — `WastelandLocation` + `DwellerLocation` tables, `locationtype` + `dwellerlocationrelation` PG enums, hand-written Alembic migration `edb924d8dbeb`
- ✅ **Place utilities** — `places.py`: name normalization, deterministic coordinate hashing, collision nudge, vault seed generation (pure stdlib, no DB/RNG)
- ✅ **Discovery event** — new `discovery` exploration event type at 10% independent roll, `discovery_names.json` data
- ✅ **Race-safe CRUD** — `wasteland_location.py` with get-or-create (IntegrityError rollback pattern), idempotent dweller linking, batched dweller refs
- ✅ **Map service** — bio place registration (origin + up to 5 visited), discovery registration, idempotent home marker, computed vault markers
- ✅ **Bio place extraction** — `DwellerBackstory`/`ExtendedBio` schemas expose `origin_place`/`visited_places`; `dweller_ai.py` extracts from generated bios
- ✅ **Server-side hooks** — discovery registration in exploration coordinator, newborn origin link in breeding service (best-effort, non-blocking)
- ✅ **Map API endpoints** — `GET /api/v1/map/vault/{id}` + `GET /api/v1/map/locations/{id}` with vault ownership checks
- ✅ **Frontend data layer** — `map.ts` models, `mapService.ts`, `useMapStore` (30s polling), regenerated `api.generated.ts`
- ✅ **Frontend map UI** — `WorldMap.vue` (SVG 100×100 grid), `MapMarker.vue` (type-color-coded), `MarkerDetailModal.vue`, `MapView.vue` (vault-shell layout)
- ✅ **Frontend wiring** — route registration (`/vault/:id/map`), SidePanel nav entry (icon: `mdi:map`), module README

### v2.23.1 — Vue 3.5 Reactive Destructure Migration (July 13, 2026)

**Focus**: Migrate 30 components from `withDefaults()` to Vue 3.5 reactive destructure pattern

**Completed:**

- ✅ **30 components migrated** — Replaced `const props = withDefaults(defineProps<Props>(), {...})` with `const { ... } = defineProps<Props>()` across core UI, vault, dweller, progression, social, storage, combat, profile, and rooms modules
- ✅ **Reactive destructure defaults** — All default values moved inline in destructure; factory defaults (`() => []`) replaced with `?? []` fallbacks where needed
- ✅ **`props.X` references cleaned** — All `props.X` references in migrated files rewritten to direct variable access for both script and template
- ✅ **TypeScript types preserved** — All type safety maintained; `vue-tsc --noEmit` passes clean; Oxlint 0 warnings

---

### v2.23.0 — Chat WebSocket Migration (July 1, 2026)

**Focus**: Chat WebSocket migration

**Completed:**

- ✅ **Chat REST→WebSocket migration** — Replaced POST-SSE chat streaming with dedicated WebSocket endpoint; removed chat SSE stub from stream.py
- ✅ **Version bump** — Backend/frontend aligned at v2.23.0

---

### v2.22.0 — Terminal Background Cleanup (June 28, 2026)

**Focus**: Remove grey surfaces from auth forms, create reusable VaultNumberField component

**Completed:**

- ✅ **UInput `variant="terminal"` prop** — Added transparent background styling option to core UInput component (`bg-transparent`, no border on non-hover)
- ✅ **Auth form cleanup** — Applied `variant="terminal"` to LoginFormTerminal, RegisterForm, ForgotPasswordView, and ResetPasswordView
- ✅ **VaultNumberField component** — Extracted vault-number-input logic from HomeView into a reusable component
- ✅ **HomeView simplification** — Replaced inline UInput with VaultNumberField; removed dead duplicates
- ✅ **Version bump** — Backend/frontend aligned at v2.22.0

---

### v2.21.0 — SSE Polish (June 24, 2026)

**Focus**: Real-time SSE for incidents and game ticks, radio recruitment PostgreSQL fix

**Completed:**

- ✅ **Incident SSE publishing** — Incident service publishes via SSE (3 TDD tests)
- ✅ **Incidents SSE endpoint** — `GET /stream/incidents/{vault_id}` with vault ownership check
- ✅ **Incident store SSE subscription** — Replaced `setInterval` polling with SSE; 30s fallback on disconnect
- ✅ **Vault store game-tick SSE** — Live resource updates via SSE; lifecycle bound to vault load/close/play-pause
- ✅ **`useSseBase` auto-reconnect** — Exponential backoff (1s→2s→4s→...→30s max)
- ✅ **Radio recruitment fix** — `datetime.now(UTC)` → `datetime.utcnow()` stops PostgreSQL `DataError`
- ✅ **SSE heartbeat configurable** — `SSE_HEARTBEAT_INTERVAL` setting
- ✅ **Dead code removal** — Removed dead POST-SSE `/stream/chat/{dweller_id}` endpoint

---

### v2.20.0 — FE Simplification (YAGNI + DRY) (June 22, 2026)

**Focus**: Reduce frontend complexity, remove dead code, consolidate DRY violations, migrate barrel imports

**Completed:**

- ✅ **6-step YAGNI heuristic** — Added to AGENTS.md governing all FE work
- ✅ **~1500 LOC reduction** — Deleted ~1000 LOC dead code across 43 files
- ✅ **DRY consolidation** — Merged useSse/usePostEventStream into useSseBase; merged WeaponCard/OutfitCard into EquipmentCard
- ✅ **Barrel migration** — All legacy barrel imports migrated to @/modules/\* paths
- ✅ **Dweller store split** — dweller.ts (796 LOC) split into 5 focused stores
- ✅ **Dead composables removed** — useTerminalAudio (326 LOC), useAuth, useFlickering, composables/index.ts barrel
- ✅ **Unused UI removed** — ComingSoonBadge, UDropdown (104 LOC)
- ✅ **Aspirational infra removed** — api.ts wrapper (116 LOC), core/types/index.ts barrel, api/incident.ts dead duplicate

---

## Planned Features (Future)

### Phase 1: Core Gameplay

- Room management improvements (optimal dweller suggestions)
- Crafting system (weapons/outfits with recipes)

### Phase 2: Advanced Gameplay

- Combat enhancements (statistics, log/replay)
- Exploration enhancement (events with choices, journal)
- Family visualization (relationship graph, family tree)

### Phase 3: Endgame

- Pet system, legendary dwellers
- Merchant system, economy
- Achievement system, daily/weekly challenges
- **Dead Dweller Reuse System**
  - Soft-delete permanently dead dwellers (keep data)
  - Reuse as raiders attacking other vaults
  - Transformation chance: ghoul, synth, super mutant
  - Cross-vault encounters with former dwellers

### Phase 4: Multiplayer

- Social features (friends, vault visits, leaderboards)
- Cloud saves, multi-device sync

---

## Technical Debt

### Backend

- [x] Router consolidation: Merge small routers into logical groupings
- [x] MinIO → RustFS migration
- [x] Alembic enum sync — `compare_type=True` in online mode
- [ ] Performance testing: Locust in nightly CI
- [ ] Datetime consistency: Migrate all `datetime.utcnow()` to aware `datetime.now(UTC)`
- [x] Test coverage target 80% — achieved 82.44%; enforced via nightly/master coverage workflow with `--cov-fail-under=80`

### Frontend

- [x] Vue architecture refactor → COMPLETED (v2.1.0)
- [ ] Component refactoring: Break down large components (DwellerCard, RoomGrid)

### DevOps

- [x] Docker build automation → COMPLETED
- [ ] Deploy immutable images: build and promote commit-SHA tags; production deployments select an explicit tested tag,
      never `latest`
- [ ] Run database migrations as a dedicated, pre-rollout Kubernetes Job and abort deployment if it fails
- [ ] Add migration safety checks to backend CI (`alembic check` and `alembic current --check-heads` against PostgreSQL)
- [ ] Add deterministic seed data and critical Playwright journeys, including stable visual regression baselines
- [ ] Test the rollback workflow against a known image tag; automate staging while retaining manual production approval

---

## Progress Metrics

### Current Stats (Aug 2026)

- **Backend**: 25+ routers, 100+ endpoints, 19+ services, **82.44% coverage**
- **Frontend**: 60+ Vue components, 10 feature modules
- **Tests**: Frontend 867+, Backend 1500+
- **Models**: 20+ database models

### Version Milestones

| Version | Release      | Highlights                                                        |
| ------- | ------------ | ----------------------------------------------------------------- |
| v2.32.0 | Aug 12, 2026 | Ruff rule cleanup + Google-style docstrings                       |
| v2.31.0 | Aug 12, 2026 | Map registration retry + failure notification, bio backfill fixes |
| v2.30.0 | Aug 11, 2026 | Frontend refactor (async actions, SSE fallback, typecheck)        |
| v2.29.0 | Aug 10, 2026 | Map unlock on chat, dweller-location `is_unlocked`, UI polish     |
| v2.28.0 | Aug 09, 2026 | Template-based bio filler + retroactive bio place backfill        |
| v2.27.0 | Aug 2026     | Test coverage push, pytest-xdist speed-up                         |
| v2.26.0 | Aug 07, 2026 | Alembic enum sync + PG enum regression tests                      |
| v2.25.0 | Aug 07, 2026 | Map declutter, 160-world scaling, pregen service                  |
| v2.24.0 | Aug 07, 2026 | World Map (schematic map, discoveries, bio places)                |
| v2.23.1 | Jul 13, 2026 | Vue 3.5 Reactive Destructure Migration                            |
| v2.23.0 | Jul 01, 2026 | Chat WebSocket migration                                          |
| v2.22.0 | Jun 28, 2026 | Terminal Background Cleanup                                       |
| v2.21.0 | Jun 24, 2026 | SSE Polish (incident/game-tick SSE)                               |
| v2.20.0 | Jun 22, 2026 | FE Simplification (YAGNI + DRY)                                   |
| v2.19.0 | Jun 21, 2026 | SSE streaming + Dict-to-Pydantic refactoring                      |
| v2.18.0 | Jun 21, 2026 | Library skills audit                                              |
| v2.17.0 | Jun 19, 2026 | Medical storage refactor                                          |
| v2.16.0 | Jun 18, 2026 | Accessibility, CRT theme, test fixes                              |
| v2.15.0 | Jun 18, 2026 | Dweller visual unification                                        |
| v2.14.4 | Jun 17, 2026 | Security dep bumps                                                |
| v2.13.1 | May 19, 2026 | Security hardening                                                |
| v2.13.0 | May 01, 2026 | Dramatiq migration                                                |
| v2.12.0 | Apr 23, 2026 | Test suite green, MinIO removed                                   |
| v2.11.0 | Mar 19, 2026 | Vite+ toolchain                                                   |
| v2.10.9 | Mar 13, 2026 | AI quota system                                                   |
| v2.10.0 | Feb 10, 2026 | Quest & Objective system                                          |
| v2.9.0  | Feb 07, 2026 | Chat exploration actions                                          |
| v2.8.0  | Jan 29, 2026 | Easter eggs, changelog system                                     |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

_Last updated: 2026-08-14_ (v2.35.1 released)
