# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:**

- [x] **v2.22.0 — @nuxt/ui Migration** — 13 custom U* components replaced with @nuxt/ui v4, useGoBack composable, toast migration
- [x] **v2.21.0 — SSE Polish** — Incident SSE publishing, incidents SSE endpoint, incident/vault store SSE subscriptions, radio datetime fix
- [x] **v2.20.0 — FE Simplification (YAGNI + DRY)** — Dead code purge (~1000 LOC deleted), barrel migration, dweller store split, component simplification, DRY consolidation
- [ ] **Dramatiq async concurrency** — Fix `asyncpg InterfaceError: another operation is in progress` during game tick objective queries

---

## Up Next (Recommended)

### v2.23.0 — Infrastructure Upgrade

- [ ] **Axios→fetch migration** — Execute `HTTP_CLIENT_MIGRATION.md` 6-phase plan (33 files): fetch adapter, call-site migration, interceptor/token-refresh migration, drop axios dep (~14KB gzip bundle saving)
- [ ] **Chat REST→WebSocket migration** — Replace POST-SSE chat streaming with dedicated WebSocket endpoint; remove chat SSE stub from stream.py

---

## Latest Release

### v2.21.0 — SSE Polish (June 24, 2026)

**Focus**: Real-time SSE for incidents and game ticks, radio recruitment PostgreSQL fix

**Completed:**
- ✅ **Incident SSE publishing** — `incident_service` publishes `incident_spawned`, `incident_resolved`, `incident_spreading` via SSE (3 TDD tests)
- ✅ **Incidents SSE endpoint** — `GET /stream/incidents/{vault_id}` with vault ownership check and heartbeat
- ✅ **Incident store SSE subscription** — `incident.ts` replaces `setInterval` polling with SSE; 30s fallback to REST on disconnect
- ✅ **Vault store game-tick SSE** — `vault.ts` subscribes to game tick SSE for live resource updates; SSE lifecycle bound to vault load/close/play-pause
- ✅ **`useSseBase` auto-reconnect** — Exponential backoff reconnect (1s→2s→4s→...→30s max) on connection loss (10 tests)
- ✅ **Radio recruitment fix** — 3 `datetime.now(UTC)` → `datetime.utcnow()` in `dweller_recycling_service.py` stops PostgreSQL `DataError` on `TIMESTAMP WITHOUT TIME ZONE` columns
- ✅ **SSE heartbeat configurable** — `SSE_HEARTBEAT_INTERVAL` setting replaces hardcoded 30s
- ✅ **Dead code removal** — Removed dead POST-SSE `/stream/chat/{dweller_id}` endpoint

**Deferred to v2.22 (completed) / v2.23 (remaining):**
- ✅ @nuxt/ui adoption (~1093 LOC replacement of 11 home-grown U* components, grey dropdown fix) — completed in v2.22.0
- Axios→fetch migration (HTTP_CLIENT_MIGRATION.md 6-phase plan, ~14KB gzip bundle saving) — moved to v2.23.0
- Chat REST→WebSocket migration (replace POST-SSE chat with dedicated WS) — moved to v2.23.0

---

### v2.22.0 — @nuxt/ui Migration (June 24, 2026)

**Focus**: Replace custom-built U* components with @nuxt/ui v4; add useGoBack navigation composable

**Completed:**
- ✅ **@nuxt/ui adoption** — Replaced 13 home-grown U* components (~1100 LOC) with @nuxt/ui v4 equivalents; added neutral color scale to `nuxt-ui.config.ts` fixing grey dropdown background
- ✅ **useGoBack composable** — Browser-history back navigation with `router.back()`, `parentRoute` fallback, and no-parent fallback (4 TDD tests)
- ✅ **parentRoute metadata** — Added `meta.parentRoute` to all 12 sub-view and detail-view route definitions
- ✅ **Toast migration** — Migrated to @nuxt/ui built-in toast via compatibility adapter (zero call-site changes)
- ✅ **Component defaults** — Expanded `nuxt-ui.config.ts` defaults for Modal, Badge, Alert, Tooltip, Skeleton, Tabs, Select
- ✅ **Custom component removal** — Deleted 13 U* component files (UButton, UInput, UCard, UModal, UBadge, UAlert, UTooltip, USkeleton, UTabs, USelect, UToast, UToastContainer, barrel index.ts) and custom useToast

**Deferred to v2.23:**
- Axios→fetch migration (HTTP_CLIENT_MIGRATION.md 6-phase plan, ~14KB gzip bundle saving)
- Chat REST→WebSocket migration (replace POST-SSE chat with dedicated WS)

---

### v2.20.0 — FE Simplification (YAGNI + DRY) (June 22, 2026)

**Focus**: Reduce frontend complexity, remove dead code, consolidate DRY violations, migrate barrel imports

