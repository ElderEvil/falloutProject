# Modular Frontend Architecture Plan

> **Version:** 1.0.0
> **Created:** 2026-01-22
> **Status:** Approved
> **Estimated Effort:** 18-24 hours

## Overview

This document outlines the plan to migrate the Fallout Shelter frontend from a flat structure to a **modular, domain-driven architecture**. The goal is to improve maintainability, enable lazy loading, and establish clear feature boundaries.

## Current State Analysis

### Inventory

| Category | Count | Location |
|----------|-------|----------|
| Components | 71 | `/src/components/` |
| Stores | 15 | `/src/stores/` |
| Services | 4 | `/src/services/` |
| Views | 19 | `/src/views/` |
| Composables | 13 | `/src/composables/` |
| Models | 11 | `/src/models/` |
| Types | 5 | `/src/types/` |
| Schemas | 3 | `/src/schemas/` |

### Strengths

- Clear domain boundaries (dwellers, rooms, exploration, etc.)
- Consistent naming conventions
- Good separation of concerns (UI/common/features)
- Modern Vue 3 patterns (Composition API)
- Type-safe with auto-generated API types

### Pain Points

- Some large components (DwellerCard 813 lines, RoomGrid 814 lines)
- Cross-store coupling (RoomGrid imports from 5 stores)
- Inconsistent API patterns (some stores call APIs directly, others use services)
- No clear module boundaries for lazy loading

---

## Target Architecture

```
/src
├── /core                          # Shared infrastructure
│   ├── /components
│   │   ├── /ui                   # Terminal-themed components
│   │   ├── /common               # Cross-cutting components
│   │   └── /layout               # Layout wrappers
│   ├── /composables              # Shared hooks
│   ├── /services                 # API client
│   ├── /utils                    # Utilities
│   ├── /types                    # Global types + api.generated.ts
│   ├── /plugins                  # Vue plugins
│   └── /schemas                  # Shared validation
│
├── /modules                       # Feature modules
│   ├── /auth                     # Authentication
│   ├── /vault                    # Vault management
│   ├── /dwellers                 # Dweller management
│   ├── /rooms                    # Room building
│   ├── /social                   # Relationships + pregnancy
│   ├── /progression              # Training + quests + objectives
│   ├── /exploration              # Wasteland exploration
│   ├── /combat                   # Incidents + equipment
│   ├── /radio                    # Recruitment
│   ├── /chat                     # AI conversations
│   └── /profile                  # User profile
│
├── /router                       # Aggregates module routes
├── /assets
├── App.vue
└── main.ts
```

### Module Structure Template

Each module follows this structure:

```
/modules/[feature]/
├── /components
│   ├── FeatureComponent.vue
│   └── index.ts                  # Barrel export
├── /composables                  # Optional
│   └── useFeature.ts
├── /stores
│   └── feature.ts
├── /services                     # Optional
│   └── featureService.ts
├── /models
│   └── feature.ts
├── /types                        # Optional
│   └── feature.ts
├── /schemas                      # Optional
│   └── feature.ts
├── /views
│   ├── FeatureView.vue
│   └── index.ts
├── /routes
│   └── index.ts                  # Route config
└── index.ts                      # Module entry
```

---

## Module Breakdown

### Core Module

**Purpose:** Shared infrastructure used by all feature modules.

| Directory | Contents |
|-----------|----------|
| `/components/ui` | UButton, UInput, UCard, UModal, UBadge, UAlert, UTooltip, UDropdown |
| `/components/common` | NavBar, SidePanel, GameControlPanel, ResourceBar, ComponentLoader, BuildModeButton |
| `/components/layout` | DefaultLayout |
| `/composables` | useAuth, useToast, useTheme, useWebSocket, useVisualEffects, useFlickering |
| `/types` | api.generated.ts, utils.ts, index.ts |
| `/plugins` | axios.ts |
| `/utils` | errorHandler.ts, validators.ts |

### Feature Modules

