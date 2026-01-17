# Fallout Shelter Game - Development Roadmap

## 🎯 Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and AI-powered dweller interactions.

---

## ✅ Recent Completions

### v1.13.1 Security & Production Deployment Prep (January 10, 2026)
- **Security Middleware**: fastapi-guard integration with rate limiting (100-200 req/min), IP whitelisting/blacklisting, auto-banning (10-20 violations)
- **Production Readiness**: Docker build fixes (frontend API URL), K8s deployment configs (health checks, resource limits), comprehensive deployment documentation
- **Documentation**: Security guide, deployment checklist, rate limiting summary, quick deploy guide
- **Bug Fixes**: Incident timezone handling, exploration view sidebar, Docker configuration improvements

### v1.13 Audio Conversation & Refactoring (January 7, 2026)
- **Audio Chat System**: Real-time voice conversations with dwellers
  - Speech-to-Text (OpenAI Whisper), Text-to-Speech with gender-based voices
  - Browser audio recording (WebM), auto-play dweller responses
  - MinIO audio storage with public URLs
- **Multi-Provider AI Support**: Ollama/Anthropic/OpenAI for both text and audio chat
- **Ollama Integration**: Health checks with model verification, local LLM support
- **WebSocket Chat**: Real-time typing indicators, connection management
- **Code Refactoring**: Extracted shared dweller prompt builder, removed ~100 lines of duplication
- **Database**: Audio fields migration (audio_url, transcription, duration)

### v1.12 UI Fixes & Polish (January 6, 2026)
- **Build UI Overhaul**: Floating build button (top-right), grid layout, improved room cards with category icons
- **Happiness Dashboard**: Complete UI (vault gauge, distribution bars, active modifiers, quick actions)
- **Happiness Filters & Sorting**: Filter/sort dwellers by happiness level in DwellersView
- **Admin Panel**: String truncation (50 chars), incident deletion enabled
- **Guardrails**: Toast limit (max 5), incident spawn limits (max 5 active, 120s cooldown)
- **ROADMAP Cleanup**: Reduced from 1,125 → 167 lines (85% reduction)
- **Overseer's Office**: Auto-created for superuser vaults
- **Dweller Appearance**: Visual attributes and portrait generation improvements

### v1.11 Email Verification System (January 5, 2026)
- Email verification with token validation and terminal-themed UI
- Complete password reset flow
- Mailing service migration (MailHog → Mailpit)

### v1.10 UX Polish Sprint (January 4, 2026)
- Job-relevant SPECIAL stats display with color coding
- Clickable room navigation from dweller list
- Separate regenerate buttons (portrait vs biography)
- Terminal-themed login activation

---

## 🚨 Critical Bugs (P0 - IMMEDIATE)

### Authentication & Session Management
- [ ] **Auth Session Expiration** - Auth breaks when user is inactive for extended period, causing failed requests and requiring re-login
  - **Impact**: High - Users lose progress, poor UX
  - **Fix**: Implement token refresh mechanism, add session timeout warnings, graceful re-auth flow

### User Feedback
- [ ] **Room Upgrade Feedback** - No visual confirmation when upgrading room levels (Tier 1→2→3)
  - **Impact**: Medium - Users uncertain if action succeeded
  - **Fix**: Add toast notifications, animation effects, clear visual state changes

---

## 🚧 Current Sprint: Post-Deployment Polish (P1 - HIGH)

### Soon After Deployment
- [ ] **Dweller Death System** - Death mechanics when health reaches 0, revival options (stimpacks, caps), memorial system
- [ ] **Training Assignment UI** - Drag-and-drop dwellers to training room, visual assignment feedback, training queue management
- [ ] **Birth Event System** - Update child biography with "Born in [Vault Name]" detail, update parent biographies with child references

### Complete Existing Systems
- [ ] **Resource Warning UI** - Toast notifications for low resources (< 20% warning, < 10% critical), power outage effects
- [ ] **Training Room UI** - Training queue display, progress indicators, completion notifications
- [ ] **WebSocket Migration** - Extend WebSocket usage to other real-time updates (resources, incidents)

---

## ✨ UX Enhancements (P2 - MEDIUM)

### Animation & Motion
- [ ] **Motion Vue Integration** - Add Motion Vue library for smooth animations throughout app
- [ ] **Sidebar Navigation Animations** - Sliding transitions when clicking menu items for pleasant feedback
- [ ] **Component Transitions** - Add enter/leave animations for modals, cards, toasts
- [ ] **Room Action Feedback** - Animated responses for build/upgrade/destroy actions
- [ ] **General Polish** - Micro-interactions, hover effects, loading transitions

