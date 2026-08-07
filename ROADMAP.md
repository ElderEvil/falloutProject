# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:**

- [ ] **Dramatiq async concurrency** — Fix `asyncpg InterfaceError: another operation is in progress` during game tick objective queries
- [ ] **Bio places silent failure (found on Andrea Freeman, vault 444)** — bio places (`Rusty Creek` origin, `Necropolis`/`Brotherhood Outpost` visited) were never registered on the world map — only `HOME_VAULT` marker exists, zero `DwellerLocation` rows. `register_bio_places` is best-effort (logs-and-swallows), so the failure is silent. Investigation (v2.26.0) confirmed it is intentionally non-raising and double-wrapped, with the `_MapDwellerLike` protocol satisfied — no cheap bugfix; follow-up needs user-visible surfacing or retry semantics for map registration failures.

---

## Latest Release

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

### v2.23.0 — Chat WebSocket & Axios→fetch Migration (July 1, 2026)

**Focus**: Execute HTTP client migration and chat WebSocket migration

**Completed:**
- ✅ **Axios→fetch migration** — Executed `HTTP_CLIENT_MIGRATION.md` 6-phase plan: fetch adapter, call-site migration, interceptor/token-refresh migration, dropped axios dep (~14KB gzip bundle saving)
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
- ✅ **Barrel migration** — All legacy barrel imports migrated to @/modules/* paths
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
- [ ] Test coverage: Target 80% (both FE/BE)

### Frontend

- [x] Vue architecture refactor → COMPLETED (v2.1.0)
- [ ] Component refactoring: Break down large components (DwellerCard, RoomGrid)

### DevOps

- [x] Docker build automation → COMPLETED
- [ ] Full CI/CD: smoke tests, DB dry-run, notifications, backup automation

---

## Progress Metrics

### Current Stats (Jul 2026)

- **Backend**: 25+ routers, 100+ endpoints, 18+ services, ~70% coverage
- **Frontend**: 60+ Vue components, 10 feature modules
- **Tests**: Frontend 867+, Backend 825+
- **Models**: 20+ database models

### Version Milestones

| Version | Release      | Highlights                                   |
| ------- | ------------ | -------------------------------------------- |
| v2.26.0 | Aug 07, 2026 | Alembic enum sync + PG enum regression tests |
| v2.25.0 | Aug 07, 2026 | Map declutter, 160-world scaling, pregen service |
| v2.24.0 | Aug 07, 2026 | World Map (schematic map, discoveries, bio places) |
| v2.23.1 | Jul 13, 2026 | Vue 3.5 Reactive Destructure Migration       |
| v2.23.0 | Jul 01, 2026 | Chat WebSocket & Axios→fetch Migration       |
| v2.22.0 | Jun 28, 2026 | Terminal Background Cleanup                  |
| v2.21.0 | Jun 24, 2026 | SSE Polish (incident/game-tick SSE)          |
| v2.20.0 | Jun 22, 2026 | FE Simplification (YAGNI + DRY)              |
| v2.19.0 | Jun 21, 2026 | SSE streaming + Dict-to-Pydantic refactoring |
| v2.18.0 | Jun 21, 2026 | Library skills audit                         |
| v2.17.0 | Jun 19, 2026 | Medical storage refactor                     |
| v2.16.0 | Jun 18, 2026 | Accessibility, CRT theme, test fixes         |
| v2.15.0 | Jun 18, 2026 | Dweller visual unification                   |
| v2.14.4 | Jun 17, 2026 | Security dep bumps                           |
| v2.13.1 | May 19, 2026 | Security hardening                           |
| v2.13.0 | May 01, 2026 | Dramatiq migration                           |
| v2.12.0 | Apr 23, 2026 | Test suite green, MinIO removed              |
| v2.11.0 | Mar 19, 2026 | Vite+ toolchain                              |
| v2.10.9 | Mar 13, 2026 | AI quota system                              |
| v2.10.0 | Feb 10, 2026 | Quest & Objective system                     |
| v2.9.0  | Feb 07, 2026 | Chat exploration actions                     |
| v2.8.0  | Jan 29, 2026 | Easter eggs, changelog system                |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

_Last updated: 2026-08-07_ (v2.26.0, alembic enum sync)
