# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:**

- [ ] **v2.24.0 — Alembic enum sync & misc fixes** — Enable `compare_type=True` in online Alembic mode so autogenerate detects PostgreSQL native enum value changes (additions/removals) matching Python `StrEnum` members. Previously only enabled in offline mode, allowing enum drift like the `DWELLER_DIED` outage.
- [ ] **Dramatiq async concurrency** — Fix `asyncpg InterfaceError: another operation is in progress` during game tick objective queries

---

## Latest Release

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

_Last updated: 2026-07-14_ (v2.23.1+, alembic enum sync)
