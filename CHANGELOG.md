# Changelog

All notable changes to this project will be documented in this file.
See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

---

## [Unreleased]

---

## [2.9.0] - 2026-02-05

### What's New
- **Enhanced Admin Panel** - Now shows all the important details at a glance
  - Chat messages now display happiness changes and audio info
  - Vault stats include resource maximums and population limits
  - Dweller details show radiation, stimpacks, radaways, and death status
  - Room coordinates, costs, and speedup multipliers are now visible

### Fixed
- **Chat Training Actions** - No more "Unable to access vault data" errors
  - Training actions from chat now work smoothly
  - Vault data properly loads when you open chat with a dweller
- **Cleaner Chat Messages** - Removed duplicate action text
  - Dwellers now express desires naturally without repeating what the action button says
  - Example: "I'm feeling energetic!" instead of "I'd love to work in the Power Generator! + [Button: Assign to Power Generator]"
- **More Reliable Chat** - Chat keeps working even if real-time notifications fail
  - WebSocket errors won't break your conversation anymore
  - You'll always get the dweller's response
- **Smoother Exploration Recall** - No more crashes when checking exploration progress
  - Safely handles cases where progress data isn't available yet
- **Better WebSocket Connections** - Fixed connection issues with different URL formats
  - Handles URLs with or without http://, with or without trailing slashes
  - More robust connection handling
- **Happiness Accuracy** - Vault happiness now includes the dweller you just chatted with
  - Fixed a timing issue where vault happiness was calculated before saving the dweller's new mood

### Improvements
- **Better Error Messages** - Chat endpoints now use proper validation errors
  - Empty audio files get a clear validation error instead of generic server error
- **Code Quality** - Cleaner, more maintainable codebase
  - Moved chat business logic from API endpoints to service layer
  - Objectives generation moved to the correct endpoint location
  - Better code organization following clean architecture

### Technical
- **Auth Token Refresh** - Fixed 422 validation error when refreshing access tokens
  - Backend now accepts `refresh_token` in request body (JSON) instead of query parameter
  - More RESTful and secure (tokens no longer exposed in URLs/logs)
- **Message Tracking** - Chat responses now include message IDs for better debugging and tracking
- **CSS to Tailwind** - Room components now use Tailwind utilities for better performance

---

## [2.8.5] - 2026-02-04

### Changed
- **Code Quality & Refactoring** - Major backend cleanup and simplification
  - Removed empty CRUD wrappers for weapon/outfit/junk items (use CRUDItem directly)
  - Deduplicated vault_id item list filtering in weapon/outfit endpoints
  - Created generic seeding helper and refactored objective seeder
  - Replaced 11 broad `except Exception` handlers with specific exceptions for better error handling
  - Moved exploration/item constants (rarity priorities, junk values, scrap probabilities) to game_config for easier tuning
  - Simplified exploration loot transfer logic (reduced from 171 to ~110 lines, removed complexity suppressions)

### Added
- **Storage Provider** - RustFS support added alongside MinIO for S3-compatible object storage
  - Add STORAGE_PROVIDER config option (minio/rustfs)
  - RustFS services in docker-compose.yml and docker-compose.infra.yml
- **Room Tiles UX** - Better visual identification of room abilities
  - Room tiles now show SPECIAL ability letter after room name (e.g., "Power Generator (S)")
  - Room tiles now display ability icon for instant visual recognition
- **Testing** - Added 5 new tests for exploration loot transfer (weapon/outfit creation, missing data, invalid rarity)

### Fixed
- **Room Images** - Room images now load correctly in dockerized HTTPS staging environments
  - Frontend prepends API base URL to image paths
  - Fixes "failed to load room image" errors on staging
- **Training Rooms** - Added test coverage for dweller status assignment to training rooms

---

## [2.8.3] - 2026-02-02

### What's New
- **Smarter Dweller Assignments** - Dwellers assigned to training rooms now correctly show "Training" status instead of "Working"
  - No more confusion about what your dwellers are actually doing
  - Training progress and status now match up perfectly

### Improvements
- **Better Error Messages** - When things go wrong, you'll get clearer, more helpful error messages
  - Missing dwellers or resources? The game now tells you exactly what couldn't be found
  - Validation errors (like trying to recruit with the wrong gender) are more descriptive
  - All error messages now follow a consistent format for easier reading

### Behind the Scenes
- **More Reliable Timestamps** - Database seed data now uses consistent UTC timestamps
- **Stronger Code Quality** - Added comprehensive tests for error handling and edge cases
- **Cleaner Architecture** - Standardized how the backend handles different types of errors

---

## [2.8.0] - 2026-01-29

## [2.8.0] - 2026-01-29

### What's New
- **Dweller Renaming** - Rename your dwellers! Click the pencil icon next to their name on the detail page
- **Easter Eggs** - Discover hidden vault secrets! Try naming a dweller "Gary" or rapidly clicking the version number in About page
- **Toast Notifications** - All feedback messages now match your chosen theme color and automatically group duplicates
- **Better Room Refunds** - Get 50% of your caps back when destroying upgraded rooms (up from 20%)

