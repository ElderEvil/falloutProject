# Fallout Shelter Project - Development Guide for Agentic Coding Agents

> **Version:** 2.2.0
> **Last Updated:** 2026-01-23
> **Architecture:** FastAPI + Vue 3 monorepo

## 🏗️ Project Overview

This is a **Fallout Shelter management game** built as a modern web application:

- **Backend:** FastAPI + SQLModel + PostgreSQL 18 + Celery + Redis
- **Frontend:** Vue 3.5 + TypeScript + Vite + Pinia + TailwindCSS v4
- **Theme:** Terminal green CRT aesthetic inspired by Fallout universe
- **AI Features:** LLM-powered dweller interactions with OpenAI/Anthropic/Ollama

## 📁 Repository Structure

```
falloutProject/
├── backend/                  # FastAPI Python application
│   ├── app/
│   │   ├── api/v1/endpoints/ # API route handlers
│   │   ├── core/             # Security, config, logging
│   │   ├── crud/             # Database operations
│   │   ├── models/           # SQLModel database models
│   │   ├── services/         # Business logic layer
│   │   ├── utils/            # Utilities and helpers
│   │   ├── agents/           # AI agent implementations
│   │   ├── middleware/       # FastAPI middleware
│   │   ├── db/               # Database setup
│   │   └── tests/            # Test suite
│   ├── locust/               # Load testing scripts
│   └── pyproject.toml        # Python configuration
├── frontend/                 # Vue 3 TypeScript application
│   ├── src/
│   │   ├── components/       # Vue components
│   │   │   ├── ui/          # Base UI components
│   │   │   ├── common/      # Shared app components
│   │   │   └── [feature]/   # Feature-specific components
│   │   ├── stores/          # Pinia stores (state management)
│   │   ├── services/        # API services
│   │   ├── composables/     # Vue composables (hooks)
│   │   ├── types/           # TypeScript type definitions
│   │   ├── models/          # Domain models
│   │   ├── schemas/         # Zod validation schemas
│   │   └── views/           # Page components
│   ├── tests/unit/          # Unit tests
│   └── package.json         # Node.js configuration
├── docs/                     # Documentation
└── docker-compose.yml        # Development containers
```

## 🚀 Essential Commands

### Backend (Python/FastAPI)

```bash
cd backend

# Setup & Dependencies
uv sync --all-extras --dev
prek install                    # Pre-commit hooks

# Development Server
uv run fastapi dev main.py      # http://localhost:8000

# Database Operations
uv run alembic upgrade head     # Apply migrations
uv run alembic revision --autogenerate -m "message"  # Create migration

# Testing
uv run pytest app/tests/                           # Run all tests
uv run pytest app/tests/test_api/test_auth.py     # Single test file
uv run pytest -k "test_login"                      # Tests matching pattern
uv run pytest --cov=app                           # With coverage
uv run pytest --cov=app --cov-report=html         # HTML coverage report

# Code Quality
uv run ruff check .                               # Lint
uv run ruff check --fix .                         # Auto-fix linting
uv run ruff format .                              # Format code
uv run prek run                                   # Run pre-commit hooks
```

### Frontend (TypeScript/Vue)

```bash
cd frontend

# Setup & Dependencies
pnpm install

# Development Server
pnpm run dev                         # http://localhost:5173
pnpm run types:generate              # Generate API types from backend

# Testing
pnpm test                            # Run all tests (Vitest)
pnpm test tests/unit/stores/auth.test.ts  # Single test file
pnpm test --reporter=verbose         # Detailed output
pnpm test --watch                    # Watch mode
pnpm test --coverage                 # With coverage

# Building
pnpm run build                       # Production build
pnpm run build:strict                # Build with type checking
pnpm run build:with-types            # Generate types + build + type check
pnpm run preview                     # Preview production build

# Code Quality
pnpm run lint                        # Lint with Oxlint (fast Rust-based)
```

### Full Stack Development

```bash
# Start both backend and frontend in parallel
docker-compose up -d                  # Start all services
# Or run manually:
# Terminal 1: cd backend && uv run fastapi dev main.py
# Terminal 2: cd frontend && pnpm run dev
```