| Module | Components | Stores | Models | Services | Views | Priority |
|--------|-----------|--------|--------|----------|-------|----------|
| **auth** | 3 | 1 | 1 | 1 | 5 | HIGH |
| **vault** | 3 | 1 | 1 | NEW | 2 | HIGH |
| **dwellers** | 15 | 1 | 1 | NEW | 2 | MEDIUM |
| **rooms** | 6 | 1 | 1 | NEW | 0 | MEDIUM |
| **social** | 5 | 2 | 2 | - | 1 | LOW |
| **progression** | 6 | 3 | 2 | 1 | 3 | MEDIUM |
| **exploration** | 4 | 1 | 1 | - | 2 | LOW |
| **combat** | 4 | 2 | 2 | 1 | 0 | LOW |
| **radio** | 2 | 1 | 1 | - | 1 | LOW |
| **chat** | 2 | 1 | 1 | - | 1 | LOW |
| **profile** | 2 | 1 | 1 | - | 3 | LOW |

---

## Detailed Module Specifications

### Auth Module (`/modules/auth`)

**Components:**
- `LoginFormTerminal.vue` - Terminal-themed login
- `LoginForm.vue` - Standard login form
- `RegisterForm.vue` - Registration form

**Store:** `auth.ts` - User authentication, tokens, session management

**Service:** `authService.ts` - Login, register, token refresh, logout

**Schemas:** `auth.ts` - loginSchema, registerSchema (Zod)

**Views:**
- `LoginView.vue` (currently component)
- `RegisterView.vue`
- `ForgotPasswordView.vue`
- `ResetPasswordView.vue`
- `VerifyEmailView.vue`

**Routes:**
```typescript
export default [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue') },
  { path: '/forgot-password', name: 'forgot-password', component: () => import('../views/ForgotPasswordView.vue') },
  { path: '/reset-password', name: 'reset-password', component: () => import('../views/ResetPasswordView.vue') },
  { path: '/verify-email', name: 'verify-email', component: () => import('../views/VerifyEmailView.vue') },
]
```

### Vault Module (`/modules/vault`)

**Components:**
- `VaultList.vue` - Vault selection
- `VaultCreationForm.vue` - New vault creation
- `HappinessDashboard.vue` - Vault happiness metrics

**Store:** `vault.ts` - Vault CRUD, active vault, resource polling

**Service:** `vaultService.ts` - NEW (extract from store)

**Schemas:** `vault.ts` - vaultNumberSchema

**Views:**
- `VaultView.vue` - Main vault management
- `HappinessView.vue` - Happiness dashboard

### Dwellers Module (`/modules/dwellers`)

**Components (sub-organized):**
```
/components
├── /cards
│   ├── DwellerCard.vue
│   └── DwellerCardSkeleton.vue
├── /stats
│   ├── DwellerStats.vue
│   ├── XPProgressBar.vue
│   └── DwellerStatusBadge.vue
├── /grid
│   ├── DwellerGrid.vue
│   ├── DwellerGridItem.vue
│   └── DwellerGridItemSkeleton.vue
├── DwellerPanel.vue
├── DwellerFilterPanel.vue
├── DwellerEquipment.vue
├── DwellerBio.vue
├── DwellerAppearance.vue
├── UnassignedDwellers.vue
├── RoomDwellers.vue
├── LevelUpNotification.vue
└── index.ts
```

**Store:** `dweller.ts` - Dweller lifecycle, filtering, assignments

**Service:** `dwellerService.ts` - NEW, `happinessService.ts` - Moved

**Model:** `dweller.ts` - Dweller, DwellerFull, Special, VisualAttributes

**Views:**
- `DwellersView.vue` - Population overview
- `DwellerDetailView.vue` - Individual dweller

### Rooms Module (`/modules/rooms`)

**Components:**
- `RoomGrid.vue` - Room placement grid
- `RoomItem.vue` - Individual room display
- `RoomMenu.vue` - Room selection menu
- `RoomMenuItem.vue` - Menu item
- `RoomDetailModal.vue` - Room details
- `EmptyCell.vue` - Empty grid cell