### Improvements
- **Changelog** - Cleaner modal design, works properly, and won't freeze your game anymore
- **Keyboard Shortcuts** - Build mode hotkey (B) now works with all keyboard layouts
- **Happiness Dashboard** - Quick actions are now easier to find and use
- **Radio Room** - Clear warnings when you need to assign dwellers before recruiting
- **Tooltips & Alerts** - Everything displays correctly above the navbar in your chosen theme color
- **Error Messages** - Cleaner, friendlier messages (technical details hidden in console)

---

## [2.4.1] - 2026-01-25

### Fixed
- **Critical: Celery Worker Crashes** - Resolved production crashes caused by mixing timezone-aware and timezone-naive datetime objects
  - Fixed `death_service.py` - All datetime operations now use consistent naive datetime format
  - Fixed `breeding_service.py` - Pregnancy and child aging operations use naive datetimes
  - All datetime operations now use `datetime.now(UTC).replace(tzinfo=None)` for consistency
- **System Info Endpoint** - Fixed `build_date` to use timezone-aware datetime for proper ISO format output
- **Test Suite** - Fixed `test_get_info_returns_valid_build_date` expecting timezone info in ISO format

### Added
- **Documentation**
  - `HOTFIX_TIMEZONE_NAIVE.md` - Deployment guide with rollback procedures (184 lines)
  - `TIMEZONE_NAIVE_ANALYSIS.md` - Complete analysis of 169 timezone-naive issues across codebase (1,062 lines)
  - `RELEASE_NOTES_v2.4.1.md` - Comprehensive release notes (206 lines)

### Changed
- Version bumped from 2.4.0 to 2.4.1 (backend and frontend)
- Updated `uv.lock` to reflect version change

### Impact
- ✅ Celery workers no longer crash on dweller death events
- ✅ Game tick processing continues uninterrupted
- ✅ Breeding and pregnancy systems function correctly
- ✅ All tests passing

### Notes
- This is a temporary fix ensuring all datetime objects remain naive to match database schema (`TIMESTAMP WITHOUT TIME ZONE`)
- Future work: Full migration to timezone-aware system (see `TIMEZONE_NAIVE_ANALYSIS.md`)

---

## [2.7.5] - 2026-01-29

### Added
- **Changelog System** - Version update notifications and changelog display
  - ChangelogModal component with terminal-themed design and smooth animations
  - Version comparison logic to show new entries since last seen version
  - Full changelog integration with backend API endpoint
  - Added changelog route and navigation integration
  - Terminal-themed modal with backdrop, escape key, and click-outside-to-close
  - Version detection composable for automatic new version notifications

### Fixed
- **API Architecture** - Moved changelog endpoints from `/changelog/` to `/system/changelog/`
  - Added `/system/changelog/latest` endpoint for latest version lookup
  - Fixed module import paths for UI components and API utilities
  - Resolved Vue component props and computed property warnings
  - Fixed modal v-model binding and lifecycle management

### Changed
- **API Organization** - Changelog endpoints now under `/api/v1/system/` as public endpoints
- **Frontend Structure** - Added profile module with changelog routes and services
- **Modal Design** - Clean terminal-themed modal with proper UCard integration
- **Documentation** - Updated CHANGELOG.md structure for better readability and impact tracking

---

## [2.7.0] - 2026-01-28

### Added
- **Storage Management System**
  - Storage sidebar navigation entry (hotkey: 9)
  - Storage space tracking and visualization
  - Item scrap functionality for weapons/outfits
  - Junk item grouping by type with count badges
  - Sell All feature for stacked items
  - Enhanced item cards with detailed stats
- **Keyboard Shortcuts**
  - Build mode toggle with 'B' key
  - ESC to exit build mode
  - Hotkey badges on buttons
- **Modern Python Tooling**
  - Added modern-python skill with comprehensive references
  - uv, ruff, ty, prek documentation
  - Security tools and migration guides
- **Oxfmt Formatter**
  - 30x faster than Prettier, 2x faster than Biome
  - Prettier-compatible configuration
  - Replaced Prettier with oxfmt across frontend

### Fixed
- **Junk Item Pricing** - Now based on rarity (Common=2, Rare=50, Legendary=200)
- **Equipment Filtering** - Weapons and outfits now properly filter by vault
- **Storage Schema** - Added missing storage_id fields to weapon/outfit/junk schemas
- **Async Issues** - Fixed greenlet-related issues in sell method with transactional rollback
- **Notification Styles** - Use theme variables instead of hardcoded colors
- **UI Consistency** - Migrated components to UCard, UButton, UTails components

### Changed
- Version bumped from 2.6.6 to 2.7.0 (backend and frontend)
- Replaced Prettier with oxfmt for 30x faster formatting
- Updated frontend to use Tailwind utilities instead of scoped CSS
- Enhanced storage item cards with Weight and Durability stats

