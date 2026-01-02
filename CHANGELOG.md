# Changelog

All notable changes to this project will be documented in this file.
See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

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