## 🎯 Code Style Guidelines

### Python (Backend)

**Linter & Formatter:** Ruff (configured in `pyproject.toml`)

- **Line length:** 120 characters
- **Import style:** isort-compatible (stdlib → third-party → local)
- **Quote style:** Double quotes for strings, single for docstrings
- **Type hints:** Required for all functions and variables

**Import Order:**

```python
# Standard library imports first
import logging
from typing import TYPE_CHECKING

# Third-party imports
from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel import select

# Local imports
from app import crud
from app.core.config import settings
from app.models.user import User
```

**Naming Conventions:**

- **Variables/Functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private:** `_leading_underscore`
- **Dunder:** `__magic_methods__`

**Function Documentation:**

```python
async def create_user(
        user: UserCreate,
        db: AsyncSession = Depends(get_db),
) -> User:
    """
    Create a new user in the database.

    :param user: User creation data
    :type user: UserCreate
    :param db: Database session
    :type db: AsyncSession
    :returns: Created user instance
    :rtype: User
    :raises UserAlreadyExistsError: If user email already exists
    """
    return await crud.user.create(db, obj_in=user)
```

### TypeScript (Frontend)

**Linter & Formatter:** Oxlint (configured in `oxlint.json`)

- **Line length:** 100 characters
- **Import style:** Absolute imports with `@/` alias
- **Quote style:** Single quotes for strings
- **Semicolons:** Never (ESLint auto-removes)

**Import Order:**

```typescript
// Vue/external imports
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'

// Local imports
import { authService } from '@/services/authService'
import type { User } from '@/types/user'
import { useAuthStore } from '@/stores/auth'
```

**Component Structure:**

```vue

<script setup lang="ts">
  /**
   * Component description
   * @component
   */
  import { computed, ref } from 'vue'
  import { UCard, UButton } from '@/components/ui'
  import type { User } from '@/types/user'

  interface Props {
    userId: string
    title?: string
  }

  interface Emits {
    (e: 'update', user: User): void

    (e: 'delete', id: string): void
  }

  const props = withDefaults(defineProps<Props>(), {
    title: 'Default Title'
  })

  const emit = defineEmits<Emits>()

  // Reactive state
  const isLoading = ref(false)
  const user = computed(() => store.getUser(props.userId))

  // Methods
  const handleUpdate = (userData: User) => {
    emit('update', userData)
  }
</script>

<template>
  <UCard :title="title" glow>
    <template #header>
      <slot name="header" />
    </template>
    <p>User ID: {{ userId }}</p>
    <UButton @click="handleUpdate">Update</UButton>
  </UCard>
</template>
```

**Naming Conventions:**

- **Components:** `PascalCase`
- **Variables/Functions:** `camelCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Files:** `kebab-case` for components, `camelCase` for utilities
- **Types/Interfaces:** `PascalCase`

## 🧪 Testing Patterns

### Backend Testing

**Test Structure:**

```python
# tests/test_api/test_auth.py
import pytest
from httpx import AsyncClient
from app.core.config import settings