### Changed
- Version bumped from 2.6.6 to 2.7.0 (backend and frontend)
- Replaced Prettier with oxfmt for 30x faster formatting
- Updated frontend to use Tailwind utilities instead of scoped CSS
- Enhanced storage item cards with Weight and Durability stats

### Documentation
- Easter eggs documentation added to ROADMAP.md
- Development scripts cleanup
- Moved documentation to proper docs/ directory

### Testing
- Added comprehensive tests for weapon scrap/sell/vault filtering (9 tests)
- Added comprehensive tests for outfit scrap/sell/vault filtering (9 tests)
- Added junk sell tests with pricing verification (6 tests)
- Added storage items endpoint tests

---

## [2.6.6] - 2026-01-27

### Changed
- **Backend Dependencies Updated**
  - alembic: 1.18.0 → 1.18.1
  - faker: 40.1.0 → 40.1.2
  - greenlet: 3.3.0 → 3.3.1
  - aiosmtplib: 5.0.0 → 5.1.0
  - coverage: 7.13.1 → 7.13.2
  - prek: 0.2.27 → 0.3.0
  - ruff: 0.14.11 → 0.14.14
  - ty: 0.0.11 → 0.0.13

### Fixed
- **UI Theme Consistency** - Replaced hardcoded colors in notification components with CSS theme variables
- **Documentation Organization** - Moved REFACTORING_PROGRESS.md to docs directory

### Removed
- Obsolete development scripts (check_rooms.py, test_config.py)

---

## [2.6.5] - 2026-01-27

### Added
- **Notification Bell UI Component**
  - Notification bell in NavBar with unread count badge
  - Pop-up UI showing recent notifications
  - Type-specific icons for different notification types
  - Mark individual or all notifications as read
  - Auto-refresh unread count every 30 seconds
- **Backend Notification Integration**
  - Exploration completion notifications with metadata (caps, XP, items)
  - Radio recruitment notifications with dweller info
  - Incident spawn notifications with incident details
  - Comprehensive notification integration tests (4 tests)

### Fixed
- **Notification Error Handling** - Wrapped notification calls in try/except to prevent failures from breaking core flows
- **Memory Leak** - Clear notification polling interval on component unmount
- **Incident Types** - Added missing incident type mappings (MOLE_RAT_ATTACK, FERAL_GHOUL_ATTACK)
- **Duplicate Notifications** - Removed duplicate notifications for dweller arrivals and baby births

### Changed
- Improved incident names with emoji icons for better UX
- Simplified notification bell display condition
- Enhanced notification error logging with full context

### Testing
- Added comprehensive notification integration tests
- Moved test fixtures to conftest.py following established pattern
- All 4 notification tests passing

---

## [2.6.0] - 2026-01-26

### Added
- **Wasteland Exploration Enhancements**
  - Distributed WebSocket system for exploration events
  - Enhanced exploration UI with real-time updates
- **Soft Delete System**
  - Soft delete implementation for critical entities
  - Preservation of data integrity while maintaining clean UI
- **UX Improvements**
  - Enhanced UI polish and user experience improvements

### Changed
- Improved WebSocket infrastructure for better real-time performance
- Enhanced exploration coordination and event handling

---

## [2.5.0] - 2026-01-26

### Added
- **Room Visual Assets**
  - 220+ room sprite images for all room types, tiers, and sizes
  - Room images render in vault overview grid as backgrounds
  - Images display in room detail modal preview section
  - Intelligent fallback system for missing tier/segment combinations
  - Automatic image URL generation based on room name, tier, and size
- **Room Capacity Enforcement**
  - Strict dweller assignment limits (2 dwellers per cell)
  - Capacity calculation: 2-cell room = 2, 6-cell = 4, 9-cell = 6
  - Prevention of over-assignment with user-friendly error messages
  - Allow reordering dwellers within same room
  - Real-time capacity validation on drag-and-drop

### Changed
- **UI Improvements**
  - Compact room info overlay for better visibility
  - Reduced font sizes and padding for room name, category, tier
  - Room info positioned at top with semi-transparent background
  - Dwellers positioned at bottom with proper z-index layering
- **Backend**
  - Database migration to populate image_url for existing rooms
  - Automatic URL generation during room build and upgrade
  - Static file serving through `/static` endpoint
- **Frontend**
  - Vite proxy configuration for image serving
  - Image loading with error handlers and console debugging
  - Test page for verifying image loading functionality

---

## [2.4.0] - 2026-01-25

### Added
- **Death System** - Complete dweller death and revival mechanics
  - Death causes: Health depletion, radiation poisoning, incidents, exploration, combat
  - Revival system with bottle cap cost (configurable)
  - Permanent death after 7 days (configurable)
  - Death statistics tracking per vault and user
  - Epitaph generation for fallen dwellers
