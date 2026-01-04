# Fallout Shelter Game - Development Roadmap

## 🎯 Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## 🚧 Current Sprint: v1.9 Happiness & UI Completion (IN PROGRESS)

### 🔥 Top Priorities (Reorganized January 3, 2026)

#### 1. Happiness System Implementation (NEW TOP PRIORITY)

**Goal**: Complete the happiness system to make vault management more engaging

- [ ] **Happiness Decay & Gain Mechanics**
    - Implement happiness decay over time based on vault conditions
    - Resource shortages reduce happiness (power/water/food)
    - Successful room production increases happiness
    - Combat/incidents reduce happiness
    - Radio room happiness boost mode (backend already exists)

- [ ] **Happiness UI Indicators**
    - Happiness bars/indicators in dweller cards
    - Vault-wide happiness average in overview
    - Color-coded happiness levels (red/yellow/green)
    - Happiness change notifications
    - Low happiness warnings

- [ ] **Happiness-Based Events**
    - Low happiness triggers negative events
    - High happiness provides bonuses (production, XP)
    - Happiness affects relationship formation
    - Happiness affects radio recruitment success

#### 2. Infrastructure & Operations

**Goal**: Add operational visibility and maintainability before adding more features

- [x] **Messages Model & Real-time Communication** ✅ (v1.7 - Jan 3, 2026)
    - Created `ChatMessage` model for persistent user-dweller conversations
    - Created `Notification` model for one-way system notifications (level-ups, births, recruitment)
    - Message persistence in database with relationships (user_id, vault_id, dweller_id)
    - **WebSocket infrastructure** with ConnectionManager for real-time delivery
    - Backend notification service integrated with game events
    - Frontend chat history loading and display
    - Chat persistence across sessions
    - Navigation fixes (chat → dwellers button uses correct vault ID)

- [x] **Structured Logging** ✅ (v1.7 - Jan 3, 2026)
    - Centralized logging configuration with `setup_logging()`
    - Replaced `print()` statements with `logger` (4 occurrences fixed)
    - Request ID tracking via middleware with `contextvars`
    - Environment-based configuration (LOG_LEVEL, LOG_JSON_FORMAT)
    - JSON formatter for production, human-readable for development
    - Startup logging with environment details
    - Request ID in all log records and response headers

- [ ] **Sentry Integration**
    - Error tracking and monitoring for production issues
    - Performance monitoring (APM) for slow endpoints
    - Frontend + Backend error capture
    - User feedback integration for bug reports

- [ ] **Backend Config Separation** (Pydantic Settings)
    - `GameRulesConfig`: spawn rates, costs, durations, XP curves
    - `AIConfig`: model selection, API keys, temperature, max tokens
    - `AppConfig`: environment-based settings (dev/staging/prod)
    - Runtime config validation with Pydantic v2
    - Easy tweaking of game balance without code changes

#### 3. Small High-Impact UX Features

**Goal**: Quick wins that significantly improve user experience

- [ ] **Click Room from Dweller List**
    - Make room badge clickable in dweller list/grid view
    - Navigate to vault view and highlight/open room detail modal
    - Improve navigation flow between dwellers and rooms

- [ ] **Dweller Stats in List View**
    - Add SPECIAL stats to list view (horizontal space available)
    - Show S.P.E.C.I.A.L. values or relevant stat for assigned room
    - Display `is_adult` status (adult/child/teen) with icon
    - Better information density without clutter

- [ ] **Regenerate Bio/Image Buttons**
    - Add regeneration button(s) in DwellerDetailView
    - Separate controls for bio vs. image regeneration
    - Display visual attributes in UI (hair color, skin tone, eye color, etc.)
    - Loading states during AI regeneration

- [ ] **Terminal-themed Login Screen**
    - Vault-Tec themed login messages (not generic "Welcome back")
    - ASCII art or terminal boot sequence animation
    - Retro computer login aesthetic
    - More immersive fallout-themed copy
    - **A/B Testing**: Terminal theme version created (`LoginFormTerminal.vue`) - test against original

#### 4. Complete Training System UI (Frontend)

- [ ] Training queue display in TrainingView
- [ ] Progress indicators for active training sessions
- [ ] Training completion notifications
- [ ] Verify auto-start functionality with backend

#### 5. Wasteland Expedition Screen (NEW FEATURE)

- [ ] Add "Wasteland" to SidePanel navigation (between Dwellers and Relationships)
- [ ] Create dedicated WastelandView page (not just panel in VaultView)
- [ ] Full-screen expedition management interface
- [ ] Detailed exploration stats and history per dweller
- [ ] Send dwellers to wasteland from dedicated screen
- [ ] **Real-time event notifications** via WebSocket/SSE
    - Live updates for exploration progress
    - Event notifications (combat, discovery, level-up) appear as messages
    - Toast notifications + persistent message log
    - No polling needed - instant updates when events occur

### What's Done ✅

- **Quest & Objective Systems (v1.8 - Jan 3, 2026)**
    - Quest CRUD with visibility tracking and assignment/completion
    - Objective system with progress tracking
    - Frontend QuestsView with Overseer's Office requirement
    - ObjectivesView with active/completed tabs
    - Navigation reorganization (hotkey conflicts fixed)
    - UI theme consistency (all views use CSS custom properties)
    - 26 new frontend tests (15 quest store + 11 QuestsView)
    - 7 backend quest CRUD tests
