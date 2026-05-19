# Modular Frontend Architecture

> **Status:** COMPLETED (January 22, 2026)
> **Tests:** 651 passing
> **PR:** #149, #152

## Overview

The frontend uses a **modular, domain-driven architecture** with feature-based organization enabling lazy loading and clear boundaries.

## Structure

```
/src
├── /core                          # Shared infrastructure
│   ├── /components
│   │   ├── /ui                   # UButton, UCard, UInput, UModal, etc.
│   │   ├── /common               # NavBar, SidePanel, ResourceBar, etc.
│   │   └── /layout               # DefaultLayout
│   ├── /composables              # useAuth, useToast, useTheme, useWebSocket
│   ├── /services                 # API client (axios)
│   ├── /utils                    # errorHandler, validators
│   ├── /types                    # api.generated.ts, global types
│   ├── /plugins                  # axios config
│   └── /schemas                  # Shared Zod schemas
│
├── /modules                       # Feature modules
│   ├── /auth                     # Authentication (login, register, password reset)
│   ├── /vault                    # Vault management, resources
│   ├── /dwellers                 # Dweller CRUD, stats, equipment
│   ├── /rooms                    # Room grid, building
│   ├── /social                   # Relationships, pregnancy
│   ├── /progression              # Training, quests, objectives
│   ├── /exploration              # Wasteland expeditions
│   ├── /combat                   # Incidents, equipment
│   ├── /radio                    # Recruitment
│   ├── /chat                     # AI conversations
│   └── /profile                  # User settings
│
├── /router                       # Aggregates module routes
└── /views                        # Core views (Home, About)
```

## Module Template

Each module follows this structure:

```
/modules/[feature]/
├── /components/          # Feature components
├── /composables/         # Feature hooks (optional)
├── /stores/              # Pinia stores
├── /services/            # API services (optional)
├── /models/              # Domain models
├── /types/               # Feature types (optional)
├── /views/               # Page components
├── /routes/              # Route config
└── index.ts              # Barrel export
```

## Import Patterns

```typescript
// From core
import { UButton, UCard } from '@/core/components/ui'
import { useAuth, useToast } from '@/core/composables'
import type { components } from '@/core/types/api.generated'

// From modules
import { DwellerCard } from '@/modules/dwellers/components'
import { useDwellerStore } from '@/modules/dwellers/stores'
import type { Dweller } from '@/modules/dwellers/models'

// Cross-module (allowed for related features)
import { useVaultStore } from '@/modules/vault/stores'
```

## Backward Compatibility

Re-exports exist at old paths for gradual migration:
- `@/components/*` → `@/core/components/*`
- `@/stores/*` → `@/modules/*/stores/*`
- `@/composables/*` → `@/core/composables/*`

## Future Enhancements

- Lazy load stores per module
- Module-level error boundaries
- Co-locate tests with modules