- **Incident Service** - Room-based incident management system
- **Security Utilities** - Core authentication and authorization helpers
- **System Endpoint** - Application metadata and version information

---

## [2.3.0] - 2026-01-24

### Added
- **Pregnancy Debug Panel** - UI controls for testing pregnancy system (superuser only)
  - Force conception between any two adult dwellers
  - Accelerate pregnancy to be immediately due
  - Accessible from Relationships → Pregnancies tab

### Fixed
- **Exploration Item Tracking** - Item count now updates in real-time during exploration
- **Exploration Rewards Modal** - Modal stays open until user collects rewards (no auto-close)
- **Storage Duplicate Items** - Removed unique constraint on item names (fixes crash when finding multiple items)
- **Outfit Type Enum** - Fixed KeyError crash when recalling dweller with tiered outfits
- **Rarity Colors** - Replaced hardcoded hex colors with CSS variables for theme consistency
- **Relationships View** - Fixed dweller loading for pregnancy debug panel

### Changed
- Compacted AGENTS.md development guide (830 → 200 lines)
- Updated pregnancy text to clarify conception chance is configurable

### Testing
- All 684 frontend tests passing

---

## [2.1.1] - 2026-01-22

### Added
- Implementation plan for v2.2.0 (death system, UX enhancements)
- Floating tooltips for improved UX