- **Chat & Notification system (v1.7 - Jan 3, 2026)**
    - ChatMessage & Notification models with database persistence
    - WebSocket infrastructure with ConnectionManager
    - Real-time message delivery
    - Chat history loading and restoration
    - Backend notification service for game events
    - Dweller name sorting fixed (backend now handles "name" sort properly)
    - Navigation bug fixed (chat → dwellers button uses correct vault ID)
- **Training system backend (v1.6 - Jan 2, 2026)**
    - Time-based SPECIAL stat training
    - Room tier bonuses for faster training
    - Capacity management and auto-completion
    - 11 comprehensive service tests

---

## ✅ Completed Features

### Core Infrastructure

- [x] **FastAPI Backend** with SQLModel + Pydantic v2
- [x] **PostgreSQL 18** with UUID v7 support
- [x] **Vue 3.5 Frontend** with TypeScript and Composition API
- [x] **Authentication System** (JWT-based)
- [x] **Redis + Celery** task queue
- [x] **MinIO** object storage for images
- [x] **Docker/Podman** containerization

### User Management

- [x] User registration and login
- [x] User profiles
- [x] Multi-vault support per user
- [x] Superuser admin capabilities

### Vault System

- [x] Vault CRUD operations
- [x] Vault storage management
- [x] Bottle caps (currency) system
- [x] Vault statistics dashboard
- [x] Game control panel (pause/resume/fast-forward)

### Dweller Management

- [x] **SPECIAL Stats System** (Strength, Perception, Endurance, Charisma, Intelligence, Agility, Luck)
- [x] Dweller CRUD operations with full attributes
- [x] **AI-Generated Content**:
    - Bio/backstory generation
    - Portrait generation (DALL-E integration)
    - Visual attributes (hair color, skin tone, etc.)
- [x] Dweller status tracking (idle, working, exploring, etc.)
- [x] Health, happiness, radiation tracking
- [x] **Stimpack and RadAway inventory** ✅ (v1.7 - Jan 3, 2026)
    - Model fields and storage (0-15 range)
    - Backend REST API endpoints for usage
    - Stimpack heals 40% of max health
    - RadAway removes 50% of radiation
    - Frontend display in DwellerCard with inventory counts
    - Use item buttons with validation (disabled when not usable)
    - Toast notifications for success/error states
- [x] Gender and rarity system
- [x] Level and experience progression
- [x] **Equipment System**:
    - Weapons (melee/ranged with damage stats)
    - Outfits (SPECIAL stat bonuses)
    - Equip/unequip functionality
    - Equipment inventory UI with filtering

### Room System

- [x] Room types (production, living quarters, storage, etc.)
- [x] Room capacity management
- [x] Room level and upgrade system (backend + frontend)
- [x] Dweller assignment to rooms (backend + drag-and-drop UI)
- [x] **Room Building UI**:
    - 4×8 grid layout visualization
    - Build mode with room selection menu
    - Click-to-place room placement
    - Cost calculation and caps deduction
- [x] **Room Upgrade System**:
    - Tier progression (1→2→3)
    - Upgrade cost calculation (t2/t3_upgrade_cost)
    - Capacity and output recalculation
    - Visual upgrade button with cost display
- [x] **Room Management**:
    - Destroy rooms with partial refund
    - Room selection and detail view
    - Dweller assignment via drag-and-drop
- [x] **Room Detail View** (v1.3):
    - Comprehensive room information modal
    - Real-time production rate calculations
    - Efficiency metrics (dweller capacity utilization)
    - Assigned dwellers list with relevant SPECIAL stats
    - Clickable dweller cards with navigation to dweller details
    - Management actions (upgrade, destroy, unassign all)
    - Resource type and output display for production rooms
    - Tier-based production multiplier visualization

### Exploration System

- [x] Send dwellers to wasteland
- [x] Exploration duration tracking
- [x] Item discovery during exploration
- [x] Experience and caps rewards
- [x] **Exploration Rewards UI**:
    - Terminal-themed rewards modal
    - Experience, caps, items, distance display
    - Auto-complete at 100% progress
    - Manual complete button

### Combat & Incident System

- [x] **Incident Management** (Raider Attacks, Fires, Infestations)
    - 8 incident types (raiders, radroaches, mole rats, deathclaws, fires, radiation leaks, electrical failures, water
      contamination)
    - Dynamic spawn system (5% per hour)
    - Difficulty scaling (1-10) with weighted distribution
    - Incident spreading mechanics (60s intervals, max 3 spreads)
- [x] **Combat Resolution System**
    - Dweller combat power calculation (SPECIAL stats + equipment + level)
    - Auto-combat processing in game loop
    - Damage distribution to dwellers
    - Enemy defeat tracking
    - Auto-resolution on victory
- [x] **Loot System**
    - Difficulty-based loot generation
    - Caps rewards (50-1000 based on difficulty)
    - Equipment drops (common/uncommon/rare tiers)
    - Junk materials rewards
- [x] **Combat UI Components**:
    - Real-time incident alert banner with pulsing animations
    - Combat modal with status details and progress
    - Room incident overlays with icons
    - Manual resolve/abandon functionality
    - Auto-refresh every 5-10 seconds
