# Fallout Shelter Game - Development Roadmap

## 🎯 Vision
Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and AI-powered dweller interactions.

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
- [x] Stimpack and RadAway inventory
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

### Objectives & Quests
- [x] Objective creation and tracking
- [x] Quest system with rewards
- [x] Objective completion logic

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
- [x] **PydanticAI Chat System**:
  - In-character dweller conversations
  - Context-aware responses based on dweller stats and mood
  - Chat history persistence

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

## 🚧 In Progress

### Phase 1 Polish
- [ ] **Resource Warning UI** (Frontend)
  - Toast notifications for low/critical resources
  - Visual effects for resource shortages
  - Power outage room indicators
- [ ] **Optimal Dweller Suggestions**
  - AI-powered room assignment recommendations
  - Efficiency scoring based on SPECIAL stats
- [x] **Vault Authorization System** ✅ (Jan 1, 2026)
  - Implemented vault-level access control
  - Resource-specific authorization (dwellers, rooms, explorations)
  - Protection against cross-vault unauthorized access
  - Superuser override capabilities
  - Removed deprecated `validation.py` (replaced by deps.py)
  - Cleaned up utils directory (removed outdated migration scripts)

---

## 📋 Planned Features

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

#### Combat & Defense
- [ ] **Raider Attacks**
  - Random raid events
  - Combat resolution based on dweller equipment and stats
  - Damage to rooms and dwellers
  - Loot from defeated raiders
- [ ] **Radroach Infestations**
  - Room-based pest control
  - Spread mechanics
- [ ] **Fire Events**
  - Room fires requiring dweller intervention
  - Fire spread to adjacent rooms

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
- [ ] **Training Rooms**
  - SPECIAL stat training
  - Training time based on current stat level
  - Multiple dwellers training simultaneously
- [ ] **Leveling System Enhancements**
  - Level-up notifications
  - Skill points allocation
  - Perk system

#### Breeding & Family
- [ ] **Dweller Relationships**
  - Relationship tracking
  - Romantic relationships in living quarters
- [ ] **Pregnancy & Birth**
  - Pregnancy duration
  - Child growth stages
  - Inherited traits from parents

### Phase 3: Endgame & Polish (Mar-Apr 2026)

#### Advanced Systems
- [ ] **Radio Room**
  - Attract new dwellers from wasteland
  - Recruitment rate based on vault happiness
  - Dweller customization for recruits
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
> **Note**: These AI features are moved to later phases to focus on core gameplay MVP. Basic PydanticAI chat already exists and works well.

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
- [ ] Performance optimization for large vaults (100+ dwellers)
- [ ] Database query optimization
- [ ] Frontend bundle size optimization
- [ ] Implement GraphQL for complex queries
- [ ] WebSocket for real-time updates
- [ ] Progressive Web App (PWA) features
- [ ] Accessibility improvements (WCAG 2.1 AA compliance)
- [ ] Internationalization (i18n) support

---

## 📊 Progress Metrics

### Current Stats (as of January 1, 2026)
- **Backend Endpoints**: 17 routers with 70+ endpoints
- **Frontend Components**: 50+ Vue components
- **UI Components**: 8 custom reusable components
- **Test Coverage**:
  - Frontend: 95+ tests passing (including room upgrade tests)
  - Backend: Comprehensive API and CRUD tests (including 7 room upgrade tests)
- **Models**: 15+ database models
- **Lines of Code**: ~17,000+ (backend + frontend)

### Version Milestones
- **v0.1** - Basic vault and dweller management ✅
- **v0.2** - Equipment system ✅
- **v1.0** - Room upgrades and exploration enhancements ✅
- **v1.1** - Room management and resource production ✅ (Current - Jan 2026)
- **v1.2** - Combat system (Jan-Feb 2026)
- **v1.3** - Training and progression (Feb 2026)
- **v1.4** - Breeding and relationships (Feb-Mar 2026)
- **v2.0** - Full release with endgame features (Mar-May 2026)

---

## 🤝 Contributing

Contributions are welcome! See specific feature branches for work-in-progress items. Check the [README.md](./README.md) for development setup instructions.

## 📝 Notes

This roadmap is subject to change based on:
- User feedback
- Technical constraints
- Priority adjustments
- Community contributions

Last updated: January 1, 2026

---

## 🎉 Recent Highlights (December 2025)

### Room Management System v0.3
- ✅ **4×8 Grid Layout** - Visual vault room grid with drag-and-drop
- ✅ **Build System** - Click-to-place room building with cost calculation
- ✅ **Upgrade System** - Tier progression (1→2→3) with capacity scaling
- ✅ **Dweller Assignment** - Drag-and-drop dwellers to rooms
- ✅ **Exploration Rewards** - Auto-complete with detailed rewards modal
- ✅ **Comprehensive Testing** - 7 backend + 5 frontend tests for upgrades
