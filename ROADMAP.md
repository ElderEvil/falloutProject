# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## Latest Release

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
  - Extracted 4 helper methods (_parse_rarity_to_enum, _create_weapon_from_loot, _create_outfit_from_loot, _create_junk_from_loot)
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
import { useMagicKeys } from '@vueuse/core'

const { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, b, a } = useMagicKeys()
const sequence = ref('')

watch([ArrowUp, ArrowDown, ArrowLeft, ArrowRight, b, a], () => {
  // Track key sequence and check for Konami Code
  // ↑ ↑ ↓ ↓ ← → ← → B A
})
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
  <canvas
    ref="quantumCanvas"
    class="fixed inset-0 pointer-events-none z-[9999]"
  />
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
    - `HOTFIX_TIMEZONE_NAIVE.md` - Deployment guide (184 lines)
    - `TIMEZONE_NAIVE_ANALYSIS.md` - Analysis of 169 timezone issues (1,062 lines)
    - `RELEASE_NOTES_v2.4.1.md` - Complete release notes (206 lines)
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
- **Docs**: [MODULAR_FRONTEND_ARCHITECTURE.md](docs/MODULAR_FRONTEND_ARCHITECTURE.md)

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

## Next Sprint: UX Enhancements (P2)

**Target: v2.4.0**

### Animation & Motion

- [ ] **Motion Vue Integration** - Smooth animations throughout app
- [ ] **Sidebar Navigation Animations** - Sliding transitions
- [ ] **Component Transitions** - Enter/leave animations for modals, cards
- [ ] **Room Action Feedback** - Animated build/upgrade/destroy responses

### Future UX (P3)

- [x] ~~Training drag-and-drop UI~~ → COMPLETED
- Sound effects (terminal UI sounds, ambient audio)
- Room damage & repair mechanics
- Sentry integration for error tracking

---

## Planned Features (P4 - Future)

### Phase 1: Core Gameplay (Feb 2026)

- Room management improvements (optimal dweller suggestions)
- Crafting system (weapons/outfits with recipes)

### Phase 2: Advanced Gameplay (Mar 2026)

- Combat enhancements (statistics, log/replay)
- Exploration enhancement (events with choices, journal)
- Family visualization (relationship graph, family tree)

### Phase 3: Endgame (Apr 2026)

- Pet system, legendary dwellers
- Merchant system, economy
- Achievement system, daily/weekly challenges
- **Dead Dweller Reuse System**
    - Soft-delete permanently dead dwellers (keep data)
    - Reuse as raiders attacking other vaults
    - Transformation chance: ghoul, synth, super mutant
    - Cross-vault encounters with former dwellers

### Phase 4: Multiplayer (May 2026)

- Social features (friends, vault visits, leaderboards)
- Cloud saves, multi-device sync

---

## Technical Debt (P3)

### Backend

- [x] Router consolidation: Merge small routers (settings, info) into logical groupings
- [ ] Storage migration: MinIO → RustFS (lighter, faster)
- [ ] Performance testing: Locust in nightly CI
- [ ] Datetime consistency: Migrate all `datetime.utcnow()` and naive `datetime.now()` to aware `datetime.now(UTC)`
- [ ] Test coverage: Target 80% (both FE/BE)

### Frontend

- [x] ~~Vue architecture refactor~~ → COMPLETED (v2.1.0)
- [ ] Component refactoring: Break down large components (DwellerCard 813 lines, RoomGrid 814 lines)

### DevOps

- [ ] Deployment optimization ([docs/DEPLOYMENT_OPTIMIZATION.md](docs/DEPLOYMENT_OPTIMIZATION.md))
- [x] ~~Docker build automation~~ → COMPLETED (build.yml)

---

## Progress Metrics

### Current Stats (January 24, 2026)

- **Backend**: 22+ routers, 92+ endpoints, 15+ services, 68% coverage
- **Frontend**: 55+ Vue components, 10 feature modules
- **Tests**: Frontend 683, Backend 388
- **Models**: 18+ database models

### Version Milestones