- [x] **Game Loop Integration**:
    - Incident processing in tick system
    - Combat status updates
    - Spread mechanics execution

### Objectives & Quests

- [x] **Quest System** ✅ (v1.8 - Jan 3, 2026)
    - Quest CRUD operations with visibility tracking
    - Quest assignment and completion endpoints
    - VaultQuestCompletionLink model for progress tracking
    - Frontend QuestsView with Overseer's Office requirement
    - Quest store with full state management
    - 7 backend tests + 15 frontend store tests + 11 component tests
- [x] **Objective System** ✅ (v1.8 - Jan 3, 2026)
    - Objective creation and tracking
    - Objective completion logic
    - VaultObjectiveProgressLink for progress tracking
    - Frontend ObjectivesView with active/completed tabs
    - Progress bars and theme-consistent UI

### Items & Resources

- [x] **Weapons**:
    - Weapon types (melee, ranged)
    - Weapon subtypes (fist, blade, pistol, rifle, etc.)
    - Damage ranges and stat bonuses
    - Rarity system (common, uncommon, rare, legendary)
- [x] **Outfits**:
    - Outfit types (casual, work, combat, special)
    - SPECIAL stat bonuses
    - Rarity system
- [x] **Junk Items**:
    - Crafting materials
    - Scrapping equipment for junk
- [x] Item storage system

### AI Integration

- [x] **PydanticAI Chat System** ✅ (v1.7):
    - In-character dweller conversations
    - Context-aware responses based on dweller stats and mood
    - **Chat history persistence** with ChatMessage model
    - Chat history restored on page re-entry
    - Database-backed message storage (user ↔ dweller conversations)

### Frontend UI/UX

- [x] **Terminal-Themed Design System**:
    - Custom TailwindCSS v4 configuration
    - Scanline and CRT effects
    - Green monochrome aesthetic
- [x] **8 Custom UI Components**:
    - UButton, UInput, UCard, UModal
    - UTabs, UTooltip, UBadge, USpinner
- [x] **Responsive Layouts**:
    - Collapsible side navigation
    - Grid and list view toggle for dwellers
    - Mobile-friendly design
- [x] **State Management** with Pinia 3.0
- [x] **Toast Notifications** system
- [x] **Loading Skeletons** for better UX
- [x] **Equipment UI**:
    - Weapon and outfit cards with stats
    - Inventory modal with tabs
    - Equip/unequip actions with real-time updates

### Testing & Quality

- [x] **Frontend Tests** (Vitest) - comprehensive coverage
    - Room store tests (build, upgrade, destroy)
    - Dweller management tests
    - Exploration tests
    - Auth and profile tests
- [x] **Backend Test Suite** (pytest)
    - Room API tests including upgrade functionality
    - CRUD operation tests
    - Integration tests
- [x] **Code Quality Tools**:
    - Ruff (linting/formatting)
    - Oxlint (frontend)
    - Type checking (ty for backend, vue-tsc for frontend)
- [x] **Pre-commit Hooks** (prek)

---

## 🎯 Next Sprint: v1.8 Responsive & Adaptive UI

### Goal: Make the game fully responsive across devices

#### 1. **Responsive Design System**

- [ ] **Breakpoint Strategy**
    - Mobile: 320px-767px (touch-first, simplified)
    - Tablet: 768px-1023px (hybrid, medium complexity)
    - Desktop: 1024px+ (full features, current behavior)

- [ ] **VaultView Adaptations**
    - Room grid: horizontal scroll on mobile, 2-column on tablet
    - Resource bars: stack vertically on mobile
    - Control panel: bottom sheet on mobile vs. top bar on desktop

- [ ] **Dweller List Adaptations**
    - Card-only layout on mobile (no list view option)
    - Reduced columns on tablet (2-3 vs 4-5)
    - Touch-friendly tap targets (min 44px)
    - Swipe gestures for actions

- [ ] **Navigation Adaptations**
    - Bottom navigation bar on mobile (5 key sections)
    - Collapsible sidebar on tablet/desktop (current behavior)
    - Consider hamburger menu for mobile

- [ ] **Modal Behavior**
    - Full-screen modals on mobile (slide-up animation)
    - Centered modals on desktop (current behavior)
    - Swipe-to-dismiss on mobile

#### 2. **Navbar Improvements or Removal**

**Option A (Recommended)**: Remove top navbar entirely

- Move profile menu to bottom of SidePanel
- Move theme switcher to Settings view in SidePanel
- Move logout to Profile submenu
- Cleaner UI, more screen space for vault

**Option B**: Make navbar contextual and useful

- Show vault-specific actions when in vault view
- Show dweller actions when viewing dweller
- Breadcrumb navigation for deep pages

#### 3. **Resource Warning UI** (Complete existing feature)

- [ ] Toast notifications for low/critical resources
    - Warning: <20% resources (yellow toast)
    - Critical: <10% resources (red toast, pulsing)
    - Auto-dismiss after 5 seconds or user action
- [ ] Visual indicators in resource bars
    - Yellow glow at <20%
    - Red pulsing at <10%
- [ ] Power outage effects
    - Dim rooms when power < 0
    - Show offline icon overlay
    - Disable room production

---

## 📋 Planned Features

### UI/UX Polish Backlog

