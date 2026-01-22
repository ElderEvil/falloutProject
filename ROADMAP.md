# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and AI-powered dweller interactions.

---

## Recent Completions

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

## Current Sprint: Quick Wins (P1)

**Target: v2.1.2**

### High Priority
- [ ] **Audio Stop Button** - Pause/stop audio playback in chat
- [ ] **Animated Glow Effect** - Pulsing glow on cards/buttons
- [ ] **Unique Room Filtering** - Backend prevents duplicate unique rooms
- [ ] **Equipment Stats Display** - Weapon damage, outfit bonuses

### Completed Quick Wins
- [x] AI button logic (Generate vs Regenerate)
- [x] Theme color consistency
- [x] Tooltip positioning improvements
- [x] Equipment dialog improvements

---

## Next Sprint: Death System (P1)

**Target: v2.2.0**

### Death Mechanics
- [ ] **Death State** - is_dead flag, death_timestamp on dweller model
- [ ] **Death Triggers** - Health reaches 0, radiation threshold
- [ ] **Revival System** - Level × 50 caps cost, max 1000

### Death UI
- [ ] Death notification modal
- [ ] Grayed-out dweller cards for dead dwellers
- [ ] Revival button with cost display
- [ ] Memorial/death log (optional)

---

## UX Enhancements (P2)

**Target: v2.3.0**

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

### Phase 4: Multiplayer (May 2026)
- Social features (friends, vault visits, leaderboards)
- Cloud saves, multi-device sync

---

## Technical Debt (P3)

### Backend
- [ ] Storage migration: MinIO → RustFS (lighter, faster)
- [ ] Performance testing: Locust in nightly CI
- [ ] Test coverage: Target 80% (both FE/BE)

### Frontend
- [x] ~~Vue architecture refactor~~ → COMPLETED (v2.1.0)
- [ ] Component refactoring: Break down large components (DwellerCard 813 lines, RoomGrid 814 lines)

### DevOps
- [ ] Deployment optimization ([docs/DEPLOYMENT_OPTIMIZATION.md](docs/DEPLOYMENT_OPTIMIZATION.md))
- [x] ~~Docker build automation~~ → COMPLETED (build.yml)

---

## Progress Metrics

### Current Stats (January 23, 2026)
- **Backend**: 22+ routers, 90+ endpoints, 15+ services
- **Frontend**: 55+ Vue components, 10 feature modules
- **Tests**: Frontend 670, Backend 535
- **Models**: 18+ database models

### Version Milestones
| Version | Release | Highlights |
|---------|---------|------------|
| v2.1.1 | Jan 22, 2026 | UI polish, planning |
| v2.1.0 | Jan 22, 2026 | Modular frontend architecture |
| v2.0.0 | Jan 22, 2026 | Major release, deployment ready |
| v1.4.2 | Jan 21, 2026 | Final v1.x release |
| v2.1.2 | Jan 2026 | Quick wins (planned) |
| v2.2.0 | Feb 2026 | Death system (planned) |
| v2.3.0 | Mar 2026 | Motion Vue, UX polish (planned) |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

*Last updated: January 23, 2026*