class TestAuthEndpoints:
    """Test authentication endpoints."""

    async def test_register_user_success(
            self,
            client: AsyncClient,
            user_factory: Callable[..., UserCreate]
    ) -> None:
        """Test successful user registration."""
        user_data = user_factory()
        response = await client.post(
            "/api/v1/auth/register",
            json=user_data.model_dump()
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data.email
        assert "access_token" in data
```

**Key Testing Patterns:**

- **Async fixtures** for database setup
- **Factory pattern** for test data (`factory-boy`)
- **Dependency injection** test overrides
- **Mock external services** (MinIO, Redis, OpenAI)
- **Coverage requirement:** Maintain >80% coverage

### Frontend Testing

**Component Testing:**

```typescript
// tests/unit/components/auth/LoginForm.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import LoginForm from '@/components/auth/LoginForm.vue'

describe('LoginForm', () => {
  it('renders login form correctly', () => {
    const wrapper = mount(LoginForm)
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('emits submit event with form data', async () => {
    const wrapper = mount(LoginForm)

    await wrapper.find('input[type="email"]').setValue('test@example.com')
    await wrapper.find('input[type="password"]').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.emitted()).toHaveProperty('submit')
    expect(wrapper.emitted('submit')?.[0]).toEqual([{
      email: 'test@example.com',
      password: 'password123'
    }])
  })
})
```

**Store Testing:**

```typescript
// tests/unit/stores/auth.test.ts
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '@/stores/auth'

describe('AuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with correct default state', () => {
    const store = useAuthStore()
    expect(store.user).toBe(null)
    expect(store.isAuthenticated).toBe(false)
    expect(store.isLoading).toBe(false)
  })
})
```

## 🔐 Error Handling Patterns

### Backend Error Handling

**Custom Exceptions:**

```python
# app/utils/exceptions.py
class FalloutException(Exception):
    """Base exception for the application."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UserAlreadyExistsError(FalloutException):
    """Raised when trying to create a user that already exists."""

    def __init__(self, email: str):
        super().__init__(f"User with email {email} already exists", 409)
```

**API Error Handler:**

```python
# app/api/v1/endpoints/auth.py
@router.post("/register", status_code=201)
async def register(
        user_data: UserCreate,
        db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user."""
    try:
        user = await user_service.create(db, obj_in=user_data)
        return UserResponse.model_validate(user)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message
        )
    except Exception as exc:
        logger.error(f"Unexpected error during registration: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Frontend Error Handling

**Global Error Handler:**

```typescript
// src/utils/errorHandler.ts
import { toast } from '@/composables/useToast'

export interface ApiError {
  detail: string
  status_code: number
}

export function handleError(error: unknown): void {
  if (error && typeof error === 'object' && 'response' in error) {
    const apiError = error.response?.data as ApiError
    toast.error(apiError?.detail || 'An unexpected error occurred')
  } else if (error instanceof Error) {
    toast.error(error.message)
  } else {
    toast.error('An unknown error occurred')
  }

  console.error('Error details:', error)
}
```

**Service Error Handling:**

```typescript
// src/services/authService.ts
export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      const response = await api.post<AuthResponse>('/auth/login', credentials)
      return response.data
    } catch (error) {
      handleError(error)
      throw error // Re-throw for store handling
    }
  }
}
```

## 🎨 UI/UX Guidelines

### Terminal Theme Design System

**Color Palette (Terminal Green Focus):**

- **Primary:** `#00ff00` (terminal green)
- **Background:** `#000000` (black)
- **Surface:** `#111111` (dark gray)
- **Text:** `#00ff00` variants (light/dim for states)
- **Semantic:** Success (green), Warning (orange), Danger (red), Info (blue)

**Component Usage:**

```vue
<!-- Always use custom UI components from @/components/ui -->
<script setup lang="ts">
  import { UButton, UInput, UCard, UModal } from '@/components/ui'
  import { PlusIcon, UserIcon } from '@heroicons/vue/24/solid'
</script>

<template>
  <UCard title="Vault Management" glow crt>
    <UInput
      v-model="vaultName"
      label="Vault Name"
      placeholder="Enter vault number..."
      :icon="UserIcon"
    />
    <div class="flex space-x-2 mt-4">
      <UButton variant="primary" :icon="PlusIcon">
        Create Vault
      </UButton>
      <UButton variant="secondary">
        Cancel
      </UButton>
    </div>
  </UCard>
</template>
```

**CSS Guidelines:**

- Use **TailwindCSS utilities** only
- Apply **design tokens** from `@theme` in `tailwind.css`
- **Never use inline styles**
- Follow **class organization order**: Layout → Positioning → Box Model → Typography → Visual → Interactive → Responsive

**Animation Effects:**

- `.flicker` - CRT monitor flicker
- `.terminal-glow` - Green phosphor glow
- `.crt-screen` - CRT container effect
- `.scanlines` - Scanline overlay (global)

## 📦 Import Management

### Backend Import Aliases

No import aliases - use absolute imports from `app`:

```python
from app.services.auth import AuthService
from app.models.user import User
from app.core.security import get_password_hash
```

### Frontend Import Aliases

Use `@/` alias for clean imports:

```typescript
import { authService } from '@/services/authService'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/user'
import { UButton } from '@/components/ui'
```

**Type-only imports:**

```typescript
import type { User, Vault } from '@/types'
import type { Component } from 'vue'
```

## 🔧 Development Workflow

### Before Starting Work

1. **Update dependencies:**
   ```bash
   cd backend && uv sync
   cd frontend && pnpm install
   ```

2. **Generate types (frontend):**
   ```bash
   cd frontend && pnpm run types:generate
   ```

3. **Run tests to ensure clean state:**
   ```bash
   cd backend && uv run pytest app/tests/
   cd frontend && pnpm test
   ```

### During Development

1. **Make changes** following the established patterns
2. **Run linting frequently:**
   ```bash
   cd backend && uv run ruff check .
   cd frontend && pnpm run lint
   ```
3. **Run tests relevant to your changes:**
   ```bash
   # Single test file
   cd backend && uv run pytest app/tests/test_services/test_auth.py
   cd frontend && pnpm test tests/unit/stores/auth.test.ts
   ```

### Before Committing

1. **Run all tests:**
   ```bash
   cd backend && uv run pytest app/tests/ --cov=app
   cd frontend && pnpm test --coverage
   ```

2. **Check code quality:**
   ```bash
   cd backend && uv run ruff check . && uv run ruff format .
   cd frontend && pnpm run lint
   ```

3. **Run pre-commit hooks:**
   ```bash
   cd backend && uv run prek run
   ```

## 🏛️ Architecture Patterns

### Backend Service Layer

**Controller → Service → CRUD → Database:**

```python
# API Endpoint
@router.post("/vaults", response_model=VaultResponse)
async def create_vault(
        vault_data: VaultCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> VaultResponse:
    return await vault_service.create(db, obj_in=vault_data, user_id=current_user.id)


# Service Layer
async def create(
        db: AsyncSession,
        obj_in: VaultCreate,
        user_id: UUID4,
) -> Vault:
    vault_data = obj_in.model_dump()
    vault_data["user_id"] = user_id
    return await crud.vault.create(db, obj_in=vault_data)
```

### Frontend Store Pattern

**Store → Service → API:**

```typescript
// Store
export const useVaultStore = defineStore('vault', () => {
  const vaults = ref<Vault[]>([])
  const isLoading = ref(false)

  const fetchVaults = async () => {
    isLoading.value = true
    try {
      vaults.value = await vaultService.getVaults()
    } catch (error) {
      handleError(error)
    } finally {
      isLoading.value = false
    }
  }

  return { vaults, isLoading, fetchVaults }
})

// Service
export const vaultService = {
  async getVaults(): Promise<Vault[]> {
    const response = await api.get<Vault[]>('/vaults')
    return response.data
  }
}
```

### v2.3.0 API Patterns

**Storage Space API** (`GET /storage/vault/{vault_id}/space`):
- Returns `used_space`, `max_space`, `available_space`, `utilization_pct`
- Used for exploration loot overflow handling

**Pregnancy Debug Endpoints** (superuser-only):
- `POST /pregnancies/debug/force-conception?mother_id=&father_id=` - Force pregnancy
- `POST /pregnancies/{id}/debug/accelerate` - Make pregnancy immediately due

**Storage Validation Pattern** (exploration coordinator):
- Items sorted by rarity (legendary > rare > uncommon > common)
- Higher rarity items prioritized when storage full
- Overflow items tracked in `RewardsSchema.overflow_items`

## 🎯 Best Practices

### Backend

1. **Always use async/await** for database operations
2. **Validate input with Pydantic** models
3. **Use dependency injection** for database sessions
4. **Log structured information** with context
5. **Handle specific exceptions** with proper HTTP status codes
6. **Write short commit messages**
7. **Add type hints** for all public functions
8. **Use factories** for test data generation

### Frontend

1. **Use Composition API** with `<script setup>`
2. **Type all props and emits** with interfaces
3. **Prefer composables** over mixins
4. **Use stores for global state** only
5. **Validate API responses** with Zod schemas
6. **Test user interactions** not implementation details
7. **Follow Vue 3 style guide** conventions
8. **Use semantic HTML5** elements

## 🔍 Debugging Tips

### Backend

1. **Use VS Code Python debugger** with launch configurations
2. **Check logs** in `app/core/logging.py` - structured JSON format
3. **Database queries** - Enable SQL logging in development
4. **API testing** - Use FastAPI docs at `/docs` endpoint
5. **Async debugging** - Use `await` statements properly

### Frontend

1. **Vue DevTools** extension for component inspection
2. **Pinia DevTools** for store state debugging
3. **Network tab** for API request inspection
4. **Console logging** with descriptive prefixes
5. **TypeScript strict mode** catches many errors early

## 📋 Environment Setup

### Backend Environment Variables

Copy `backend/.env.example` to `backend/.env`:

```bash
# Core settings
SECRET_KEY=your-secret-key-here
ENVIRONMENT=local

# Database (use localhost for native, db for docker)
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=fallout_db

# AI Provider (openai, anthropic, ollama)
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1

# Redis (use localhost for native, redis for docker)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Frontend Environment Variables

Create `frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_VERSION=1.13.0
```

---

## 🚨 Important Reminders for Agents

1. **Never commit secrets** or environment files with real credentials
2. **Always run tests** before pushing changes
3. **Follow existing patterns** - don't introduce new architectures without discussion
4. **Maintain backward compatibility** for API endpoints
5. **Use semantic versioning** for breaking changes
6. **Update documentation** when adding new features
7. **Check test coverage** - maintain >80% for backend, >70% for frontend
8. **Respect the terminal theme** when adding UI components
9. **Generate types** after backend API changes
10. **Test on both mobile and desktop** for responsive design

**When in doubt, ask for clarification rather than make assumptions about the codebase architecture.**

---

## Git

- When creating branches, prefix them with feat/ fix/ chore/ etc.
- **NEVER merge to master/main without explicit user approval** - always ask before merging release branches or any branch to master

---

## Deployment

### Environments

| Environment | Config File | Description |
|-------------|-------------|-------------|
| Local Dev | `docker-compose.yml` | Development with hot reload |
| TrueNAS Staging | [docs/examples/docker-compose.truenas.yml](docs/examples/docker-compose.truenas.yml) | Production-like staging |

### Docker Images

Automated builds on semantic release (push to `master`):
- `elerevil/fo-shelter-be:latest`, `elerevil/fo-shelter-be:v1.x.x`
- `elerevil/fo-shelter-fe:latest`, `elerevil/fo-shelter-fe:v1.x.x`

### CI/CD

**Workflows:**
- `.github/workflows/release.yml` - Semantic release
- `.github/workflows/build.yml` - Docker image builds

**Required GitHub Secrets:**
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub access token

**Required GitHub Variables:**
- `PRODUCTION_API_URL` - Frontend API URL (e.g., `https://fallout-api.evillab.dev`)

### TrueNAS Staging

**Location:** `/mnt/dead-pool/apps/fallout-shelter/config/`

**Domains:**
- Frontend: `https://fallout.evillab.dev`
- Backend: `https://fallout-api.evillab.dev`
- Media: `https://fallout-media.evillab.dev`

**Update procedure:**
```bash
cd /mnt/dead-pool/apps/fallout-shelter/config
docker compose pull
docker compose up -d
docker compose exec fastapi uv run alembic upgrade head  # if needed
```

**Complete guide:** [docs/deployment/TRUENAS_SETUP.md](docs/deployment/TRUENAS_SETUP.md)

---

## Plans

- Make the plan extremely concise. Sacrifice grammar for the sake of concision.
- At the end of each plan give me a list of unresolved questions to answer, if any.

---

*This guide is maintained for agentic coding agents working on the Fallout Shelter project. Last updated: 2026-01-21*