#### Future A/B Tests & UI Experiments
- [ ] **Terminal Login Theme** - A/B test `LoginFormTerminal.vue` vs current simple login
- [ ] **Vault-Tec Corporate Naming** - Consider more "corporate/technical" naming for RelationshipsView
    - Examples: "Paired Dwellers" vs "Partners", "Gestation Cycles" vs "Pregnancies"
    - May be too corporate/clinical - test with users first
- [ ] **Scoped Styles Refactor** - Move component-specific styles to global theme system
    - Maintain consistent styling across app
    - Reduce duplication and improve maintainability

### Phase 1: Core Gameplay Loop (Jan-Feb 2026)

#### Room Management

- [x] **Room Assignment UI** ✅
    - Drag-and-drop dweller assignment
    - Room detail panel with current workers
- [x] **Room Upgrades** ✅
    - Multi-level room upgrades (Tier 1→2→3)
    - Increased capacity and efficiency
    - Visual upgrade button in UI
- [x] **Room Production** ✅
    - Resource generation (power, water, food)
    - Production rates based on dweller stats
    - Resource consumption and balance
- [ ] **Training Room Capacity Formula**
    - Calculate capacity based on room size (e.g., size/3*2 or similar)
    - Replace static capacity field with dynamic calculation
- [ ] **Optimal Dweller Suggestions**
    - Suggest best dwellers for room based on SPECIAL
    - Efficiency indicators

#### Resource Management

- [x] **Power, Water, Food Systems** ✅
    - Resource bars in vault dashboard
    - Display current/max values
- [x] **Resource Consumption & Production** ✅
    - Active consumption rates (backend complete)
    - Production rates based on dweller stats (backend complete)
    - Warning system for low resources (backend complete)
    - Game loop integration with ResourceManager
- [ ] **Resource Warning UI** (Frontend)
    - Toast notifications for resource warnings
    - Visual indicators when resources critical
    - Outage effects UI (no power = rooms show as inactive)
- [ ] **Storage System UI**
    - Vault storage inventory view
    - Item categorization (weapons, outfits, junk)
    - Bulk actions (move, delete, scrap)
    - Search and filter

#### Crafting System

- [ ] **Weapon Crafting**
    - Recipe system
    - Junk requirements
    - Crafting time and success rate
- [ ] **Outfit Crafting**
    - Recipe system
    - Material requirements
- [ ] **Room Crafting/Workshop**
    - Dedicated crafting room
    - Queue system for multiple crafts

### Phase 2: Advanced Gameplay (Feb-Mar 2026)

#### Combat & Defense Enhancements

- [x] **Raider Attacks** ✅ (Jan 2026)
    - Random raid events with 5% hourly spawn rate
    - Combat resolution based on dweller equipment and stats
    - Damage to dwellers with health tracking
    - Loot from defeated raiders (caps + equipment)
- [x] **Incident System** ✅ (Jan 2026)
    - 8 incident types (raiders, radroaches, mole rats, deathclaws, fires, radiation, electrical, water)
    - Room-based incident tracking with spread mechanics
    - Real-time UI indicators and alerts
- [ ] **Enhanced Combat Features**
    - Room damage system
    - Dweller death mechanics
    - Incident prevention items (sprinklers, security stations)
    - Combat statistics and history

#### Exploration Enhancement

- [ ] **Detailed Exploration Events**
    - Encounter system (combat, discovery, dialogue)
    - Choice-based outcomes
    - Death risk management
- [ ] **Exploration Log/Journal**
    - Event history per dweller
    - Loot summary
- [ ] **Recall Mechanism**
    - Manual recall button
    - Auto-recall at low health
    - Return time based on distance

#### Dweller Progression

- [x] **Core Leveling System** ✅ (v1.5 - Jan 2, 2026)
    - Exponential XP curve (100 * level^1.5) for 1-50 progression
    - Multiple XP sources with bonuses (exploration, combat)
    - Auto level-up with +5 HP per level and full heal
- [x] **Training Rooms ✅ (v1.6 - Jan 2, 2026)**
    - Time-based SPECIAL stat training (2-6.5 hours)
    - Room tier bonuses (T2: 25% faster, T3: 40% faster)
    - Capacity management, progress tracking, auto-completion
- [ ] **Leveling UI Enhancements (Frontend)**
    - Level-up notifications
    - Training UI components
        - XP progress bars

#### Breeding & Family

- [x] **Dweller Relationships** ✅ (Jan 2026)
    - Relationship tracking (acquaintance, friend, romantic, partner, ex)
    - Affinity system (0-100)
    - Romantic relationships in living quarters
    - Compatibility scoring system
    - Quick-pair testing endpoint
- [x] **Pregnancy & Birth** ✅ (Jan 2026)
    - Pregnancy duration (3 hours real-time)
    - Conception chance for partners in living quarters
    - Child growth stages (child → teen → adult)
    - Inherited SPECIAL traits from parents
    - Pregnancy tracking UI with progress bars
- [ ] **Relationship Visualization**
    - Visual relationship graph/network diagram
    - Connection lines between related dwellers
    - Family tree visualization
    - Partner and parent-child indicators
    - Interactive relationship explorer

### Phase 3: Endgame & Polish (Mar-Apr 2026)

#### Advanced Systems