**Composables:**
- `useRoomInteractions.ts` - Room interaction logic
- `useHoverPreview.ts` - Hover preview functionality

**Store:** `room.ts` - Building and infrastructure

**Model:** `room.ts` - Room, RoomCreate, RoomUpdate

### Social Module (`/modules/social`)

**Components:**
```
/components
├── /relationships
│   ├── RelationshipList.vue
│   ├── RelationshipCard.vue
│   └── ChildrenList.vue
├── /pregnancy
│   ├── PregnancyTracker.vue
│   └── PregnancyCard.vue
└── index.ts
```

**Stores:** `relationship.ts`, `pregnancy.ts`

**Models:** `relationship.ts`, `pregnancy.ts`

**Views:** `RelationshipsView.vue`

### Progression Module (`/modules/progression`)

**Components:**
```
/components
├── /training
│   ├── TrainingProgressCard.vue
│   ├── TrainingQueuePanel.vue
│   └── TrainingRoomModal.vue
├── /quests
│   └── QuestCard.vue (NEW)
├── /objectives
│   └── ObjectiveCard.vue (NEW)
└── index.ts
```

**Stores:** `training.ts`, `quest.ts`, `objectives.ts`

**Service:** `trainingService.ts`

**Models:** `quest.ts`, `objective.ts`

**Views:**
- `TrainingView.vue`
- `QuestsView.vue`
- `ObjectivesView.vue`

### Exploration Module (`/modules/exploration`)

**Components:**
- `ExplorerCard.vue`
- `EventTimeline.vue`
- `ExplorationRewardsModal.vue`
- `WastelandPanel.vue`

**Store:** `exploration.ts`

**Model:** `exploration.ts` (NEW)

**Views:**
- `ExplorationView.vue`
- `ExplorationDetailView.vue`

### Combat Module (`/modules/combat`)

**Components:**
```
/components
├── /incidents
│   ├── IncidentAlert.vue
│   └── CombatModal.vue
├── /equipment
│   ├── WeaponCard.vue
│   └── OutfitCard.vue
└── index.ts
```

**Stores:** `incident.ts`, `equipment.ts`

**Service:** `equipment.ts`

**Models:** `incident.ts`, `equipment.ts`

### Radio Module (`/modules/radio`)

**Components:**
- `RadioStatsPanel.vue`
- `ManualRecruitButton.vue`

**Store:** `radio.ts`

**Model:** `radio.ts`

**Views:** `RadioView.vue`

### Chat Module (`/modules/chat`)

**Components:**
- `DwellerChat.vue`
- `DwellerChatPage.vue`

**Composables:** `useAudioRecorder.ts`

**Store:** `chat.ts`

**Model:** `chat.ts`

**Views:** `ChatView.vue` (wrap DwellerChatPage)

### Profile Module (`/modules/profile`)

**Components:**
- `ProfileEditor.vue`
- `ProfileStats.vue`

**Store:** `profile.ts`

**Model:** `profile.ts`

**Views:**
- `ProfileView.vue`
- `SettingsView.vue`
- `PreferencesView.vue`

---

## Import Patterns

### From Core

```typescript
// UI components
import { UButton, UCard, UInput } from '@/core/components/ui'

// Shared composables
import { useAuth, useToast } from '@/core/composables'

// Global types
import type { ApiResponse, ApiError } from '@/core/types'
import type { components } from '@/core/types/api.generated'
```

### From Modules

```typescript
// Feature components
import { DwellerCard } from '@/modules/dwellers/components'

// Feature stores
import { useDwellerStore } from '@/modules/dwellers/stores'

// Feature types/models
import type { Dweller } from '@/modules/dwellers/models'

// Validation schemas
import { loginSchema } from '@/modules/auth/schemas'
```

### Cross-Module Imports

```typescript
// Allowed for related features
import type { Room } from '@/modules/rooms/models'
import { useVaultStore } from '@/modules/vault/stores'
```

---

## Migration Phases

