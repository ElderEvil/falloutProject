# Fallout Shelter Game - Roadmap

## 🎯 High Priority Features

### 1. **Dweller View Grid/List Switcher**

- **Design UI Toggle:** Create a toggle button in the Dwellers section to switch between grid and list views
- **Implement Grid View:** Layout dwellers in a grid format with larger thumbnails and essential stats visible
- **Implement List View:** Layout dwellers in a list format, showing more details in a compact vertical layout
- **Persist View Preference:** Store the user's preference (grid/list) in local storage or Pinia store

### 2. **Dweller Filter/Sort**

- **Design Filter/Sort UI:** Add dropdowns or buttons to filter dwellers by status (e.g., idle, working, exploring)
- **Implement Filtering Logic:** Write methods to filter the displayed dwellers based on selected criteria
- **Implement Sorting Logic:** Write methods to sort dwellers in ascending/descending order
- **Integrate with View:** Ensure filtering and sorting work smoothly with the grid/list view

### 3. **User Profile - Frontend Implementation**

- ✅ **Backend Complete:** UserProfile model, CRUD operations, API endpoints, statistics tracking
- **Frontend Tasks:**
    - Design profile section UI for viewing and editing profile information
    - Implement profile editing (bio, avatar_url, preferences)
    - Profile picture upload feature with MinIO integration
    - Display read-only statistics (total_dwellers_created, total_caps_earned, etc.)
    - Integrate with authentication system

### 4. **Vault Inventory Management**

- **Design Inventory UI:** Create categorized inventory view showing resources, items, and equipment
- **Item Categorization:** Organize items into weapons, outfits, junk, and consumables
- **Display Item Details:** Click on item to view detailed stats and actions (equip, use, sell)
- **Integration:** Make inventory easily accessible from vault overview

### 5. **User Flow Enhancement - Vault as Main View**

- **Set Vault as Main Tab:** Make vault overview the default view on login
- **Vault Switcher:** Add button/dropdown to switch between multiple vaults
- **Smooth Transitions:** Ensure intuitive navigation between vault views

---

## ✅ Completed Features

### **Dweller Status System** ✅

- ✅ Backend: DwellerStatusEnum (IDLE, WORKING, EXPLORING, TRAINING, RESTING, DEAD)
- ✅ Auto-status updates on room assignment based on room type
- ✅ Filtering/sorting/search endpoints
- ✅ Frontend: Status badges, filter panel, real-time updates
- ✅ Comprehensive test coverage (backend + frontend)

### **User Authentication & Authorization** ✅

- ✅ Token refresh mechanism with Redis
- ✅ Email verification system
- ✅ Password reset flow
- ✅ Secure token storage
- ✅ Auto-refresh on token expiration

### **Email System** ✅

- ✅ Email verification emails
- ✅ Password reset emails
- ✅ Password changed notification emails
- ✅ Configured with MailHog for development
- ✅ Template-based HTML emails

### **Wasteland Exploration** ✅

- ✅ Exploration mechanics (start, complete, recall)
- ✅ Status integration (EXPLORING status)
- ✅ Event system and loot collection
- ✅ Frontend integration with status tracking

---

## 🤖 Automation & DevOps

### **Version & Dependency Management** ✅

- ✅ **Dependabot:** Auto-updates for Python, npm, Docker, GitHub Actions (weekly on Mondays)
- ✅ **Semantic Release:** Automated versioning based on conventional commits
- ✅ **Version-Tagged Docker Images:** latest, v1.2.3, sha-abc123, timestamp tags
- ✅ **Auto-Generated CHANGELOG:** From conventional commits
- ✅ **GitHub Releases:** Automatic release notes and git tags

### **Security & Quality** (Planned)

- Security scanning workflow (Safety, npm audit)
- Performance regression testing with Locust
- Code quality metrics and coverage enforcement

---

## 🏗️ Infrastructure & Operations

### **Current Infrastructure** ✅