- [x] **Radio Room** ✅ (Jan 2026)
    - Attract new dwellers from wasteland
    - Recruitment rate based on vault happiness and charisma
    - Manual recruitment for 500 caps
    - Mode toggle: Recruitment vs. Happiness boost
    - Speedup multiplier (1.0x-10.0x) per radio room
    - Initial vault includes radio room
- [ ] **Pet System**
    - Pets with special bonuses
    - Pet assignment to dwellers
- [ ] **Legendary Dwellers**
    - Special named characters
    - Unique abilities and high stats
    - Special quests to unlock

#### Economy & Trading

- [ ] **Merchant System**
    - Traveling merchants
    - Buy/sell items
    - Special deals and rotation
- [ ] **Caps Management**
    - Earning caps (selling items, quests, exploration)
    - Spending (upgrades, purchases)
    - Budget management

#### Enhanced Objectives

- [ ] **Achievement System**
    - Steam-like achievements
    - Reward system
    - Progress tracking
- [ ] **Daily/Weekly Challenges**
    - Time-limited objectives
    - Special rewards
- [ ] **Story Campaign**
    - Multi-stage quest line
    - Narrative progression
    - Unique rewards

#### UI/UX Polish

- [ ] **Empty States**
    - No dwellers placeholder
    - No vaults placeholder
    - No rooms placeholder
- [ ] **Animations**
    - Dweller movement in vault
    - Room production animations
    - Smooth transitions
- [ ] **Sound Effects**
    - UI interactions
    - Ambient vault sounds
    - Alert sounds
- [ ] **Tutorial System**
    - First-time user onboarding
    - Guided vault setup
    - Feature introductions

### Phase 4: Multiplayer & Social (Apr-May 2026)

#### Social Features

- [ ] **Friend System**
    - Add friends
    - Visit friend vaults
    - Gift items
- [ ] **Leaderboards**
    - Vault population
    - Total caps
    - Highest level dweller
    - Exploration records
- [ ] **Co-op Quests**
    - Multi-player objectives
    - Shared rewards

#### Cloud Saves & Sync

- [ ] **Cloud Save System**
    - Automatic backups
    - Multi-device sync
- [ ] **Export/Import**
    - Save file management
    - Backup downloads

---

## 🔮 Future Considerations

### Advanced AI Features (Deferred to Post-MVP)

> **Note**: These AI features are moved to later phases to focus on core gameplay MVP. Basic PydanticAI chat already
> exists and works well.

- [ ] **Enhanced AI Dweller Chat with Tools**
    - PydanticAI tool integration for dweller actions
    - Dwellers request actions via chat (equip weapon, explore, train)
    - Multi-turn conversation memory and context
    - Emotional state system influencing responses
- [ ] **AI Personality Engine**
    - Dynamic personality responses based on SPECIAL stats
    - Personality evolution over time based on experiences
    - Context-aware conversations (remembers vault state, recent events)
- [ ] **AI-Driven Content Generation**
    - AI-generated exploration narratives
    - Dynamic quest and storyline generation
    - Procedural event generation
- [ ] **Social AI Features**
    - Dweller-to-dweller conversations
    - Relationship dynamics influenced by AI
    - AI-mediated conflict resolution

### Potential Features (Backlog)

- [ ] Mobile app (React Native or Flutter)
- [ ] Mod support and custom content
- [ ] Steam integration
- [ ] Advanced analytics dashboard for vault performance
- [ ] Seasons/Events (holiday themes, special events)
- [ ] Vault customization (color schemes, layouts)
- [ ] Multiplayer vault raids
- [ ] Community marketplace for trading

### Technical Debt & Improvements

#### v1.9.5 Technical Improvements & Chores (IN PROGRESS - Jan 2026)

**Goal**: Code quality improvements, performance optimizations, and developer experience enhancements

##### 1. Game Balance Configuration Migration to Pydantic Settings ✅
**Priority: Medium | Impact: High** ✅ **COMPLETED (Jan 4, 2026)**

**Problem**: 249 lines of hardcoded constants in `game_balance.py`, no validation, difficult to test different configurations

**Solution**: Migrate to Pydantic BaseSettings with environment variable support

- [x] **Create `app/core/game_config.py`** with Pydantic BaseSettings ✅
- [x] **Define Nested Config Classes** ✅:
  - `GameLoopConfig`: tick intervals, catchup limits
  - `IncidentConfig`: spawn rates, difficulties, weights, spread mechanics, vault door incidents
  - `CombatConfig`: raider power, dweller combat weights, loot ranges
  - `HealthConfig`: regen rates, thresholds, decay rates
  - `HappinessConfig`: decay/gain rates, bonuses, thresholds
  - `TrainingConfig`: durations, tier multipliers, stat limits
  - `ResourceConfig`: production/consumption rates, warning thresholds
  - `RelationshipConfig`: affinity rates, romance thresholds
  - `BreedingConfig`: conception chance, pregnancy duration, inheritance
  - `LevelingConfig`: XP curves, HP gains, max level
  - `RadioConfig`: recruitment rates, tier multipliers, manual cost
- [x] **Add `.env` Support** for balance tweaking (e.g., `INCIDENT_SPAWN_CHANCE=0.10`) ✅
- [x] **Replace Imports** ✅: `game_balance.CONSTANT` → `game_config.incident.spawn_chance`
  - Updated all services (training, leveling, relationship, radio, breeding, wasteland, game_loop, happiness, incident)
  - Updated API endpoints (radio, relationship)
  - Updated models (dweller)
  - Updated all test files (5 test suites)