### Phase 1: Foundation (1-2 hours)

- [ ] Create `/core` and `/modules` directories
- [ ] Move `/components/ui` to `/core/components/ui`
- [ ] Move `/components/common` to `/core/components/common`
- [ ] Move `/components/layout` to `/core/components/layout`
- [ ] Move shared composables to `/core/composables`
- [ ] Move `api.generated.ts` to `/core/types`
- [ ] Move `/plugins`, `/utils`, `/schemas` to `/core/`
- [ ] Update tsconfig path aliases
- [ ] Test core imports work

### Phase 2: Simple Modules (3-4 hours)

Start with smallest, most isolated modules:

**Radio Module:**
- [ ] Create module structure
- [ ] Move components
- [ ] Move store
- [ ] Move model
- [ ] Move view
- [ ] Create route config
- [ ] Create barrel exports
- [ ] Update imports
- [ ] Test

**Profile Module:**
- [ ] Same steps as radio

**Chat Module:**
- [ ] Same steps as radio

### Phase 3: Auth & Vault (2-3 hours)

Critical core modules:

**Auth Module:**
- [ ] Create module structure
- [ ] Move components (3)
- [ ] Move store
- [ ] Move service
- [ ] Move types
- [ ] Move schemas
- [ ] Move/create views (5)
- [ ] Create route config
- [ ] Update all auth imports (gradual)

**Vault Module:**
- [ ] Create module structure
- [ ] Move components (3)
- [ ] Move store
- [ ] Create vaultService (NEW)
- [ ] Move schema
- [ ] Move views (2)
- [ ] Create route config

### Phase 4: Medium Modules (4-5 hours)

**Exploration Module:**
- [ ] Move 4 components
- [ ] Move store
- [ ] Create model file
- [ ] Move 2 views
- [ ] Create routes

**Rooms Module:**
- [ ] Move 6 components
- [ ] Move 2 composables
- [ ] Move store
- [ ] Move model
- [ ] Create routes

**Progression Module:**
- [ ] Move training components (3)
- [ ] Create quest/objective components
- [ ] Move 3 stores
- [ ] Move service
- [ ] Move 2 models
- [ ] Move 3 views
- [ ] Create routes

**Social Module:**
- [ ] Move relationship components (3)
- [ ] Move pregnancy components (2)
- [ ] Move 2 stores
- [ ] Move 2 models
- [ ] Move view
- [ ] Create routes

**Combat Module:**
- [ ] Move incident components (2)
- [ ] Move equipment components (2)
- [ ] Move 2 stores
- [ ] Move service
- [ ] Move 2 models

### Phase 5: Complex Module (3-4 hours)

**Dwellers Module:**
- [ ] Create sub-directories (cards/, stats/, grid/)
- [ ] Move 15 components with organization
- [ ] Move store
- [ ] Create dwellerService (NEW)
- [ ] Move happinessService
- [ ] Move model
- [ ] Move 2 views
- [ ] Create routes
- [ ] Consider splitting DwellerCard (separate PR)

### Phase 6: Router Integration (1 hour)

- [ ] Update `/router/index.ts` to aggregate module routes
- [ ] Test all routes with lazy loading
- [ ] Verify route guards function
- [ ] Test navigation between modules

### Phase 7: Optimization (2-3 hours)

- [ ] Add service layer to all modules
- [ ] Create module-level barrel exports
- [ ] Add README.md to each module
- [ ] Update test imports
- [ ] Run full test suite
- [ ] Document module APIs

---

## Router Integration

