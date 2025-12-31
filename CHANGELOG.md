# Changelog

All notable changes to this project will be documented in this file. See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

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