| Version | Release      | Highlights                             |
|---------|--------------|----------------------------------------|
| v2.9.0  | Feb 07, 2026 | Chat exploration actions, room agent   |
| v2.8.5  | Feb 04, 2026 | Code quality, refactoring              |
| v2.8.4  | Feb 03, 2026 | Test infrastructure fixes              |
| v2.3.0  | Jan 24, 2026 | Storage validation, pregnancy debug    |
| v2.2.0  | Jan 23, 2026 | Death system complete                  |
| v2.1.0  | Jan 22, 2026 | Modular frontend architecture          |
| v2.0.0  | Jan 22, 2026 | Major release, deployment ready        |
| v1.4.2  | Jan 21, 2026 | Final v1.x release                     |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

## Code Quality Audit Results (January 29, 2026)

### Duplicates Identified

| Category | Files Affected | Lines | Priority |
|----------|----------------|-------|----------|
| Empty CRUD classes | weapon.py, outfit.py, junk.py | ~30 | 🔴 Critical |
| Vault filtering logic | weapon.py, outfit.py endpoints | 25 each | 🔴 Critical |
| Seeding functions | seed_quests.py, seed_objectives.py | ~65 each | 🟡 High |
| Query patterns | 10+ CRUD files | ~200 total | 🟢 Medium |
| Exception handling | 28 endpoint files | ~56 total | 🟢 Medium |

### Issues by Severity

**🔴 Critical (3 issues)**
- Unimplemented TODO stub (`celery_task.py:26`)
- Broken test isolation (2 test files)
- `game_loop.py` too large (767 lines)

**🟡 High Priority (11 issues)**
- 11 bare `except Exception` handlers with silent failures
- 6 functions with complexity suppressions (noqa: C901, PLR0912, PLR0915)
- Hardcoded magic numbers in 5+ files
- N+1 query patterns in game loop
- Large transaction in vault initialization

**🟢 Medium Priority (9 issues)**
- Debug print statement in migration
- Repeated notification error handling (5+ services)
- Datetime handling duplication (10+ locations)
- Performance concerns in exploration coordinator
- Inconsistent service instantiation patterns

### Metrics
- **Total Lines of Duplicate Code**: 200-300 lines
- **Files with Issues**: 35+ files
- **TODO Comments**: 7 locations
- **Complexity Violations**: 6 functions
- **Test Coverage**: 68% (target: 80%)

---

## Upcoming Releases

### v2.9.1 - UX Papercuts & Docs (Completed - February 8, 2026)

**Focus**: Quick UX fixes and documentation updates

**Completed:**
- ✅ ChangelogModal single footer CTA (Got it only)
- ✅ Vault experimental warning banner (create + list)
- ✅ DwellerChat message-id based keys for WebSocket correlation

### v2.9.2 - Boosted Start (Completed - February 8, 2026)

**Focus**: Opt-in boosted vault creation

**Completed:**
- ✅ Opt-in "Boosted Start" vault creation option
- ✅ Creates vault with 6 dwellers (3F/3M), 1000 caps, and starter resources
- ✅ Reduced initial build costs for faster early game

### v2.9.3 - Component Refactoring & Quick Wins (Completed - February 8, 2026)

**Focus**: Component splitting and backend code quality

**Completed:**
- ✅ RoomDetailModal deep split into 7 components + 4 composables
- ✅ DwellerChat light split (logic extraction)
- ✅ Backend service logging added
- ✅ Dead code removal (get_spreading_incidents)
- ✅ Version bump to 2.9.3 (BE + FE)

### v2.9.4 - Frontend Quick Wins (Planned)

**Focus**: Time-boxed frontend improvements

**Planned:**
- UI polish (a11y, loading states)
- DX improvements (type safety, remove debug logs)
- Add missing store tests

### v2.9.5 - Stabilization (Planned)

**Focus**: Regression fixes and final polish

**Planned:**
- Regression fixes from 2.9.1-2.9.4
- Final polish
- Version bump preparation

---

*Last updated: February 8, 2026*