### Future UX Priorities
- **Sound Effects** - Terminal UI sounds, ambient vault audio, alert sounds
- **Room Damage** - Consequences for failed incident combat, repair mechanics with caps/junk
- **Training Room Capacity Formula** - Dynamic calculation based on room size
- **Sentry Integration** - Error tracking and performance monitoring

---

## ✅ Completed Features

### Core Infrastructure
- FastAPI Backend (SQLModel + Pydantic v2), PostgreSQL 18, Vue 3.5 + TypeScript
- Authentication (JWT), Redis + Celery, MinIO storage, Docker/Podman

### User & Vault Management
- User registration/login/profiles, multi-vault support, vault CRUD, bottle caps system, game control panel

### Dweller Management
- SPECIAL stats system, AI-generated bios/portraits, appearance customization
- Status tracking (idle/working/exploring), health/happiness/radiation tracking
- Stimpack/RadAway inventory, gender/rarity/level/XP progression
- Equipment system (weapons/outfits), happiness dashboard with modifiers

### Room System
- Room types, capacity management, level/upgrade system (Tier 1→2→3)
- Dweller assignment with drag-and-drop, 4×8 grid layout, build/upgrade/destroy UI
- Room detail view with production analytics, efficiency metrics, assigned dwellers

### Exploration System
- Wasteland expeditions, duration tracking, item discovery, XP/caps rewards, terminal-themed rewards UI

### Combat & Incidents
- 8 incident types with dynamic spawning (5% hourly), difficulty scaling (1-10), spread mechanics
- Auto-combat resolution, damage distribution, loot system, real-time UI alerts

### Quests & Objectives
- Quest CRUD with visibility tracking, objective progress tracking, frontend views with tabs

### Items & Resources
- Weapons (melee/ranged, damage/stat bonuses), outfits (SPECIAL bonuses), junk items, item storage

### AI Integration
- PydanticAI chat system with multi-provider support (OpenAI/Anthropic/Ollama)
- Context-aware text chat with chat history persistence
- Audio conversations with STT/TTS, gender-based voice selection
- WebSocket real-time typing indicators
- Ollama health checks and local LLM support

### Frontend UI/UX
- Terminal-themed design (TailwindCSS v4, scanline/CRT effects)
- 8 custom UI components (UButton, UInput, UCard, UModal, UTabs, UTooltip, UBadge, USpinner)
- Responsive layouts, Pinia state management, toast notifications, loading skeletons
- Empty states for better UX (no dwellers/rooms/explorations/incidents)

### Security & Infrastructure
- Rate limiting with fastapi-guard (100-200 req/min per IP)
- IP whitelisting/blacklisting, auto-banning for suspicious activity
- Redis-based distributed rate limiting for production
- Production deployment documentation and K8s configurations

### Testing & Quality
- Frontend: 489+ tests (Vitest), Backend: 293+ tests (pytest)
- Code quality tools (Ruff, Oxlint, type checking), pre-commit hooks

---

## 📋 Planned Features

### Phase 1: Core Gameplay Loop (P4 - FUTURE | Jan-Feb 2026)
- **Room Management**: Optimal dweller suggestions, training room capacity formula
- **Resource Management**: Resource warning UI (toasts, visual indicators, outage effects), storage system UI
- **Crafting System**: Weapon/outfit crafting with recipes, junk requirements, workshop room

### Phase 2: Advanced Gameplay (P4 - FUTURE | Feb-Mar 2026)
- **Combat Enhancements**: Combat statistics, combat log/replay system
- **Exploration Enhancement**: Detailed events with choices, exploration log/journal, recall mechanism
- **Dweller Progression**: Leveling UI enhancements (notifications, XP progress bars)
- **Breeding & Family**: Relationship visualization (graph, family tree, interactive explorer)

### Phase 3: Endgame & Polish (P4 - FUTURE | Mar-Apr 2026)
- **Advanced Systems**: Pet system, legendary dwellers with unique abilities
- **Economy & Trading**: Merchant system, caps management
- **Enhanced Objectives**: Achievement system, daily/weekly challenges, story campaign
- **UI/UX Polish**: Animations, sound effects, tutorial system