### Fixed
- **UI Improvements** (#155)
  - AI generation button logic (Generate vs Regenerate states)
  - Theme color consistency fixes
  - Equipment UI improvements
  - Room menu styling

### Testing
- All 670 frontend tests passing

---

## [2.1.0] - 2026-01-22

### Added
- **Modular Frontend Architecture** (#149)
  - 10 feature-based domain modules
  - 300+ files reorganized
  - Backward compatibility via re-exports
  - Complete architecture documentation

### Fixed
- TypeScript strict build errors (#152)
- Template type errors with strictTemplates (#153)

### Testing
- All 639 frontend tests passing after refactor

---

## [2.0.2] - 2026-01-22

### Added
- Agent skills documentation (#143)
- Deployment optimization guide (#133)

### Changed
- Documentation consolidation (#148)

---

## [2.0.1] - 2026-01-22

### Fixed
- Relationship service and vault CRUD issues (#144)
- Dependency updates (urllib3, pyasn1)

---

## [2.0.0] - 2026-01-22

### Changed
- **BREAKING**: Major version bump from v1.4.2 for semantic-release alignment
- No API breaking changes - version jump for release automation

### Notes
- Docker images now follow v2.x.x tagging
- See AGENTS.md for versioning strategy

---

## [1.14.1] - 2026-01-22

### Fixed

#### TypeScript Build & Module Polish (PR #152)
- **Build Strict**: Resolved all `build:strict` TypeScript errors across modular architecture
- **Config Fixes**: Fixed vite.config.ts and vitest.config.ts plugin array type issues
- **Type Safety**: Fixed useTheme.ts parseInt non-null assertions for regex results
- **Import Paths**: Updated auth types, ProfileEditor, RadioStatsPanel, happinessService imports
- **Component Fixes**: Fixed DwellerChat.vue undefined array access, exploration component return types
- **Backward Compat**: Added Dweller type re-export from stores for compatibility
- **Cleanup**: Deleted orphaned view files replaced by module views, updated router paths

### Changed
- Updated relative imports to `@/` alias throughout codebase (OutfitCard, WeaponCard, RadioStatsPanel, EmptyCell)
- All 651 frontend tests passing

---

## [1.14.0] - 2026-01-22

### Added

#### System Information & About Page
- **Backend**: Public `/api/v1/info` endpoint returning app version, API version, environment, Python version
- **Frontend**: Terminal-themed About page displaying system information with GitHub link
- **Testing**: 4 backend tests, 6 frontend tests for info endpoint and About page

#### Rate Limit User Experience
- **429 Error Handling**: User-friendly "Rate Limit Exceeded" messages in axios interceptor
- **Retry-After Support**: Parses `Retry-After` header to show wait time to users
- **Toast Notifications**: Clear messaging when rate limited instead of generic errors

### Changed
- Updated ROADMAP.md with v1.13.6-7 and v1.14 completions
- Moved "Training Drag-and-Drop UI" from P1 to P3 (nice-to-have)

---

## [1.13.7] - 2026-01-22

### Added

#### Modular Frontend Architecture
- **Feature-Based Organization**: Complete restructure into 10 domain modules
  - `core/` - Shared UI components, composables, utilities
  - `modules/auth/` - Authentication and user management
  - `modules/vault/` - Vault operations and resource management
  - `modules/dwellers/` - Dweller management and stats
  - `modules/combat/` - Equipment and incident systems
  - `modules/exploration/` - Wasteland exploration
  - `modules/progression/` - Training, quests, objectives
  - `modules/radio/` - Radio room and recruitment
  - `modules/social/` - Relationships and pregnancy
  - `modules/profile/` - User profile and settings
- **Backward Compatibility**: Re-exports for smooth migration
- **Documentation**: Complete architecture guide in `docs/MODULAR_FRONTEND_ARCHITECTURE.md`

### Changed
- Reorganized 300+ frontend files into modular structure
- Updated all import paths to use new module organization

### Fixed
- All 639 frontend tests passing after refactor

---

## [1.13.5-1.13.6] - 2026-01-17

### Added
- **Proactive Token Refresh**: Automatic refresh 5 minutes before expiry
- **Refresh Token Rotation**: Enhanced security with token rotation
- **Production Security**: Rate limiting, IP filtering, auto-banning with Redis

### Fixed
- **MinIO Production**: Internal connection protocol issues resolved
- **Database Migrations**: Profile initialization and SQLAlchemy session errors
- **CI/CD Performance**: Optimized caching strategies

---

## [1.9-1.12] - 2026-01-03 to 2026-01-06

### Summary
- Audio conversation system with STT/TTS
- Multi-provider AI support (Ollama/Anthropic/OpenAI)
- WebSocket chat with typing indicators
- Email verification and password reset
- UX polish (happiness dashboard, filters, sorting)
- See ROADMAP.md for detailed changelog

---

## [1.8.0] - 2026-01-03

### Added

#### Quest System (Backend + Frontend)

- **Backend API**:
  - Quest CRUD operations with visibility tracking
  - Quest assignment endpoint `POST /api/v1/quests/{quest_id}/assign`
  - Quest completion endpoint `POST /api/v1/quests/{quest_id}/complete`
  - Get vault quests endpoint with assignment status
  - VaultQuestCompletionLink model for tracking quest progress
  - 7 comprehensive quest CRUD tests

- **Frontend UI**:
  - QuestsView component with active/completed tabs
  - Overseer's Office requirement check (quests locked until built)
  - Quest store with state management (15 tests)
  - Quest assignment and completion actions
  - Terminal-themed quest cards with rewards display
  - Empty states for no available quests
  - 11 component tests for QuestsView

#### Objective System Improvements

- **UI Enhancements**:
  - ObjectivesView with active/completed tabs
  - Objective progress tracking with progress bars
  - Theme-consistent styling with CSS custom properties
  - Icons for active/completed tabs

- **Bug Fixes**:
  - Fixed objective validation error by shortening challenge text to fit 32-char limit
  - Updated `assign.json` objectives with shorter challenge texts

#### Navigation & UI Consistency

- **Navigation Reorganization**:
  - Fixed hotkey duplication conflicts
  - Reserved hotkey 3 for future Exploration feature
  - Reorganized by early-game usefulness:
    - 1: Overview, 2: Dwellers, 3: Exploration (coming soon), 4: Objectives
    - 5: Quests, 6: Radio, 7: Relationships, 8: Training
  - Added SidePanel to TrainingView for navigation

- **Theme Consistency**:
  - Replaced all hardcoded colors with CSS custom properties in:
    - QuestsView (green → theme variables)
    - ObjectivesView (green → theme variables)
    - TrainingView (green → theme variables)
    - TrainingQueuePanel (all colors themed)
  - Reduced element sizes in TrainingView (20-30% smaller)

### Fixed

- **Quest System**:
  - Fixed quest completion mixin to use `quest_id` instead of `quest_entity_id`
  - Updated `get_multi_for_vault` to return all assigned quests with visibility status

- **Objective System**:
  - Fixed ObjectiveCreate validation by shortening challenge texts from 38 to 28 characters
  - Challenge text format: "Assign X dwellers correctly" (fits 32-char limit)

- **Navigation**:
  - Fixed hotkey conflicts between Quests and Radio Room
  - Added missing SidePanel to TrainingView

### Testing

- **Frontend Tests**:
  - Added 15 quest store tests (fetch, assign, complete, computed properties)
  - Added 11 QuestsView component tests (UI, actions, Overseer check)
  - All 489 frontend tests passing

- **Backend Tests**:
  - All 33 quest/objective CRUD tests passing
  - Fixed test expectations for quest visibility behavior

## [1.7.0] - 2026-01-03

### Added

#### Structured Logging System

- **Centralized Logging Configuration** (`app/core/logging.py`):
  - `setup_logging()` function with environment-based configuration
  - JSON formatter for production (structured logs with timestamps, levels, context)
  - Human-readable formatter for development (colored, request ID tracking)
  - Context vars for request ID propagation across async operations
  - Custom JSON formatter with additional fields (timestamp, level, module, function, exception)

- **Request ID Middleware** (`app/middleware/request_id.py`):
  - Automatic request ID generation (UUID4)
  - Support for X-Request-ID header from proxies/load balancers
  - Request ID added to all log records
  - X-Request-ID returned in response headers for client-side tracing

- **Configuration** (`app/core/config.py`):
  - `LOG_LEVEL`: Configurable log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - `LOG_JSON_FORMAT`: Toggle JSON vs human-readable format
  - `LOG_FILE_PATH`: Optional file logging

- **Print Statement Replacement**:
  - `app/utils/load_quests.py`: Replaced 2 print statements with `logger.info/debug`
  - `app/utils/image_processing.py`: Replaced print with `logger.error` (with exc_info)
  - `app/api/v1/endpoints/chat.py`: Replaced print with `logger.debug`

- **Startup Logging** (`main.py`):
  - Log environment, API version, log level, JSON logging status on startup
  - Request ID middleware integrated into app

- **Dependencies**:
  - Added `python-json-logger>=4.0.0` for structured JSON logging

#### Stimpack & RadAway System

- **Backend API**:
  - `POST /api/v1/dwellers/{id}/use_stimpack` - Heal dweller for 40% of max health
  - `POST /api/v1/dwellers/{id}/use_radaway` - Remove 50% of radiation
  - Validation: Checks for item availability and need (no healing at full health, no radiation removal at 0 radiation)
  - Error handling with descriptive messages

- **CRUD Operations**:
  - `use_stimpack()` method in CRUDDweller with health restoration logic
  - `use_radaway()` method in CRUDDweller with radiation removal logic
  - Proper exception handling (ResourceConflictException, ContentNoChangeException)

- **Frontend UI**:
  - Inventory display in DwellerCard showing stimpack/radaway counts
  - Icon-based inventory stats with color coding (green for stimpack, yellow for radaway)
  - Radiation stat display when radiation > 0
  - "Use Stimpack" and "Use RadAway" buttons with smart validation
  - Buttons disabled when items unavailable or not needed
  - Loading states during item usage
  - Toast notifications for success/error feedback

- **Store Integration**:
  - `useStimpack()` and `useRadaway()` methods in dwellerStore
  - Automatic state updates after item usage
  - Error message extraction from API responses

#### Chat & Notification System (v1.7)

- **ChatMessage Model**: Persistent user-dweller conversations
  - Database-backed message storage with relationships (user_id, vault_id, dweller_id)
  - Message history preserved across sessions
  - Timestamp tracking for conversation ordering

- **Notification Model**: One-way system notifications
  - Level-up notifications
  - Birth announcements
  - Recruitment alerts
  - Event-driven notification creation

- **WebSocket Infrastructure**:
  - ConnectionManager for real-time message delivery
  - Instant message delivery without polling
  - Backend notification service integrated with game events

- **Frontend Chat System**:
  - Chat history loading and display
  - Messages restored when re-entering chat
  - Real-time message updates via WebSocket

### Fixed

- **Dweller Sorting**: Backend now properly sorts dwellers by `first_name + last_name` when using "name" sort parameter
- **Navigation Bug**: Fixed chat page → dwellers button to use correct vault ID instead of dweller ID

### Technical

- WebSocket connection management with async support
- Notification service layer for game event integration
- Enhanced chat endpoints with history retrieval

## [1.6.0] - 2026-01-02

### Added

#### Training System (Backend)

- **Training Rooms**: Time-based SPECIAL stat training in dedicated rooms
  - Duration: Base 2 hours + 30 minutes per current stat level
  - Tier bonuses: T2 (25% faster), T3 (40% faster)
  - Capacity management and status tracking
- **Training Service**: Start/complete/cancel operations with validation
- **REST API**: 6 endpoints for training management
- **Game Loop Integration**: Phase 4.5 with auto-completion
- **Admin Panel**: TrainingAdmin view
- **Testing**: 11 comprehensive service tests

### Changed
- Dweller: Added trainings relationship, max_health → 1500
- Game balance: Training constants added

### Fixed
- **Foreign Key Constraints**: Added `ondelete` behavior to prevent IntegrityError
  - Dweller self-references (partner_id, parent_1_id, parent_2_id): `SET NULL` on delete
  - Relationship table (dweller_1_id, dweller_2_id): `CASCADE` on delete
  - Pregnancy table (mother_id, father_id): `CASCADE` on delete
  - Resolves errors during vault deletion and dweller cleanup operations

## [1.5.0] - 2026-01-02

### Added

#### Core Leveling System (Backend)

- **XP Calculation**: Exponential curve (100 * level^1.5) for 1-50 progression
- **XP Sources**:
  - Exploration (survival +20%, luck +2% per point)
  - Combat (perfect combat +50%)
- **Level-Up**: +5 HP per level, full heal, cap at 50
- **LevelingService**: XP calculation and auto-leveling
- **Testing**: 11 comprehensive tests

### Changed
- Enhanced exploration/combat XP with bonuses
- Added ix_dweller_level index

---

## [1.4.0] - 2026-01-02

### Added

#### Breeding System (Backend)

- **Relationship Management**:
    - Complete CRUD API for dweller relationships
    - Relationship types: acquaintance, friend, romantic, partner, ex
    - Affinity system (0-100) tracking relationship strength
    - Relationship progression endpoints (initiate romance, make partners, break up)
    - Compatibility scoring based on SPECIAL stats and personality traits
    - Quick-pair testing endpoint for development
    - Relationship service layer with business logic

- **Pregnancy System**:
    - Pregnancy creation with conception mechanics
    - 3-hour pregnancy duration (configurable)
    - Pregnancy status tracking (pregnant/delivered)
    - Baby delivery endpoint with child creation
    - Child inherits SPECIAL traits from both parents
    - Age progression system (child → teen → adult)
    - Due date calculation with timezone-aware comparisons
    - Progress percentage and time remaining calculations

#### Radio Recruitment System (Backend)

- **Radio Room Functionality**:
    - Manual recruitment endpoint (500 caps cost)
    - Automatic recruitment rate calculation
    - Radio mode toggle: Recruitment vs. Happiness boost
    - Recruitment speedup multipliers (1.0x-10.0x per radio room)
    - Multiple radio rooms stack for increased recruitment rates
    - Happiness-based recruitment probability
    - Charisma stat influence on recruitment
    - Radio service layer with rate calculations

#### Database & Models

- **New Models**:
    - `Relationship` model with dweller associations
    - `Pregnancy` model with parent tracking
    - Extended `Dweller` model with age group and parent fields
    - `RadioMode` enum for room mode tracking

- **Enums**:
    - `RelationshipTypeEnum` (acquaintance, friend, romantic, partner, ex)
    - `PregnancyStatusEnum` (pregnant, delivered)
    - `AgeGroupEnum` (child, teen, adult)
    - `RadioModeEnum` (recruitment, happiness)

### Fixed

- **Test Suite Corrections**:
    - Fixed `create_with_user_id` to accept dict inputs in addition to Pydantic models
    - Fixed pregnancy timezone comparison (naive vs. aware datetime handling)
    - Fixed radio room test data (category enum: "misc" → "misc.")
    - Added missing required fields to RoomCreate in tests (base_cost, upgrade costs, size constraints)
    - Fixed test assertions to match actual API response schemas
    - Fixed relationship query to use UUID conversion for database lookups
    - Updated expected status codes (404 → 422 for validation errors)
    - Updated expected response keys (child → child_id, status values)

### Testing

- **Backend Tests**:
    - 11 relationship API tests (CRUD, romance, partners, breakup)
    - 8 pregnancy API tests (create, deliver, status tracking, progress)
    - 6 radio API tests (manual recruit, mode toggle, rate calculation)
    - Full test coverage for breeding and radio services
    - All backend tests passing (600+ tests)

### Technical

- **CRUD Operations**:
    - `CRUDRelationship` with bidirectional relationship queries
    - `CRUDPregnancy` with due date and delivery logic
    - Enhanced `CRUDVault` with dict/model input handling

- **Service Layer**:
    - `RelationshipService` with compatibility and progression logic
    - `BreedingService` with conception and delivery mechanics
    - `RadioService` with recruitment rate calculations

## [1.3.1] - 2026-01-01

### Added

#### Room Detail Modal Enhancements

- **Frontend**:
    - Added clickable dweller cards in Room Detail Modal
    - Implemented navigation to dweller detail page when clicking on assigned dwellers
    - Added hover effects with cursor pointer, lift animation, and enhanced glow for clickable dwellers
    - Integrated Vue Router navigation with proper route params (vault ID and dweller ID)

### Fixed

- Fixed Vue Router mock in RoomDetailModal tests by adding `useRouter` mock
- Updated test expectations to match new component layout:
    - Dweller capacity display format (e.g., "2 / 2" instead of "2 / 4")
    - Room size display format (e.g., "1x merged" instead of raw numbers)
    - Section title changed from "Assigned Dwellers" to "Dweller Details"
    - Efficiency calculations updated to reflect actual room capacity logic
- Fixed router error by properly importing and using `useRouter` at component setup level

### Testing

- Updated 5 RoomDetailModal tests to match new layout and behavior
- All 428+ frontend tests now passing

## [1.1.0] - 2024-12-31

### Added

#### Room Management System

- **Backend**:
    - Added room upgrade endpoint `POST /api/v1/rooms/upgrade/{room_id}`
    - Implemented tier progression system (1→2→3) with capacity/output recalculation
    - Added proportional scaling formula for capacity and output based on tier ratio
    - Implemented upgrade cost validation (t2_upgrade_cost, t3_upgrade_cost)
    - Added proper error handling for insufficient caps and max tier validation
    - Added 7 comprehensive pytest tests for room upgrade functionality

- **Frontend**:
    - Implemented 4×8 grid layout for visual vault room management
    - Created room upgrade UI with cost display and tier progression
    - Added `upgradeRoom()` function to room store with vault refresh
    - Implemented upgrade button with golden styling and cost tooltip
    - Added `canUpgrade()` and `getUpgradeCost()` helper functions
    - Built room selection and detail view system
    - Added 5 comprehensive Vitest tests for upgrade store functionality

#### Exploration System Enhancements

- **Backend**:
    - Fixed datetime timezone handling (reverted to `datetime.utcnow()`)
    - Removed debug logging from exploration models
    - Improved timezone compatibility between database and application

- **Frontend**:
    - Implemented auto-complete detection for explorations at 100% progress
    - Added manual Complete button for explorations
    - Created `ExplorationRewardsModal.vue` with terminal-themed design
    - Display experience (with golden pulse animation), caps, items, distance, enemies
    - Added recalled early indicator with reduced rewards display
    - Implemented duplicate call prevention for completion actions

### Fixed

- Fixed room upgrade `AttributeError` by removing formula access from Room model
- Added HTTP error handling in upgrade endpoint (ValueError → 400, InsufficientResourcesException → 422)
- Fixed grid dimensions from 8×25 to 4×8 as specified
- Fixed exploration timezone calculation issues with UTC handling
- Fixed Vue component update errors with null checks and duplicate prevention
- Fixed exploration rewards modal props validation with nullable rewards

### Changed

- Changed grid layout from 8×25 to 4×8 (4 columns, 8 rows)
- Updated room upgrade logic to use proportional tier scaling instead of formulas
- Improved room store to update local state and refresh vault after upgrade
- Enhanced error messages for room upgrade failures

### Testing

- Added 7 backend tests for room upgrade (tier progression, capacity calculation, error cases)
- Added 5 frontend tests for room upgrade store functionality
- All tests passing with comprehensive coverage of upgrade scenarios

## [0.2.0] - 2024-12-31

### Added

#### Equipment System

- **Backend**:
    - Added weapon and outfit equip/unequip endpoints
    - Implemented eager loading for equipment relationships to prevent lazy loading errors
    - Updated `DwellerReadFull` schema to include weapon and outfit fields
    - Override `CRUDDweller.get()` to eager load weapon, outfit, vault, and room relationships
    - Fixed SQLAlchemy async session issues with `selectinload()`

- **Frontend**:
    - Created comprehensive TypeScript equipment type system (`equipment.ts`)
        - Weapon types: MELEE, RANGED with subtypes (FIST, BLADE, PISTOL, RIFLE, etc.)
        - Outfit types: CASUAL, WORK, COMBAT, SPECIAL
        - Rarity system: COMMON, UNCOMMON, RARE, LEGENDARY
    - Implemented equipment service layer with API integration
    - Created Pinia equipment store with state management
    - Built `WeaponCard.vue` component with damage stats and rarity coloring
    - Built `OutfitCard.vue` component with SPECIAL stat bonuses
    - Implemented `DwellerEquipment.vue` with:
        - Equipment slots for weapon and outfit
        - Inventory modal with tabbed interface
        - Real-time equipment updates
        - Empty states for unequipped slots
    - Added refresh event chain for automatic data updates after equipment changes

#### UI/UX Improvements

- Terminal-themed equipment cards with rarity-based styling
- Modal overlay with inventory tabs for weapons and outfits
- Loading states and toast notifications for equipment actions
- Responsive equipment grid layout

### Fixed

- Fixed backend SQLAlchemy `MissingGreenlet` error by adding eager loading for equipment relationships
- Fixed frontend equipment rendering by reading from dweller object instead of store
- Fixed unequip API endpoint paths (changed from `/{dwellerId}/unequip/{itemId}` to `/{itemId}/unequip/`)
- Added null checks in equipment store to prevent errors with null entries in arrays
- Fixed props undefined errors in DwellerEquipment component with optional chaining

### Changed

- Updated `/api/v1/dwellers/{dweller_id}` endpoint to return `DwellerReadFull` instead of `DwellerRead`
- Modified equipment fetch logic to include weapon and outfit data in dweller responses

## [0.1.0] - 2024-12-30

### Initial Release

#### Core Features

- User authentication and authorization (JWT-based)
- Vault management system
- Dweller CRUD operations with SPECIAL stats
- Room system with types and capacity
- AI-powered dweller chat (PydanticAI integration)
- AI-generated dweller portraits and biographies (DALL-E)
- Exploration system
- Objectives and quests
- Item system (weapons, outfits, junk)

#### Frontend

- Vue 3.5 with TypeScript and Composition API
- Terminal-themed design system with TailwindCSS v4
- 8 custom UI components
- Pinia state management
- Toast notifications
- Loading skeletons
- Grid and list view for dwellers
- 88 passing frontend tests (Vitest)

#### Backend

- FastAPI with SQLModel and Pydantic v2
- PostgreSQL 18 with UUID v7 support
- Celery + Redis for background tasks
- MinIO for object storage
- Comprehensive test suite (pytest)
- Ruff linting and formatting
- Type checking with ty

#### Infrastructure

- Docker/Podman containerization
- Development and production configurations
- Pre-commit hooks with prek
- CI/CD ready setup
