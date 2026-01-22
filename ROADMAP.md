# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and AI-powered dweller interactions.

---

## Recent Completions

### v1.14.1 TypeScript & Module Polish (January 22, 2026)
- **Build Fixes**: Resolved all `build:strict` TypeScript errors across modular architecture
- **Import Cleanup**: Updated relative imports to `@/` alias throughout codebase
- **Testing**: 651 frontend tests passing

### v1.14.0 Tech Debt & Polish (January 22, 2026)
- **System Info**: Public `/api/v1/info` endpoint, terminal-themed About page
- **Rate Limit UX**: User-friendly 429 errors with Retry-After support
- **Profile**: Superuser status display

### v1.13.7 Modular Frontend Architecture (January 22, 2026)
- **Complete Refactor**: 10 feature modules (auth, vault, dwellers, combat, exploration, progression, radio, social, chat, profile)
- **Core Module**: Shared UI components, composables, utilities
- **Backward Compatibility**: Re-exports for smooth migration
- **Docs**: [MODULAR_FRONTEND_ARCHITECTURE.md](docs/MODULAR_FRONTEND_ARCHITECTURE.md)

### Previous Releases (v1.10-v1.13.5)
- v1.13.5: Production security (token refresh, MinIO fixes, CI/CD optimization)
- v1.13.1: Security middleware (rate limiting, IP filtering, auto-banning)
- v1.13: Audio conversations, multi-provider AI (Ollama/Anthropic/OpenAI)
- v1.12: Happiness dashboard, UI polish, admin panel improvements
- v1.11: Email verification, password reset flow
- v1.10: UX polish (SPECIAL stats display, navigation improvements)

See [CHANGELOG.md](CHANGELOG.md) for full history.

---

## Current Sprint: Core Gameplay Polish (P1)

### High Priority
- [ ] **Dweller Death System** - Death mechanics, revival options, memorial system
- [x] **Training Assignment UI** - Progress indicators, queue management
- [x] **Birth Event System** - Pregnancy, child aging, stat inheritance
- [x] **System Info & About Page** - Version display, environment info

### Complete Existing Systems
- [x] **Resource Warning UI** - Toast notifications for low resources
- [x] **Training Room UI** - Progress indicators, completion notifications
- [x] **WebSocket Migration** - Infrastructure ready

---

## UX Enhancements (P2)

### Animation & Motion
- [ ] **Motion Vue Integration** - Smooth animations throughout app
- [ ] **Sidebar Navigation Animations** - Sliding transitions
- [ ] **Component Transitions** - Enter/leave animations for modals, cards
- [ ] **Room Action Feedback** - Animated build/upgrade/destroy responses

### Future UX (P3)
- Training drag-and-drop UI
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
- [x] ~~Vue architecture refactor~~ → COMPLETED (v1.13.7)
- [ ] Component refactoring: Break down large components (DwellerCard 813 lines, RoomGrid 814 lines)

### DevOps (Backlog)
- [ ] Deployment optimization ([docs/DEPLOYMENT_OPTIMIZATION.md](docs/DEPLOYMENT_OPTIMIZATION.md))
- [ ] Docker/CI audit

---

## Progress Metrics

### Current Stats (January 22, 2026)
- **Backend**: 22+ routers, 90+ endpoints, 15+ services
- **Frontend**: 55+ Vue components, 10 feature modules
- **Tests**: Frontend 651, Backend 535
- **Models**: 18+ database models

### Version Milestones
| Version | Release | Highlights |
|---------|---------|------------|
| v1.14.1 | Jan 2026 | TypeScript fixes, module polish |
| v1.14.0 | Jan 2026 | System info, rate limit UX |
| v1.13.7 | Jan 2026 | Modular frontend architecture |
| v1.13.5 | Jan 2026 | Production security |
| v2.0 | Feb 2026 | Phase 1 completion (planned) |
| v2.1 | Mar 2026 | Full MVP (planned) |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

*Last updated: January 22, 2026*