```typescript
// /router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

// Import module routes
import authRoutes from '@/modules/auth/routes'
import vaultRoutes from '@/modules/vault/routes'
import dwellersRoutes from '@/modules/dwellers/routes'
import roomsRoutes from '@/modules/rooms/routes'
import socialRoutes from '@/modules/social/routes'
import progressionRoutes from '@/modules/progression/routes'
import explorationRoutes from '@/modules/exploration/routes'
import radioRoutes from '@/modules/radio/routes'
import chatRoutes from '@/modules/chat/routes'
import profileRoutes from '@/modules/profile/routes'

// Core views (not in modules)
import HomeView from '@/views/HomeView.vue'
const AboutView = () => import('@/views/AboutView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true }
    },
    {
      path: '/about',
      name: 'about',
      component: AboutView
    },
    ...authRoutes,
    ...vaultRoutes,
    ...dwellersRoutes,
    ...roomsRoutes,
    ...socialRoutes,
    ...progressionRoutes,
    ...explorationRoutes,
    ...radioRoutes,
    ...chatRoutes,
    ...profileRoutes,
  ]
})

// Auth guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router
```

---

## TypeScript Configuration

### Path Aliases

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@/core/*": ["src/core/*"],
      "@/modules/*": ["src/modules/*"]
    }
  }
}
```

### Vite Configuration

```typescript
// vite.config.ts
import { resolve } from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@/core': resolve(__dirname, 'src/core'),
      '@/modules': resolve(__dirname, 'src/modules'),
    }
  }
})
```

---

## Design Decisions

### 1. Cross-module Dependencies

**Decision:** Allow direct imports between modules, but document them.

**Rationale:** Modules like `rooms` naturally need `dweller` data. Enforcing strict boundaries would create unnecessary indirection.

**Guidelines:**
- Document cross-module imports in module README
- Use TypeScript to track dependencies
- Consider events/composables for looser coupling later

### 2. Service Layer

**Decision:** Gradually add services to all modules.

**Rationale:** Consistent API abstraction improves testability and separation of concerns.

**Guidelines:**
- Services = API abstraction only
- Business logic stays in stores
- Create thin service wrappers

### 3. Type Organization

**Decision:** Hybrid approach.

**Rationale:** API-generated types are shared, but feature-specific types belong with features.

**Guidelines:**
- `api.generated.ts` stays in `/core/types`
- Feature types in `/modules/[x]/types`
- Models in `/modules/[x]/models`

### 4. Testing Structure

**Decision:** Keep `/tests` root-level initially.

**Rationale:** Easier to update imports without breaking tests during migration.

**Future:** Move tests to modules after migration stabilizes.

### 5. Component Splitting

**Decision:** Refactor large components during Phase 5.

**Targets:**
- `DwellerCard.vue` (813 lines) - Extract action buttons, stats sections
- `RoomGrid.vue` (814 lines) - Extract grid logic, room rendering

**Approach:** Separate PRs for refactoring, after module migration.

---

## Success Criteria

### Per Phase

- [ ] All imports resolve correctly
- [ ] No TypeScript errors
- [ ] All tests pass
- [ ] Application runs without errors
- [ ] Routes work with lazy loading

### Final

- [ ] Clear module boundaries
- [ ] Improved code organization
- [ ] Lazy loading enabled
- [ ] Bundle size improved
- [ ] Development experience improved
- [ ] Documentation complete

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Import breakage | HIGH | Gradual migration, alias redirects |
| Test failures | MEDIUM | Update tests after each phase |
| Bundle size regression | LOW | Monitor bundle analysis |
| Circular dependencies | MEDIUM | TypeScript strict mode catches |
| Team confusion | LOW | Document thoroughly |

---

## Future Enhancements

After completing the migration:

1. **Lazy load stores** - Load stores only when module is accessed
2. **Module-level error boundaries** - Isolate module failures
3. **Module federation** - For micro-frontend architecture
4. **Automated dependency analysis** - Track cross-module dependencies
5. **Module-level testing** - Co-locate tests with modules

---

## References

- [Vue 3 Application Structure](https://vuejs.org/guide/scaling-up/sfc.html)
- [Pinia Best Practices](https://pinia.vuejs.org/cookbook/composing-stores.html)
- [Vite Code Splitting](https://vitejs.dev/guide/build.html#chunking-strategy)
- Original architecture analysis: Session 2026-01-22

---

*This plan is maintained for the Fallout Shelter frontend migration. Last updated: 2026-01-22*