- [x] **Add Validation** ✅: Ensure valid ranges (e.g., 0.0 ≤ spawn_chance ≤ 1.0)
- [x] **Add Logging** ✅: Config logs key settings on startup
- [x] **Delete Old File** ✅: Removed `app/config/game_balance.py`
- [x] **Fix FIXME Statements** ✅:
  - Added `vault_door_incidents` property to IncidentConfig
  - Fixed happiness service to use `resource.low_threshold`

**Achieved Benefits**:
- ✅ Easy A/B testing of game balance via environment variables
- ✅ Runtime validation catches config errors on startup
- ✅ Single source of truth with type hints and docstrings
- ✅ All configuration centralized and type-safe
- ✅ Startup logging shows loaded configuration values

##### 2. Auth Routes Consolidation ✅
**Priority: Low | Impact: Medium** ✅ **COMPLETED (Jan 4, 2026)**

**Problem**: Auth split across `login.py` (2 endpoints) and `auth.py` (5 endpoints), confusing organization

**Solution**: Merge into single `auth.py` router

- [x] **Move Login Endpoints** from `login.py` to `auth.py` ✅ (Jan 4, 2026)
  - `POST /login/access-token` → `POST /auth/login`
  - `POST /login/refresh-token` → `POST /auth/refresh`
  - `POST /logout` → `POST /auth/logout`
- [x] **Update Frontend** API calls (3 files affected) ✅
  - `authService.ts`: Updated login, refresh, logout endpoints
  - `authService.test.ts`: Updated test assertions
- [x] **Update Router** registration in `app/api/v1/api.py` ✅
- [x] **Delete** `login.py` ✅
- [x] **Update Backend Tests** ✅
  - `test_auth.py`: Updated all 11 endpoint references
  - `utils/user.py`: Updated authentication helper
  - `utils/utils.py`: Updated superuser token helper
- [x] **Update Load Tests** ✅
  - `locust/utils.py`: Updated login endpoint
  - `locust/tasks/auth_tasks.py`: Updated auth task endpoints
- [x] **Update OAuth2 Config** ✅
  - `api/deps.py`: Updated OAuth2PasswordBearer tokenUrl
- [x] **Update OpenAPI Tags** (all under "Authentication") ✅
- [x] **Run Tests** to verify no regressions ✅
  - Backend: 300 passed (fixed 73 auth-related errors)
  - Frontend auth tests: 15/15 passed

**Achieved Benefits**:
- ✅ Single auth module, easier to navigate
- ✅ Consistent URL structure (`/auth/*`)
- ✅ Reduced cognitive load for API consumers
- ✅ All references updated (tests, load tests, OAuth2 config)

##### 3. Incident Service N+1 Query Optimization ✅
**Priority: High | Impact: High**

**Problem**: `incident_service.py:process_incident()` has N+1 query issues:
- Line 177: Individual dweller refresh inside loop (unnecessary)
- Line 198-202: Individual vault fetch per incident for cap updates
- Current: ~10-15 queries per incident

**Solution**: Eliminate redundant queries

- [x] **Training Service Optimization** ✅ (Jan 4, 2026)
  - Batch dweller fetching in training CRUD
  - Optimized training service methods with optional dweller parameter
  - Game loop batch operations (N queries → 2 queries)
  - 60-80% query reduction achieved
- [x] **Remove Individual Dweller Refresh** (line 177) ✅ (Jan 4, 2026)
  - SQLAlchemy session tracks objects, no re-fetch needed
  - Removed unnecessary `await db_session.execute(select(Dweller)...)` refresh
- [x] **Batch Vault Updates** for cap rewards ✅ (Jan 4, 2026)
  - Collect caps from multiple incidents in game loop
  - Single vault fetch + update at game loop end (`game_loop.py:518-526`)
  - Caps returned in process_incident result dict
- [x] **Pre-fetch Equipment** for combat ✅ (Jan 4, 2026)
  - Use `selectinload(Dweller.weapon, Dweller.outfit)` in initial query (line 147-158)
  - Enabled weapon damage calculation (line 359-360)
- [x] **Fixed Happiness Service Tests** ✅ (Jan 4, 2026)
  - Fixed `test_active_incident_reduces_happiness` assertion
  - Fixed `test_partner_bonus` relationship creation and assertion
  - All 15 happiness tests passing

**Achieved Impact**:
- Before: ~10-15 queries per incident
- After: ~3-4 queries per incident
- **60-70% query reduction** achieved for incident-heavy vaults
- Tests: 308 passed (up from 305), 8 failed (down from 10)

##### 4. Wasteland Service Optimization ✅
**Priority: Medium | Impact: Medium** ✅ **COMPLETED (Jan 4, 2026)**

**Problem**: `wasteland_service.py:process_event()` was re-fetching exploration objects from database unnecessarily

**Solution**: Use model methods directly instead of CRUD re-fetches

- [x] **Optimize add_event** ✅
  - Changed from `crud_exploration.add_event(exploration_id=exploration.id, ...)`
  - To `exploration.add_event(...)` (direct model method)