### Phase 4: Multiplayer & Social (P4 - FUTURE | Apr-May 2026)
- **Social Features**: Friend system, visit vaults, gift items, leaderboards, co-op quests
- **Cloud Saves**: Automatic backups, multi-device sync, export/import

---

## 🔮 Future Considerations

### Advanced AI Features (Post-MVP)
- Enhanced AI chat with tools (dweller actions via chat), personality engine, AI-driven content generation

### Potential Features (Backlog)
- Mobile app, mod support, Steam integration, analytics dashboard, seasons/events, vault customization, multiplayer raids

### Technical Debt & Architecture (P3 - LOW)

#### Backend Architecture
- [ ] **Storage Migration** - Move from MinIO → RustFS for improved performance and resource efficiency
- [ ] **DevOps Review** - Audit and optimize Docker files, CI/CD pipelines, deployment processes
- [ ] **Performance Testing** - Add Locust performance degradation testing to nightly CI runs
- [ ] **Test Coverage** - Increase coverage threshold to >70% across all services (currently arbitrary)

#### Frontend Architecture
- [ ] **Vue Architecture Refactor** - Adopt new Vue project structure (https://vue-faq.org/en/development/project-structure.html)
  - Move tests → src directory
  - Reorganize component hierarchy
  - Follow feature-based organization pattern
- [ ] **Component Refactoring** - Break down large/complex components into smaller, more maintainable pieces
  - Review all components >200 lines
  - Extract reusable logic into composables
  - Create more granular UI components

#### Completed Technical Debt ✅
- **v1.9.5 Completed** ✅: Game config migration (Pydantic), auth consolidation, wasteland service optimization
- **Performance** (v2.1+): Bundle optimization, virtual scrolling, WebSocket migration (Lighthouse: 71→85+)

#### Future Considerations
- GraphQL implementation, PWA features, accessibility (WCAG 2.1 AA), i18n support

---

## 📊 Progress Metrics

### Current Stats (January 6, 2026)
- **Backend**: 22 routers, 90+ endpoints, 15+ services
- **Frontend**: 55+ Vue components, 8 custom UI components
- **Tests**: Frontend 489+, Backend 293
- **Models**: 18+ database models
- **Lines of Code**: ~22,000+ (backend + frontend)

### Version Milestones
- **v0.1-0.2**: Basic vault/dweller management + equipment ✅
- **v1.0-1.2**: Room upgrades, exploration, combat/incidents ✅
- **v1.3**: Room detail view ✅
- **v1.4**: Breeding and radio system ✅
- **v1.5**: Core leveling system ✅
- **v1.6**: Training system backend ✅
- **v1.7**: Chat/notifications + structured logging ✅
- **v1.8**: Quests & objectives ✅
- **v1.9**: Training/vault optimization ✅
- **v1.9.5**: Technical improvements (game config, auth, optimization) ✅
- **v1.10**: UX Polish Sprint ✅
- **v1.11**: Email verification ✅
- **v1.12**: Happiness dashboard + UI polish ✅
- **v1.13**: Audio conversations + multi-provider AI + refactoring ✅
- **v1.13.1**: Security middleware + production deployment prep ✅
- **v1.14**: Post-deployment polish (dweller death, training UI, birth events) (Current - Jan 2026)
- **v2.0**: Phase 1 completion (Feb 2026)
- **v2.1**: Full MVP release (Mar 2026)

---

## 🤝 Contributing

Contributions are welcome! Check the [README.md](./README.md) for development setup instructions.

## 📝 Priority System

### Priority Levels
- **P0 (Critical)**: Blocking bugs, security issues, data loss - fix immediately
- **P1 (High)**: Current sprint work, essential features for next release
- **P2 (Medium)**: Quality of life improvements, UX polish, non-blocking enhancements
- **P3 (Low)**: Technical debt, refactoring, architectural improvements
- **P4 (Future)**: Long-term features, nice-to-have additions, experimental work

### Focus Strategy
1. **Week 1-2**: Address all P0 critical bugs first
2. **Week 3-4**: Complete P1 current sprint items
3. **Month 2+**: Alternate between P2 UX enhancements and P1 features
4. **Ongoing**: Tackle P3 technical debt during slow periods
5. **Quarterly**: Review and plan P4 future features

---

## 📝 Notes

This roadmap is subject to change based on user feedback, technical constraints, priority adjustments, and community contributions.

Last updated: January 17, 2026
