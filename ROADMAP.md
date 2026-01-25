# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## Recent Completions

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
| v2.3.0  | Jan 24, 2026 | Storage validation, pregnancy debug    |
| v2.2.0  | Jan 23, 2026 | Death system complete                  |
| v2.1.3  | Jan 22, 2026 | Router consolidation                   |
| v2.1.2  | Jan 22, 2026 | Quick wins complete                    |
| v2.1.1  | Jan 22, 2026 | UI polish, planning                    |
| v2.1.0  | Jan 22, 2026 | Modular frontend architecture          |
| v2.0.0  | Jan 22, 2026 | Major release, deployment ready        |
| v1.4.2  | Jan 21, 2026 | Final v1.x release                     |
| v2.4.0  | Feb 2026     | Motion Vue, animations (planned)       |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

*Last updated: January 24, 2026*