- [x] **Optimize add_loot** ✅
  - Changed from `crud_exploration.add_loot(exploration_id=exploration.id, ...)`
  - To `exploration.add_loot(...)` (direct model method)
- [x] **Optimize update_stats** ✅
  - Changed from `crud_exploration.update_stats(exploration_id=exploration.id, ...)`
  - To direct property updates (`exploration.total_caps_found +=`, etc.)
- [x] **Fix Config Reference** ✅
  - Fixed `partner_bonus` → `partner_nearby_bonus` in happiness service

**Achieved Impact**:
- Eliminated 3+ unnecessary database queries per exploration event
- More efficient code working with existing in-memory objects
- Reduced database round-trips for wasteland expeditions

##### 5. Additional Quick Wins

- [ ] **Remove Unused Imports** (chore)
  - Run `ruff check --select F401`
  - Clean up unused imports (~50-100 lines)
- [ ] **Add Missing Type Hints**
  - Return type hints for all service methods
  - Enable `--strict` mode for `ty` type checker
- [ ] **Consolidate Game Constants**
  - Move magic numbers to config (e.g., `difficulty * 2` → config)
  - Document formulas in comments
- [ ] **Improve Error Messages**
  - Add context to exceptions (e.g., "Incident {id} not found in vault {vault_id}")
  - Review all `HTTPException` messages for clarity

#### v1.9+ Recent Optimizations ✅

- [x] **Training Service N+1 Optimization** ✅ (Jan 4, 2026)
  - Added batch dweller fetching to training CRUD
  - Optimized training service with optional dweller parameters
  - Updated game loop for batch operations
  - Reduced training queries from N+2 to 2 (60-80% improvement)
- [x] **Vault Service Extraction** ✅ (Jan 4, 2026)
  - Created `VaultService` (375 lines) with business logic
  - Reduced Vault CRUD from 619 to 244 lines (60% reduction)
  - Clear separation: CRUD (data access) vs Service (business logic)
  - Consistent architecture pattern across services

#### v2.1+ Performance & Optimization (Deferred)

> **Note**: Lighthouse optimizations deferred to post-v2.0. Current performance score of 71/100 is acceptable for MVP
> phase. Focus on features over premature optimization.

- [x] **Phase 1-3: Lighthouse Improvements** ✅ (Jan 2, 2026)
    - Performance: 54 → 71/100 (+17 points)
    - Accessibility: 87 → 90/100 (+3 points)
    - SEO: 83 → 92/100 (+9 points)
    - Code splitting and lazy loading implemented
    - FCP: 15.3s → 1.7s (target met!)
    - See `LIGHTHOUSE_PROGRESS.md` for details

- [ ] **Phase 4-9: Additional Optimizations** (Deferred to v2.1+)
    - Bundle tree-shaking and minification improvements
    - Virtual scrolling for large lists (100+ items)
    - Loading skeletons and progressive enhancement
    - Polling optimization and WebSocket migration
    - Resource hints and preloading
    - Target: Performance 71 → 85-90/100

#### Other Technical Debt