**Completed:**
- ✅ **6-step YAGNI heuristic** — Added to AGENTS.md governing all FE work
- ✅ **~1500 LOC reduction** — Deleted ~1000 LOC dead code across 43 files (barrel re-exports, dead composables, unused UI components, aspirational infra)
- ✅ **DRY consolidation** — Merged useSse/usePostEventStream into useSseBase; merged WeaponCard/OutfitCard into EquipmentCard; consolidated room-destroy logic; CSS variables replace hardcoded hex colors
- ✅ **Barrel migration** — All legacy barrel imports migrated to @/modules/* paths; 8 empty directories removed
- ✅ **Dweller store split** — dweller.ts (796 LOC) split into 5 focused stores with backward-compat facade
- ✅ **DwellerCard split** — Extracted DwellerCardActions + HappinessModifierPopover sub-components
- ✅ **Dead composables removed** — useTerminalAudio (326 LOC), useAuth, useFlickering, composables/index.ts barrel
- ✅ **Unused UI removed** — ComingSoonBadge, UDropdown (104 LOC)
- ✅ **Aspirational infra removed** — api.ts wrapper (116 LOC), core/types/index.ts barrel, api/incident.ts dead duplicate

**Deferred to v2.21:**
- @nuxt/ui adoption (~1093 LOC replacement of 11 home-grown U* components, grey dropdown fix)
- Axios→fetch migration (HTTP_CLIENT_MIGRATION.md 6-phase plan, ~14KB gzip bundle saving)

### v2.19.0 — Dict-to-Pydantic Refactoring + SSE Streaming (June 21, 2026)

**Focus**: Replace `dict` return types with typed Pydantic schemas; add real-time SSE streaming for game ticks, notifications, chat, and exploration

**Completed:**
- ✅ **SSE streaming infrastructure** — `SSEManager` singleton, 4 SSE endpoints (notifications, game ticks, chat tokens, exploration), heartbeat keepalive
- ✅ **Dual notification broadcast** — Notifications sent via both WebSocket + SSE; NotificationBell uses live SSE instead of 30s polling
- ✅ **Streaming AI chat** — Token-by-token SSE streaming via `chat_service.stream_response()`
- ✅ **Game tick SSE** — `process_vault_tick()` publishes to SSE; duplicate publish bug fixed with TDD (3 tests)
- ✅ **Exploration SSE** — Live events published from coordinator (process_event, complete_exploration, recall_exploration)
- ✅ **Frontend SSE composables** — `useEventStream`, `usePostEventStream` (proper SSE protocol parser), `useSse` (auth header support)
- ✅ **Stream manager tests** — 11 unit tests covering subscribe/publish, queue full, close, heartbeat
- ✅ **New response schemas** — Created `GameBalanceResponse`, `HappinessModifiersResponse`, `DeathStatsResponse`, `UnassignResponse`, `AutoAssignResponse`, `DwellerAssignmentItem`, `QuestPartyMemberRead`, `EligibleDwellerRead` across `schemas/` files.
- ✅ **Dict → Pydantic conversion** — Replaced `dict` returns in 8+ endpoints (game balance, happiness, death stats, vault auto-assign, quest party/eligible dwellers).
- ✅ **Schema unpacking** — 4 pregnancy endpoints switched from manual field mapping to `PregnancyRead.model_validate()`.
- ✅ **Service layer relocation** — Moved vault mutation from `radio.py` endpoint into `radio_service.set_radio_mode()`; consolidated `get_by_vault`/`get_active_by_vault` into single `get_by_vault(active_only=False)`.
- ✅ **Return type annotations** — Added `response_model=None` + `-> None` to `unequip_outfit`/`unequip_weapon`; added `-> dict[str, Any]` to game control endpoints; wired 5 auth endpoints to existing `MessageResponse`.
- ✅ **E2E verification** — All refactored endpoints tested via curl against running backend. Auth (MessageResponse), game balance (GameBalanceResponse), vault auto-assign (UnassignResponse/AutoAssignResponse), and death stats (DeathStatsResponse) confirmed working.
- ✅ **Tests** — Full suite 804 passing, ruff clean.

### v2.18.0 — Library Skills Compliance (June 21, 2026)

**Focus**: Audit project against FastAPI, Typer, and Pydantic AI best-practice skills; fix all violations

**Completed:**

- ✅ **Library skills audit** — Added FastAPI, Typer, and Pydantic AI skills from `uvx library-skills`. Ran full compliance audit across all 3 skills, fixed all violations.
- ✅ **Router prefix/tags compliance** — Moved `prefix` and `tags` from `include_router()` into individual `APIRouter()` constructors across all 22 router files.
- ✅ **Annotated dependency style** — Standardized to `Annotated[Type, Depends()]` pattern in 12 endpoint params and 6 shared deps.
- ✅ **Return type annotations** — Added explicit return types to ~108 endpoint functions.
- ✅ **Nested try-except extraction** — Extracted helper functions in `chat_service.py`, `conversation_service.py`, and `chat.py` endpoint.
- ✅ **Async safety** — Wrapped sync S3/storage/OpenAI calls with `asyncio.to_thread()` in 4 service files.
- ✅ **Chat endpoint cleanup** — Moved `ChatMessage` model to `schemas/chat.py` and `_send_chat_notification` helper to `ChatService` as a static method.
- ✅ **Tests** — 37/37 backend tests passing, ruff clean across the entire project.

### v2.17.0 — Medical Storage Refactor (June 19, 2026)

**Focus**: Move stimpaks/radaways from Vault model to Storage model, compute capacity dynamically from rooms

**Completed:**

- ✅ **Storage model** — Added `stimpack`, `radaway` fields to `StorageBase`
- ✅ **Vault model cleanup** — Removed `stimpack`, `stimpack_max`, `radaway`, `radaway_max` from `VaultBase`
- ✅ **Config mapping** — `MEDICAL_ROOM_PRODUCTION` mapping (medbay→stimpak, science lab→radaway) + `compute_medical_capacity()` in `game_config.py`
- ✅ **Resource Manager** — Medical production writes to Storage, capped by `compute_medical_capacity`, no more string matching
- ✅ **Vault Service** — Room build no longer updates capacity fields; vault init writes medical to Storage; `transfer_medical_supplies` reads/writes Storage
- ✅ **Exploration Service** — `send_dweller` deducts from Storage; unused supplies return to Storage capped by capacity
- ✅ **CRUD** — Removed `stimpack_max`/`radaway_max` special-casing in `crud/vault.py`
- ✅ **Frontend types regenerated** — `api.generated.ts` no longer has `stimpack_max`/`radaway_max`
- ✅ **StorageView medical display** — Added `stimpack`/`radaway` fields to `StorageSpaceResponse`; StorageView reads from storage API instead of removed vault fields
- ✅ **Tests** — 804 backend tests, 861 frontend tests, 19 new medical storage/capacity tests
- ✅ **DB migration** — `abc123def456` copies data vault→storage, drops 4 columns, reversible

### v2.15.0 - Dweller Visual Unification (June 18, 2026)

**Focus**: Unified visual attribute schemas, race/faction-aware AI agent, manual appearance editor

**Completed:**

- ✅ **Schema unification** — Merged 3 schemas into one 22-field `DwellerVisualAttributes` with canonical field names (`hair_style`, `build`)
- ✅ **Race/Faction-aware AI agent** — Agent prompt now includes race-specific skin tone, build, and style guidance
- ✅ **Race/faction display in frontend** — `DwellerAppearance.vue` shows Race, Faction, State of Being
- ✅ **Default visual attributes** — New dwellers get `{race: human, faction: vault_dweller}`
- ✅ **Manual appearance editor** — Race-filtered dropdowns for all fields, Randomize button, portrait force-regeneration
- ✅ **Options data module** — `backend/app/options/` ported from `fallout-avatar` project
- ✅ **Frontend types regenerated** — OpenAPI types include full `DwellerVisualAttributes`
- ✅ **33 passing tests** (8 schema, 15 service/options, 1 crud, 9 frontend editor)

### v2.16.0 - Infrastructure & Code Quality (June 18, 2026)

**Focus**: Frontend accessibility, CRT theme consistency, module READMEs, backend test fixes

**Completed:**

- ✅ **FE accessibility pass** — Added `role=button`/`tabindex`/keyboard handlers to 13 clickable elements across 8 files; full focus trap on UModal with Tab cycling, Escape close, focus restore; `aria-label` on 8 icon-only buttons; `role="dialog"`/`aria-modal` on inline modals
- ✅ **CRT theme consistency** — Replaced hardcoded hex colors in ~45 files with CSS variables (`--color-theme-primary`, `--color-danger`, etc.); migrated 5 auth forms and HomeView vault creation form from raw `<button>`/`<input>` to UButton/UInput; added `type` prop to UButton
- ✅ **Module READMEs** — Added 1-paragraph docs for each frontend module (auth, vault, dwellers, rooms, etc.) — 12 READMEs total
- ✅ **Backend skipped tests** — Fixed 12 skipped backend tests (quest datetime, 6 bare-skips, 3 incident assertions, 2 room session-race)
- ✅ **Nuxt UI migration plan** — Drafted `.omo/drafts/nuxt-ui-migration-plan.md`
- ✅ **Dead code removal** — Deleted `LoginForm.vue` (replaced by `LoginFormTerminal`), dropped `fix-changelog-freeze.md`

### v2.13.0 - Dramatiq Migration (May 1, 2026)

**Focus**: Replaced Celery with Dramatiq for simpler, more reliable task processing

**Completed:**

- ✅ **Dramatiq Task Queue** - Migrated from Celery + Celery Beat to Dramatiq + Periodiq
  - 8 task actors: `game_tick`, `process_vault_tick`, `check_permanent_deaths`, `check_quest_completion`, `refresh_daily_objectives`, `refresh_weekly_objectives`, `cleanup_old_records`, `create_task`
  - Periodiq scheduler replaces Celery Beat with cron syntax
  - 3 Celery containers + Flower → 1 Dramatiq worker container
- ✅ **Backend Dockerfile** - Multi-stage build (builder + runtime stages)
- ✅ **MinIO Cleanup** - Removed dead MinIO env vars from all `.env` files
- ✅ **Dependency Cleanup** - Removed `celery`, `sqlalchemy-celery-beat`, `celery-types`, `psycopg2`

**Migration required:**

- Update `.env`: remove `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `FLOWER_USER`, `FLOWER_PASSWORD`
- Update Docker Compose: replace `celery_worker` + `celery_beat` + `flower` with `dramatiq_worker`
- Run DB migration to drop `celery_schedule_jobs` table

### v2.13.1 - Security & Reliability Hardening (May 19, 2026)

**Focus**: Security improvements and infrastructure reliability post-Dramatiq migration

**Completed:**

- ✅ **Non-root containers** - Backend Docker image no longer runs as root
- ✅ **RustFS credential security** - Removed hardcoded credentials; `RUSTFS_ACCESS_KEY` / `RUSTFS_SECRET_KEY` now required explicitly
- ✅ **Task scheduler auto-recovery** - Docker restart policy added for Dramatiq worker / Periodiq scheduler
- ✅ **DB migration cleanup** - Fixed migration leaving orphaned PostgreSQL enum types on Celery table drop
- ✅ **RustFS config restored** - `.env.prod.example` now includes all required `RUSTFS_*` variables
- ✅ **Documentation cleanup** - Removed 11 outdated docs, archived 4 guides, compacted 12-factor report

### v2.14 - Asset Repurpose & Bug Fixes (In Progress)

**Focus**: Repurpose soft-deleted dweller assets for radio recruitment; address issues discovered post-Dramatiq migration

**In Progress:**

- [ ] **Radio asset repurpose** (`2.14-repurpose`) - When the radio recruits, prefer restoring a soft-deleted dweller (reusing their existing S3 image/thumbnail/bio assets) over generating a blank new one. Falls back to `create_random` when the recycling pool is empty or an override is supplied. Config-gated via `RADIO_RECYCLE_ENABLED` / `RADIO_RECYCLE_PROBABILITY` / `RADIO_RECYCLE_MIN_AGE_DAYS`. Frontend shows a distinct toast for recycled recruits.

**Planned:**

- [ ] **SQLAlchemy async concurrency error in `game_tick`** - `InterfaceError: cannot perform operation: another operation is in progress` during objective queries (`vaultobjectiveprogresslink`) inside game tick tasks. Root cause: concurrent async operations sharing the same SQLAlchemy connection/session. Fix: ensure proper session isolation per task (`async with` session per query).

### v2.12.0 - Stabilization & Quality (April 23, 2026)

**Focus**: Fix all failing tests, remove deprecated code, harden error handling

**Completed:**

- ✅ **Chat Error Handling** - Hardened AI provider failure handling across all services
  - Fixed `AttributeError: 'coroutine' object has no attribute 'input_tokens'` bug
  - Added safe usage extraction with fallback to `None` for token counts
  - Applied fix to `chat_service.py`, `dweller_ai.py`, `open_ai.py`, `conversation_service.py`
  - Added 4 regression tests for error handling scenarios
- ✅ **Test Suite Green** - Fixed 23 previously failing/skipped backend tests
  - 18 quota tests: resolved session isolation for LLMInteraction records
  - 5 radio tests: unskipped by fixing fixture session commit patterns
  - Full suite: 657 passed, 20 skipped, 0 failures
- ✅ **MinIO Removal** - Completely removed deprecated MinIO storage provider
  - Deleted `minio_adapter.py` and all references
  - Removed MinIO config, Docker Compose services, and env vars
- ✅ **Celery Cleanup** - Removed unused `generate_dweller_attributes` task stub
- ✅ **Version Bump** - Backend and frontend aligned at v2.12.0

### v2.11.0 - Toolchain Migration & Recycling Service (March 19, 2026)

**Focus**: Vite+ unified toolchain, dweller recycling service, and test fixes

**Completed:**

- ✅ **Vite+ Unified Toolchain** - Migrated to Vite+ for improved bundling and DX
  - Unified build tooling across frontend
  - Improved build performance
- ✅ **MinIO Deprecation Warnings** - RustFS is now the primary storage provider
  - Added deprecation warnings for MinIO configuration
  - RustFS marked as default and recommended option
- ✅ **Dweller Recycling Service** - New service for processing dead dwellers
  - Implemented recycling mechanics for permanent deaths
  - Integration with vault economy system
- ✅ **Exploration Coordinator Tests** - Fixed 4 failing tests
  - Test isolation issues resolved
  - All exploration coordinator tests now passing

### v2.10.9 - AI Usage Tracking & Quota System (March 13, 2026)

**Focus**: AI usage monitoring, token quota enforcement, and observability improvements

**Completed:**

- ✅ **AI Usage API** - New `/me/profile/ai-usage` endpoint with token statistics
  - Tracks prompt, completion, and total tokens across all AI calls
  - Redis-cached responses for performance
  - Terminal-themed UI card in profile view
- ✅ **Quota System** - Per-user monthly token limits with enforcement
  - Default 500K tokens per month per user
  - Atomic quota checks with SELECT FOR UPDATE
  - HTTP 429 responses when quota exceeded
  - UI blocking and warnings at 80% threshold
  - Admin bypass support
- ✅ **Observability** - Optional Logfire integration
  - Initialized at startup when configured
  - Richer OpenAI usage reporting
- ✅ **Storage** - Completed RustFS migration
  - Removed legacy MinIO integration
  - Added HTTPS and public URL configuration options
- ✅ **Tests** - Comprehensive test coverage
  - Unit, integration, and race condition tests for quota system
  - E2E tests for quota blocking UI

### v2.10.8 - RustFS Migration & Code Quality (February 19, 2026)

**Focus**: Storage provider migration, objective improvements, code quality

**Completed:**

- ✅ **RustFS Migration** - Switched default storage from MinIO to RustFS
  - Added utility scripts for image URL fixes and bucket policies
  - Updated bucket whitelist with all required buckets
- ✅ **Objective System** - Added `assign_correct` type, made `category` required
- ✅ **Code Quality** - Fixed lint issues, added integration tests, addressed code review feedback

### v2.10.4 - Quest System Fix (February 13, 2026)

**Focus**: Fixed quest seeding bugs and verified quest system works

**Completed:**

- ✅ **Quest JSON Fixes** - Fixed invalid requirement types in quest files
  - Changed `dweller_level` → `level` in 4 quest files
  - Removed invalid `weapon_damage` requirement type
  - All 18 quests now seed correctly
- ✅ **Quest Seeding Tests** - 8 tests passing
- ✅ **Reward Service Tests** - 13 tests passing
- ✅ **Quest UI Verified** - Full UI already implemented and working
  - QuestsView with tabs (active/available/completed)
  - QuestDetailView with requirements and rewards
  - Quest store with API integration
  - Route: `/vault/:id/quests`

**Note:** Quest UI was already implemented - just fixed the seeding bugs that prevented it from working.

### v2.10.6 - Medical Storage System (Planned)

**Focus**: Stimpaks and Radaways vault storage with production from Medbay/Science Lab

**Known Issue (needs fix):**

- ⚠️ **Storage Model Refactor** - Currently stimpaks/radaways are on Vault model, should be on Storage model
  - Add fields to Storage: `stimpack`, `radaway`, `stimpack_max`, `radaway_max`
  - Remove from Vault model
  - Update all code to read/write from storage instead of vault

**Planned:**

- [ ] **Vault Storage for Medical Items** - Add stimpaks and radaways to vault storage
  - New storage model fields: `stimpaks`, `radaways`
  - Max capacity calculated from Medbay/Science Lab rooms (number + tier)
  - UI: Show medical items in Storage view
- [ ] **Medbay Production** - Medbay rooms produce stimpaks over time
  - Production rate based on room tier
  - Produced items go directly to vault storage
- [ ] **Science Lab Production** - Science Lab rooms produce radaways over time
  - Production rate based on room tier
  - Produced items go directly to vault storage
- [ ] **Exploration Integration** - Dwellers can equip stimpaks/radaways from storage before exploration
  - Show available stimpaks/radaways in exploration preparation UI
  - Deduct from storage when dweller takes them
- [ ] **Objectives Support** - "Collect X Stimpaks/Radaways" objectives work with storage

---

### v2.10.3 - Frontend Cleanup (February 13, 2026)

**Focus**: Fixed type errors and lint warnings

**Completed:**

- ✅ Fixed Vue TypeScript build errors (undefined array access, void elements)
- ✅ Fixed backend lint warnings

---

### v2.10.0 - Quest & Objective System (February 10, 2026)

**Focus**: Working quest system with proper reward distribution and objective progress tracking

**Completed:**

- ✅ **Quest JSON Loading** - Fixed `QuestJSON` schema to accept both space-separated ("Quest name") and snake_case ("quest_name") field names
- ✅ **Quest Seeding** - All 19 quests across 7 chains now load correctly from JSON files
- ✅ **Quest Rewards** - Implemented `reward_service.process_quest_rewards()` with caps, items, dwellers, stimpaks, radaways, and lunchboxes
- ✅ **Objective Progress** - Fixed `create_for_vault()` to set `total` from `target_amount` (was defaulting to 1)
- ✅ **Quest Completion Events** - Emits `QUEST_COMPLETED` events and notifications when quests finish
- ✅ **Power Struggle Quest Chain** - Fixed loading of 8-quest chain from `power_struggle.json`
- ✅ **Level-Up Tracking** - Added `DWELLER_LEVEL_UP` event emission in `game_loop.py` and `crud/dweller.py` for objective tracking
- ✅ **Event Data Format** - Fixed event data to use `level` field (what `ReachEvaluator._extract_amount` expects)
- ✅ **Quest Rewards Validation** - Fixed 11 quests with empty/short rewards by adding `generate_rewards_string()` function that parses structured `quest_rewards` into human-readable strings
- ✅ **QuestJSON Schema** - Added "Rewards" and "Requirements" to field mapping for proper parsing of space-separated keys
- ✅ **Tests** - 24 tests passing (11 leveling + 13 reward services)

### v2.9.3 - Component Refactoring & Backend Quick Wins (February 8, 2026)

**Focus**: Major frontend component refactoring and backend code quality improvements

**Completed:**

- ✅ **RoomDetailModal Deep Split** - Reduced from 1045 lines to ~200 lines (~80% reduction)
  - Extracted 7 focused components: RoomDetailHeader, RoomPreviewSection, RoomInfoGrid, ProductionStats, DwellerList, RoomActions, RadioControls
  - Extracted 4 composables: useRoomProduction, useRoomUpgrade, useRoomDwellers, useRadioRoom
  - All 49 existing tests pass, no behavioral changes
- ✅ **DwellerChat Light Split** - Logic extracted into composables
  - useChatMessages, useChatActions, useChatAudio, useTypingIndicator
  - UI remains intact, complexity reduced
- ✅ **Backend Service Logging** - Added to leveling_service.py and notification_service.py
- ✅ **Dead Code Removal** - Removed unused get_spreading_incidents() from incident CRUD
- ✅ **Version Alignment** - Backend and frontend both at v2.9.3

### v2.9.0 - Chat Actions & Agent Intelligence (February 7, 2026)

**Focus**: Chat action suggestions, exploration integration, and smarter room assignment

**Completed:**

- ✅ **Exploration from Chat** - Start and recall explorations directly from dweller chat
  - `start_exploration` action with automatic supply packing (2 stimpaks / 1 radaway caps)
  - `recall_exploration` action with completion detection (collect rewards if done)
  - Deterministic enrichment — backend computes all IDs/counts, never trusts LLM
- ✅ **Universal Room Assignment** - Dwellers can be assigned to ANY room type from chat
  - New `list_all_rooms()` agent tool covers all 7 categories
  - Dwellers follow orders strictly when a specific room is named
  - Kept specialized `list_production_rooms()` / `list_training_rooms()` for stat-based queries
- ✅ **Training Action Fix** - Fixed "Unable to access vault data" when confirming training
  - Root cause: vault API doesn't return rooms array, now uses room store
- ✅ **WebSocket Stability** - UUID serialization, URL handling, typing race conditions
- ✅ **Chat UX** - Latest-only action suggestion rendering, message ID correlation
- ✅ **Conversation Happiness System (shipped)** - Core happiness tracking
  - Chat happiness impact display (delta + reason text)
  - WebSocket happiness_update events with message correlation
  - Real-time happiness indicators in chat UI
  - Remaining for future: happiness analytics/trends, decay mechanics
- ✅ **Tests** - 799 frontend tests, 33+ new backend tests (chat + agent tools)

### v2.8.5 - Code Quality & Refactoring (Completed - February 2026)

**Focus**: Technical debt reduction, code deduplication, and maintainability improvements

**Completed:**

- ✅ **Code Deduplication**
  - Removed empty CRUD classes (weapon, outfit, junk) - now use CRUDItem directly
  - Extracted vault filtering logic into shared `get_items_list()` utility
  - Created generic `seed_from_json()` helper and refactored objective seeder
- ✅ **Error Handling Improvements**
  - Replaced 11 bare `except Exception` handlers with specific exceptions (SMTPException, SQLAlchemyError, RedisError, etc.)
- ✅ **Configuration Cleanup**
  - Moved exploration/item constants to game_config.py (rarity priorities, junk values, scrap probabilities)
- ✅ **Refactoring**
  - Refactored `_transfer_loot_to_storage()` - reduced from 171 to ~110 lines
  - Extracted 4 helper methods (\_parse_rarity_to_enum, \_create_weapon_from_loot, \_create_outfit_from_loot, \_create_junk_from_loot)
  - Removed complexity suppressions (PLR0912, PLR0915)
- ✅ **Storage & Infrastructure**
  - Added RustFS storage provider support (alongside MinIO)
  - Fixed room images loading in dockerized HTTPS staging environments
- ✅ **UX Improvements**
  - Room tiles now show SPECIAL ability letter (e.g., "Power Generator (S)")
  - Room tiles display ability icon for visual identification
- ✅ **Testing**
  - Added 5 tests for weapon/outfit loot transfer branches
  - Added training room status assignment test

**Deferred to Future Releases:**

- Add query builder methods to CRUDBase for soft-delete and vault-scoped queries
- Create `get_or_404()` helper to reduce ResourceNotFoundException boilerplate (28 locations)
- Add notification error handling decorator/utility
- Split game_loop.py (767 lines) into smaller domain services
- Implement TODO stub in `celery_task.py:26`
- Fix session isolation issues in 2 test files
- Address N+1 query patterns in game loop
- **Parse objective text to structured data** - Auto-extract `objective_type`, `target_entity`, and `target_amount` from challenge text (e.g., "Collect 100 Caps" → collect, {resource_type: caps}, 100) instead of hardcoded mappings

### v2.8.0 - Easter Eggs & UI Fixes (January 29, 2026)

**Focus**: Hidden features, terminal aesthetic polish, and UX bug fixes

**Completed:**

- ✅ **Changelog System**
  - Terminal-themed modal with version update notifications
  - Auto-show on login after update
  - Manual `/changelog` route for browsing history
  - Backend API parsing CHANGELOG.md
  - Version detection with localStorage tracking
- ✅ **Easter Eggs**
  - Gary Virus (Vault 108 tribute): click dweller named "Gary" for 10s glitch overlay
  - Version Glitch Crash: click version 7 times for fake BSOD + terminal reboot
  - Frontend-only implementation with localStorage persistence
  - Automated tests (9/12 passing)
- ✅ **Build Mode Hotkey** - Russian keyboard layout support
  - Layout-independent via `KeyboardEvent.code === 'KeyB'`
  - Ctrl/Cmd+B conflict resolution with SidePanel
  - Guards for contenteditable/input/textarea contexts
- ✅ **Happiness Page UX** - Quick Actions footer
  - Moved to UCard footer (clear bottom placement)
  - Shows "optimal" hint when no actions needed
- ✅ **Radio Recruitment** - Staffing enforcement and cost accuracy
  - Backend validates: requires ≥1 dweller in radio room
  - Frontend UAlert warning when no dwellers assigned
  - Cost fetched from API (was hardcoded to 100)
- ✅ **Room Destroy Refund** - 50% including upgrades
  - New formula: `floor(0.5 * (base + incremental + tier_upgrades))`
  - Frontend refreshes vault caps after destroy
- ✅ **Tooltip Z-Index** - Fixed rendering above navbar
  - UTooltip uses Teleport to body (escapes stacking context)
  - Fixed positioning with `getBoundingClientRect()`
  - Resource tooltips now visible

**Remaining for v2.10.0+:**

- Token Management & Usage Tracking
- Provider Rotation (Ollama URL config + health checking)
- Admin & Configuration (birth control, room render config)
- Additional Easter Eggs:
  - "It Just Works" (Todd Howard tribute with buffs)
  - Konami Code developer mode (unlock Debug Room)
  - Quantum Mouse trail effect

### v2.7.0 - Storage Management & UI Polish (Completed)

**Focus**: Vault storage system implementation and UI improvements

**Completed:**

- ✅ **Storage Management System**
  - Storage sidebar navigation entry (hotkey: 9)
  - Storage space tracking and visualization
  - Item scrap functionality for weapons/outfits
  - Junk item grouping by type with count badges
  - Sell All feature for stacked items
  - Enhanced item cards with detailed stats
- ✅ **Keyboard Shortcuts**
  - Build mode toggle with 'B' key
  - ESC to exit build mode
  - Hotkey badges on buttons
- ✅ **Bug Fixes**
  - Fixed junk item pricing (now based on rarity)
  - Fixed equipment filtering by vault
  - Fixed async greenlet issue in sell method
  - Added missing fields to weapon/outfit schemas
- ✅ **UI Enhancements**
  - Equipment cards match storage card styling
  - Progress bar uses consistent theme color
  - Better stat display with icons
  - Improved button layout and grouping

**Remaining for Future Updates:**

- Layout Improvements (sticky panels, smooth scrolling)
- Toast Notifications (unification, grouping, deduplication)
- Exploration UI (overflow handling, pagination, history)

### v2.6.5 - Notification Foundation (Completed)

**Status**: Notification system implemented

**Completed:**

- ✅ Notification bell UI component with pop-up
- ✅ Exploration completion notifications
- ✅ Radio recruitment notifications
- ✅ Incident spawn notifications
- ✅ Comprehensive test coverage (4 tests passing)

---

## Easter Eggs & Hidden Features (v2.8.0+)

**Focus**: Lore-accurate and playful hidden interactions to reward player discovery

### 1. The "Gary" Virus (Vault 108 Tribute)

**Lore**: In Fallout 3, Vault 108 was overrun by clones who only said "Gary."

**Trigger**: Player renames a dweller to "Gary"

**Effect**:

- For 10 seconds, all text in the UI (headers, buttons, logs, tooltips) displays "Gary"
- Terminal glitch/flicker animation during transformation
- Audio: Distorted "Gary!" voice clip (optional)

**Implementation Notes**:

- Vue composable: `useGaryMode()`
- Global reactive state that temporarily overrides text rendering
- CSS class `.gary-mode` on `<body>` element
- Alternative: Override i18n/localization helper temporarily
- Reset after 10 seconds with smooth transition

---

### 2. "It Just Works" (Todd Howard Tribute)

**Trigger**: Rename a dweller to "Todd"

**Effect**:

- **Permanent Buff**: +10 Charisma (CHA) stat
- **Hidden 24h Buff**: 100% Rush Success Rate
- **Audio**: On successful rush, play Todd Howard's "It just works" voice clip instead of default success sound
- **Visual**: Special golden glow effect on the dweller card

**Implementation Notes**:

- Backend: Add hidden buff system for temporary bonuses
- Track buff expiry with timestamp
- Frontend: Custom sound effect for Todd dweller rush success
- Special visual indicator on dweller card (subtle sparkle/glow)

---

### 3. Version Number Glitch (Fake BSOD)

**Trigger**: Rapidly click the version number in footer 7 times

**Effect**:

1. Screen fades to black
2. Terminal text types out: `CRITICAL FAILURE. INITIATING PROTOCOL 27...`
3. Fake "Vault-Tec Terminal Crash" screen with CRT effects
4. Screen "reboots" with terminal boot sequence animation
5. Player receives 27 Nuka-Colas (or premium currency)
6. Toast notification: "Emergency systems restored. Compensation awarded."

**Implementation Notes**:

- Click counter with timeout (reset after 2s of no clicks)
- Full-screen modal overlay with CRT/terminal aesthetic
- Typewriter text animation
- Backend API call to award premium items
- Version number extraction from `package.json` (not hardcoded)

**Code Snippet**:

```vue
<script setup>
import { ref } from 'vue'
const clicks = ref(0)
let timeout: NodeJS.Timeout | null = null

const handleVersionClick = () => {
  clicks.value++
  if (timeout) clearTimeout(timeout)

  if (clicks.value === 7) {
    triggerFakeCrash()
    clicks.value = 0
  } else {
    timeout = setTimeout(() => { clicks.value = 0 }, 2000)
  }
}
</script>
<template>
  <footer @click="handleVersionClick" class="cursor-pointer select-none">
    v{{ version }}
  </footer>
</template>
```

---

### 4. Konami Code Developer Mode

**Trigger**: Enter Konami Code sequence: ↑ ↑ ↓ ↓ ← → ← → B A

**Effect**:

- Toast notification: "Cheat Codes Enabled"
- Unlock hidden "Debug Room" in build menu
- Debug Room properties:
  - Cost: 0 caps
  - Power production: +999
  - Risk: 50% chance per minute to spawn Deathclaw (super hard enemy)
  - Visual: Glitchy, unstable aesthetic (flickering, distorted)
  - Category: "Experimental" (new category)

**Implementation Notes**:

- Use VueUse `useMagicKeys()` composable for key sequence detection
- Backend: Add "Debug Room" template (locked by default)
- Frontend: Toggle room availability in build menu based on cheat code state
- Persist cheat state in localStorage (session-based)
- Deathclaw spawn: Celery task with 50% probability

**Code Snippet**:

```typescript
import { useMagicKeys } from "@vueuse/core";

const { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, b, a } = useMagicKeys();
const sequence = ref("");

watch([ArrowUp, ArrowDown, ArrowLeft, ArrowRight, b, a], () => {
  // Track key sequence and check for Konami Code
  // ↑ ↑ ↓ ↓ ← → ← → B A
});
```

---

### 5. Quantum Mouse (Visual Effect)

**Trigger**: Player reaches exactly 1000 caps (or specific milestone)

**Effect**:

- Mouse cursor leaves glowing blue particle trail (Nuka Quantum style)
- Particles fade out over 1-2 seconds
- Effect persists for entire session
- Subtle, non-intrusive visual enhancement

**Implementation Notes**:

- Canvas overlay with `pointer-events: none`
- Track mouse coordinates with `mousemove` event
- Render fading circles/bubbles on canvas
- RequestAnimationFrame for smooth animation
- Blue glow color: `#00B4FF` (Nuka Quantum)
- Z-index: 9999 to stay above all UI

**Code Snippet**:

```vue
<template>
  <canvas ref="quantumCanvas" class="fixed inset-0 pointer-events-none z-[9999]" />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const quantumCanvas = ref<HTMLCanvasElement | null>(null)
const particles: Particle[] = []

const handleMouseMove = (e: MouseEvent) => {
  particles.push(new Particle(e.clientX, e.clientY))
}

const animate = () => {
  // Clear canvas, update particles, render
  requestAnimationFrame(animate)
}

watch(() => userStore.caps, (caps) => {
  if (caps === 1000) {
    window.addEventListener('mousemove', handleMouseMove)
    animate()
  }
})
</script>
```

---

### Technical Requirements

**Backend**:

- Hidden buff system (temporary stat modifiers)
- Easter egg event tracking (analytics)
- API endpoints for easter egg rewards
- Debug room template data

**Frontend**:

- Global state management for active easter eggs
- Composables: `useGaryMode()`, `useKonamiCode()`, `useQuantumMouse()`
- Audio service for custom sound effects
- Canvas rendering utilities for particle effects
- VueUse integration for key detection

**Testing**:

- Unit tests for each easter egg trigger
- E2E tests for UI effects
- Backend tests for buff system
- Audio playback tests

**Documentation**:

- Easter egg hints in loading screen tips (subtle)
- Achievement tracking for players who discover them
- Optional: Hidden achievement badges for each easter egg

---

## Recent Completions

### v2.8.3 - Maintenance Release (February 2026)

**Focus**: Backend refactoring and service improvements

**Completed:**

- ✅ **Backend Refactoring**
  - Split game loop relationship update logic into helper functions
  - Extracted exploration loot transfer into separate coordinator functions
  - Improved code organization and maintainability
- ✅ **Coverage Improvements** - Updated backend test coverage reporting

### v2.8.2 - Backend Improvements (February 2026)

**Focus**: Code quality and service layer enhancements

**Completed:**

- ✅ **Service Refactoring** - Improved game loop service structure
- ✅ **Code Organization** - Better separation of concerns in backend services

### v2.5.0 Room Visual Assets (January 26, 2026)

**Feature Release** - Room sprite rendering and capacity enforcement

- **Room Images**: Full visual representation of all rooms
  - 220+ room sprite images for all room types, tiers, and sizes
  - Images render in vault overview grid as backgrounds
  - Images display in room detail modal preview section
  - Intelligent fallback system for missing tier/segment combinations
  - Automatic image URL generation based on room name, tier, and size
- **Room Capacity Enforcement**: Strict dweller assignment limits
  - Capacity calculation: 2 dwellers per cell (3-cell room = 2, 6-cell = 4, 9-cell = 6)
  - Prevents over-assignment with user-friendly error messages
  - Allows reordering dwellers within same room
  - Real-time capacity validation on drag-and-drop
- **UI Improvements**: Compact room info overlay for better visibility
  - Reduced font sizes and padding for room name, category, tier
  - Room info positioned at top with semi-transparent background
  - Dwellers positioned at bottom
  - All content properly layered with z-index
- **Backend**: Migration to populate image_url for existing rooms
  - Database migration: `fc75e738a303_add_room_image_urls`
  - Automatic URL generation during room build and upgrade
  - Static file serving through `/static` endpoint
- **Frontend**: Vite proxy configuration for image serving
  - `/static` proxy forwards requests to backend
  - Image loading with error handlers and console debugging
  - Test page for verifying image loading functionality

### v2.4.1 Critical Hotfix (January 25, 2026)

**Hotfix Release** - Resolved production Celery worker crashes

- **Critical Fix**: Timezone-naive datetime mixing causing Celery crashes
  - Fixed `death_service.py` - All datetime operations use consistent naive format
  - Fixed `breeding_service.py` - Pregnancy and child aging use naive datetimes
  - All datetime operations: `datetime.now(UTC).replace(tzinfo=None)`
  - Prevents asyncpg DataError: "can't subtract offset-naive and offset-aware datetimes"
- **System Info Fix**: `build_date` now uses timezone-aware datetime for proper ISO format
- **Documentation**:
  - Hotfix deployment guide
  - Timezone-naive analysis (169 occurrences)
  - Release notes
- **Impact**: Celery workers stable, game tick processing uninterrupted, all systems operational
- **Note**: Temporary fix - full timezone-aware migration planned for future release

### v2.4.0 Death System & Infrastructure (January 25, 2026)

**Feature Release** - Complete death mechanics and core services

- **Death System**: Full implementation of dweller mortality
  - Death causes: health, radiation, incidents, exploration, combat
  - Revival system with bottle cap costs
  - Permanent death after 7 days (configurable)
  - Death statistics tracking
  - Epitaph generation
- **Incident Service**: Room-based incident management
- **Security Utilities**: Core authentication and authorization helpers
- **System Endpoint**: Application metadata and version information

### v2.3.0 Pregnancy Debug & Storage Fixes (January 24, 2026)

**Feature Release** - Testing tools and bug fixes

- **Pregnancy Debug Panel**: UI controls for testing pregnancy system (superuser only)
  - Force conception between dwellers
  - Accelerate pregnancy to immediate due date
- **Exploration Fixes**: Item tracking updates in real-time, rewards modal improvements
- **Storage Fixes**: Removed unique constraint on item names (fixes duplicate item crash)
- **Outfit Type Fix**: Fixed KeyError crash with tiered outfits
- **UI Improvements**: Rarity colors use CSS variables, compacted AGENTS.md guide

### v2.2.0 Life & Death Cycle (January 23, 2026)

**Major Feature Release** - Complete dweller mortality system

### Death System Details

- **Death Mechanics**: Full life/death cycle for dwellers
  - Death model fields: `is_dead`, `death_timestamp`, `death_cause`, `is_permanently_dead`, `epitaph`
  - Death causes: health, radiation, incident, exploration, combat
  - Auto-generated epitaphs based on death cause
  - 7-day revival window before permanent death
- **Revival System**: Tiered revival costs by level
  - Level 1-5: 50-250 caps
  - Level 6-10: 450-750 caps
  - Level 11+: 1100-2000 caps (capped)
  - Revival restores 50% max health
- **Backend**: Complete death service and API
  - `POST /api/v1/dwellers/{id}/revive` - Revive dead dweller
  - `GET /api/v1/dwellers/{id}/revival_cost` - Get revival cost
  - `GET /api/v1/dwellers/vault/{id}/dead` - List dead (revivable) dwellers
  - `GET /api/v1/dwellers/vault/{id}/graveyard` - List permanently dead
  - `GET /api/v1/users/me/profile/statistics` - Death statistics
  - Celery task for daily permanent death check
- **Frontend**: Death UI components
  - `DeadDwellerCard.vue` - Card for deceased dwellers
  - `RevivalSection.vue` - Revival cost and action UI
  - `LifeDeathStatistics.vue` - Death stats dashboard
  - `GraveyardView.vue` - Memorial for permanently dead
  - Integration in DwellersView, DwellerDetailView, ProfileView
- **Tests**: 23 backend + 10 frontend tests for death system

### v2.1.3 Backend & Frontend Cleanup (January 22, 2026)

- **Router Consolidation**: Reduced router count from 23 to 20
  - Merged `settings.py` → `game_control.py` (`/game/balance`)
  - Moved `info.py` → `system.py` (`/system/info`)
  - Merged `profile.py` → `user.py` (`/users/me/profile`)
  - Deleted 3 single-endpoint router files, merged tests
- **Frontend Updates**: Updated to use new API endpoints
  - AboutView now uses `/api/v1/system/info`
  - Created systemService in profile module
  - Dynamic version injection from package.json via Vite define

### v2.1.2 Quick Wins Complete (January 22, 2026)

- **Audio Controls**: Stop/pause button for chat audio playback
- **Animated Effects**: Pulsing glow effect on UI elements
- **Navigation**: Motion Vue animations on NavBar dropdowns
- **Room Management**: Unique room filtering (needs verification)
- **Equipment**: Dialog simplification and improved layout
- **AI Generation**: Smart button states (Generate/Regenerate)
- **UI Polish**: Appearance tooltip cleanup

### v2.1.1 UI Polish & Planning (January 22, 2026)

- **UI Improvements**: AI button states (Generate/Regenerate), theme colors, tooltips
- **Equipment**: Dialog improvements, better weapon/outfit display
- **Planning**: v2.2.0 implementation roadmap created
- **Testing**: 670 frontend tests passing

### v2.1.0 Modular Architecture (January 22, 2026)

- **Frontend Refactor**: 10 feature modules, 300+ files reorganized
- **TypeScript**: strictTemplates enabled, all build errors resolved
- **Backward Compat**: Re-exports for smooth migration
- **Docs**: Modular frontend architecture guide (archived)

### v2.0.0 Major Release (January 22, 2026)

- **Deployment**: Production-ready, TrueNAS staging setup
- **Docs**: Agent skills, consolidated documentation
- **Stability**: Relationship service fixes, dependency updates
- **Version**: Aligned with semantic-release automation

### Previous Releases (v1.0-v1.4)

- v1.4.2: Final v1.x release (Jan 21, 2026)
- v1.3-1.4: Email verification, password reset, UX polish
- v1.0-1.2: Core features, breeding system, radio recruitment
- See [CHANGELOG.md](CHANGELOG.md) for complete v1.x history

---

## v2.3.0 Storage & Pregnancy Debug (January 24, 2026)

**Backend Stability & Testability Release**

### P0: Storage Validation (COMPLETE)

- [x] **Storage overflow fix** - Items validated against max_space before transfer
- [x] **Rarity prioritization** - Legendary > rare > uncommon when storage full
- [x] **Storage API endpoint** - `GET /storage/vault/{id}/space`
- [x] **Overflow tracking** - Excess items tracked in `RewardsSchema.overflow_items`
- [x] **Comprehensive tests** - 7 exploration coordinator tests

### P1: Pregnancy Debug (COMPLETE)

- [x] **Force conception** - `POST /pregnancies/debug/force-conception` (superuser-only)
- [x] **Accelerate pregnancy** - `POST /pregnancies/{id}/debug/accelerate` (superuser-only)
- [x] **Simplified config** - No env flags, just superuser access gate
- [x] **Pregnancy CRUD** - Helper with vault access validation

### Testing Improvements

- [x] Enhanced test fixtures (composite fixtures)
- [x] DB initialization tests (97% coverage)
- [x] Room unique property tests
- [x] Test coverage: 46% → 68%

### Known Issues (Deferred)

- **datetime.utcnow() deprecation** - 88 occurrences, deferred to v2.4.0+

---

## Progress Metrics

### Current Stats (Jun 2026)

- **Backend**: 25+ routers, 100+ endpoints, 18+ services, ~70% coverage
- **Frontend**: 60+ Vue components, 10 feature modules
- **Tests**: Frontend 867+, Backend 825+
- **Models**: 20+ database models

### Version Milestones

| Version | Release      | Highlights                                   |
| ------- | ------------ | -------------------------------------------- |
| v2.22.0 | Jun 24, 2026 | @nuxt/ui Migration (custom U* components → @nuxt/ui v4)      |
| v2.23.0 | TBD          | Infrastructure Upgrade (axios→fetch, Chat WebSocket)         |
| v2.21.0 | Jun 24, 2026 | SSE Polish (incident/game-tick SSE, radio datetime fix) |
| v2.20.0 | Jun 22, 2026 | FE Simplification (YAGNI + DRY, dead code purge) |
| v2.19.0 | Jun 21, 2026 | SSE streaming + Dict-to-Pydantic refactoring |
| v2.18.0 | Jun 21, 2026 | Library skills audit, compliance fixes       |
| v2.17.0 | Jun 19, 2026 | Medical storage refactor                     |
| v2.16.0 | Jun 18, 2026 | Accessibility, CRT theme, test fixes         |
| v2.15.0 | Jun 18, 2026 | Dweller visual unification                   |
| v2.14.4 | Jun 17, 2026 | Security dep bumps                           |
| v2.13.1 | May 19, 2026 | Security hardening, non-root containers      |
| v2.13.0 | May 01, 2026 | Dramatiq migration, Celery removal           |
| v2.12.0 | Apr 23, 2026 | Test suite green, MinIO removed              |
| v2.11.0 | Mar 19, 2026 | Vite+ toolchain, dweller recycling           |
| v2.10.9 | Mar 13, 2026 | AI quota system, usage tracking              |
| v2.10.0 | Feb 10, 2026 | Quest & Objective system launch              |
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

_Last updated: 2026-06-24_ (v2.22.0, @nuxt/ui Migration)