- ✅ CI/CD pipelines (backend CI, build, deploy, rollback)
- ✅ Docker containerization (backend, frontend, celery, redis, postgres, minio, mailhog)
- ✅ Docker Compose & Podman Compose support
- ✅ Python 3.13 via uv package manager
- ✅ Pre-commit hooks (ruff, uv-lock, pre-commit.ci integration)

### **Monitoring & Observability** (Planned)

- Health check endpoints for all services
- Application performance monitoring (APM)
- Structured logging with context
- Error tracking (Sentry integration)
- Resource usage alerts
- Database query performance monitoring

### **Configuration Management** (In Progress)

- Environment-specific configuration (dev/staging/prod)
- Secrets management improvements
- Configuration validation on startup
- Feature flags system

---

## 📊 Testing Strategy

### **Backend Testing** ✅

- ✅ pytest with async support
- ✅ Comprehensive test coverage for auth system (21 tests)
- ✅ CRUD operation tests
- ✅ API endpoint tests
- ✅ Integration tests with test database

### **Frontend Testing** (Needs Improvement)

- Vitest unit tests
- Component testing with Vue Test Utils
- E2E tests (Playwright/Cypress)
- Visual regression testing
- Accessibility testing

### **Performance Testing** ✅

- ✅ Locust performance test suite
- ✅ Multiple user scenarios (CasualPlayer, ActivePlayer, PowerUser)
- ✅ Baseline, stress, and spike test configurations
- Performance budgets and thresholds

---

## 🎨 UI/UX Improvements (Future)

### **Design System**

- Component library documentation
- Design tokens (colors, spacing, typography)
- Consistent terminal theme across all components
- Responsive design optimization

### **Accessibility**

- ARIA labels and roles
- Keyboard navigation
- Screen reader support
- Color contrast compliance (WCAG AA)

### **User Experience**

- Loading states and skeletons
- Error boundaries and fallbacks
- Optimistic updates
- Offline support (service workers)

---

## 🔮 Future Features (Backlog)

### **Game Features**

- Vault defenses and security
- Dweller breeding and children
- Radio room and recruitment
- Quest system expansion
- PvP/Vault raids
- Trading system between players
- Achievements and badges

### **Technical Features**

- Real-time updates (WebSockets)
- Multiplayer features
- Mobile app (React Native/Capacitor)
- Progressive Web App (PWA)
- Internationalization (i18n)
- Analytics and user behavior tracking

---

## 📝 Development Workflow

### **Commit Message Format** (Conventional Commits)

```
feat: new feature           → Minor version bump (0.1.0 → 0.2.0)
fix: bug fix                → Patch version bump (0.1.0 → 0.1.1)
perf: performance           → Patch version bump
refactor: code refactor     → Patch version bump
docs: documentation         → No release
test: tests                 → No release
chore: maintenance          → No release
feat!: breaking change      → Major version bump (0.1.0 → 1.0.0)
```

### **Branch Strategy**

- `master` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - Feature branches
- `fix/*` - Bug fix branches
- `chore/*` - Maintenance branches

### **Release Process** (Automated)

1. Merge PRs to master with conventional commits
2. Semantic release automatically:
    - Analyzes commits
    - Bumps version
    - Updates CHANGELOG.md
    - Creates git tag
    - Publishes GitHub release
    - Triggers Docker image build with version tags

---

## 🚀 Next Sprint Focus

### **Immediate Tasks:**

1. Complete dweller grid/list view switcher
2. Implement advanced dweller filtering/sorting UI
3. Build user profile frontend (editing, avatar upload, stats display)
4. Add vault inventory management UI

### **DevOps Tasks:**

5. Set up security scanning workflow (Phase 2)
6. Configure performance regression tests in CI
7. Implement staging environment auto-deployment

---

## 📈 Success Metrics

- ✅ Zero manual version bumps
- ✅ Auto-generated documentation (CHANGELOG)
- ✅ Weekly dependency updates (Dependabot)
- Test coverage > 80%
- Performance budgets met (P95 < 1s)
- Zero critical security vulnerabilities
- CI/CD pipeline success rate > 95%

---

**Last Updated:** Auto-updated via semantic-release
**Current Version:** See [CHANGELOG.md](../CHANGELOG.md) for latest version