> **Note**: See [v1.9.5 Technical Improvements](#v195-technical-improvements--chores-in-progress---jan-2026) above for active work on N+1 optimizations, config migration, and auth consolidation.

- [ ] **Email Testing Infrastructure**
    - Migrate from MailHog to Mailpit
    - Improved web UI with better performance
    - Modern, actively maintained alternative
    - Better compatibility with current Docker/Podman setup
- [ ] Performance optimization for large vaults (100+ dwellers)
- [x] ~~Database query optimization (N+1 query prevention)~~ ✅ **In Progress** (see v1.9.5)
  - Training service optimized (60-80% reduction) ✅
  - Incident service optimization pending
- [ ] Implement GraphQL for complex queries
- [ ] WebSocket for real-time updates (replace polling)
- [ ] Progressive Web App (PWA) features
- [ ] Accessibility improvements (WCAG 2.1 AA compliance)
- [ ] Internationalization (i18n) support

### Security Enhancements (Optional)

- [ ] **FastAPI Guard Integration** - Advanced authorization and access control library for more granular permissions
  and security policies

---

## 📊 Progress Metrics

### Current Stats (as of January 4, 2026)

- **Backend Endpoints**: 22 routers with 90+ endpoints (including quests, objectives, incident management)
- **Frontend Components**: 55+ Vue components (including QuestsView, ObjectivesView, combat UI, room detail modal)
- **UI Components**: 8 custom reusable components
- **Services**: 15+ backend services (including new VaultService)
- **Test Coverage**:
    - Frontend: 489+ tests passing (including quest/objective tests, room detail modal tests)
    - Backend: 293 tests passing (33+ quest/objective tests, 7 room upgrade tests, training optimization tests)
- **Models**: 18+ database models (including Quest, Objective, Incident, GameState, link tables)
- **Lines of Code**: ~22,000+ (backend + frontend)
- **Performance**:
    - Training service: 60-80% query reduction ✅
    - Vault CRUD: 60% line reduction (619 → 244 lines) ✅

### Version Milestones

- **v0.1** - Basic vault and dweller management ✅
- **v0.2** - Equipment system ✅
- **v1.0** - Room upgrades and exploration enhancements ✅
- **v1.1** - Room management and resource production ✅
- **v1.2** - Combat and incident system ✅
- **v1.3** - Room detail view with clickable dweller navigation ✅
- **v1.4** - Breeding and radio system ✅ (Jan 2, 2026)
- **v1.5** - Core leveling system ✅ (Jan 2, 2026)
- **v1.6** - Training system backend ✅ (Jan 2, 2026)
- **v1.7** - Chat/Notification system + Structured logging ✅ (Jan 3, 2026)
- **v1.8** - Quest & Objective systems + UI consistency ✅ (Jan 3, 2026)
- **v1.9** - Training/Vault optimization + Service refactoring ✅ (Jan 4, 2026)
- **v1.9.5** - Technical improvements (game config, auth consolidation, incident N+1) (Current - Jan 2026)
- **v2.0** - Happiness system + Resource warnings + Phase 1 completion (Feb 2026)
- **v2.1** - Full MVP release (Mar 2026)
- **v2.2+** - Performance optimizations, advanced features (Post-MVP)

---

## 🤝 Contributing

Contributions are welcome! See specific feature branches for work-in-progress items. Check the [README.md](./README.md)
for development setup instructions.

## 📝 Notes

This roadmap is subject to change based on:

- User feedback
- Technical constraints
- Priority adjustments
- Community contributions

Last updated: January 4, 2026

---

## 🎉 Recent Highlights

### Training & Vault Service Optimization v1.9 (January 4, 2026)

- ✅ **Training Service N+1 Optimization** - Eliminated redundant queries in training operations
  - Added batch dweller fetching (`get_dwellers_for_trainings()`)
  - Optimized service methods with optional dweller parameter
  - Game loop now batch-fetches dwellers (N+2 queries → 2 queries)
  - **60-80% query reduction** for training-heavy vaults
- ✅ **Vault Service Extraction** - Major architectural refactoring
  - Created `VaultService` (375 lines) with all business logic
  - Reduced Vault CRUD from 619 to 244 lines (**60% reduction**)
  - Clear separation: CRUD (data access) vs Service (business logic)
  - Consistent architecture pattern with other services
- ✅ **Bug Fixes** - Fixed 6 failing tests in game control and vault initialization
  - Corrected dweller creation (`create_random` vs `create`)
  - Fixed vault capacity updates for production/storage rooms
  - Fixed enum usage (RoomTypeEnum, DwellerStatusEnum)
- ✅ **Code Quality** - Fixed 11 ruff linting errors across 6 files
  - G201, TRY300, BLE001, B904 errors resolved
  - Improved exception handling patterns

### Quest & Objective Systems v1.8 (January 3, 2026)

- ✅ **Quest CRUD** - Full quest management with visibility tracking
- ✅ **Objective System** - Progress tracking with VaultObjectiveProgressLink
- ✅ **Frontend Views** - QuestsView with Overseer's Office requirement, ObjectivesView with tabs
- ✅ **Testing** - 7 backend + 15 store + 11 component tests (33 total)
- ✅ **UI Consistency** - All views use CSS custom properties theme system

### Chat & Notification System v1.7 (January 3, 2026)

- ✅ **ChatMessage Model** - Persistent user-dweller conversations with full history
- ✅ **Notification Model** - One-way system notifications (level-ups, births, recruitment)
- ✅ **WebSocket Infrastructure** - Real-time message delivery with ConnectionManager
- ✅ **Chat History Loading** - Messages restored when re-entering chat
- ✅ **Backend Integration** - Notifications triggered on game events (dweller leveling, etc.)
- ✅ **Bug Fix: Name Sorting** - Backend now properly sorts dwellers by first_name + last_name
- ✅ **Bug Fix: Navigation** - Chat → Dwellers button now uses correct vault ID (not dweller ID)

### Room Detail View v1.3 (January 1, 2026)

- ✅ **Comprehensive Room Modal** - Click any room to view detailed statistics
- ✅ **Production Analytics** - Real-time calculation of resource production rates
- ✅ **Efficiency Metrics** - Visual display of room capacity utilization
- ✅ **Dweller Management** - View assigned dwellers with their relevant SPECIAL stats
- ✅ **Clickable Dweller Navigation** - Click dweller cards to open their detail page (v1.3.1)
- ✅ **Quick Actions** - Upgrade, destroy, or unassign all dwellers from one place
- ✅ **29 Component Tests** - Full test coverage for room detail functionality

### Combat System v1.2 (January 2026)

- ✅ **Complete Incident System** - 8 incident types with dynamic spawning
- ✅ **Combat Resolution** - Auto-combat based on dweller stats + equipment
- ✅ **Loot Generation** - Difficulty-scaled rewards (caps + items)
- ✅ **Real-time Combat UI** - Alert banners, combat modals, room overlays
- ✅ **Game Loop Integration** - Automated incident processing in 60s ticks
- ✅ **Spread Mechanics** - Incidents can spread to adjacent rooms

### Room Management System v1.1 (December 2025)

- ✅ **4×8 Grid Layout** - Visual vault room grid with drag-and-drop
- ✅ **Build System** - Click-to-place room building with cost calculation
- ✅ **Upgrade System** - Tier progression (1→2→3) with capacity scaling
- ✅ **Dweller Assignment** - Drag-and-drop dwellers to rooms
- ✅ **Exploration Rewards** - Auto-complete with detailed rewards modal
- ✅ **Comprehensive Testing** - 7 backend + 5 frontend tests for upgrades
