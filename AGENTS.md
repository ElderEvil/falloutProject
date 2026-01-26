# Fallout Shelter - Agent Development Guide

> **Version:** 2.4.1 | **Architecture:** FastAPI + Vue 3 + PostgreSQL + Redis

## Project Overview

Fallout Shelter management game with terminal green CRT aesthetic.

**Tech Stack:**
- **Backend:** FastAPI, SQLModel, PostgreSQL 18, Celery, Redis
- **Frontend:** Vue 3.5, TypeScript, Pinia, TailwindCSS v4
- **AI:** OpenAI/Anthropic/Ollama for dweller interactions

**Structure:**
```
falloutProject/
├── backend/app/         # FastAPI (api/v1/endpoints, core, crud, models, services)
└── frontend/src/        # Vue 3 (components, stores, services, views)
```

## Quick Start

**Backend:**
```bash
cd backend
uv sync --all-extras --dev        # Setup
uv run fastapi dev main.py        # Dev server (localhost:8000)
uv run alembic upgrade head       # Migrations
uv run pytest app/tests/          # Tests
uv run ruff check . && ruff format .  # Lint & format
```

**Frontend:**
```bash
cd frontend
pnpm install                      # Setup
pnpm run dev                      # Dev server (localhost:5173)
pnpm run types:generate           # Generate API types
pnpm test                         # Tests
pnpm run lint                     # Lint (Oxlint)
```

## Code Style

### Python (Backend)
- **120 chars**, double quotes, type hints required
- Imports: stdlib → third-party → local
- Naming: `snake_case` (vars), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants)

```python
# API Endpoint Pattern
@router.post("/vaults", response_model=VaultResponse)
async def create_vault(
    vault_data: VaultCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VaultResponse:
    """Create vault with current user ownership."""
    return await vault_service.create(db, obj_in=vault_data, user_id=current_user.id)
```

### TypeScript (Frontend)
- **100 chars**, single quotes, no semicolons
- Imports: `@/` alias for absolute paths
- Naming: `PascalCase` (components, types), `camelCase` (vars, functions)

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { UCard, UButton } from '@/components/ui'

interface Props {
  userId: string
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Default Title'
})

const emit = defineEmits<{
  update: [user: User]
}>()
</script>

<template>
  <UCard :title="title" glow>
    <UButton @click="emit('update', user)">Update</UButton>
  </UCard>
</template>
```

## Architecture Patterns

### Backend: Controller → Service → CRUD → DB
```python
# Service Layer
async def create(db: AsyncSession, obj_in: VaultCreate, user_id: UUID4) -> Vault:
    vault_data = obj_in.model_dump()
    vault_data["user_id"] = user_id
    return await crud.vault.create(db, obj_in=vault_data)
```

### Frontend: Store → Service → API
```typescript
export const useVaultStore = defineStore('vault', () => {
  const vaults = ref<Vault[]>([])

  const fetchVaults = async () => {
    try {
      vaults.value = await vaultService.getVaults()
    } catch (error) {
      handleError(error)
    }
  }

  return { vaults, fetchVaults }
})
```

## Testing

**Backend:**
```python
class TestAuthEndpoints:
    async def test_register_success(self, client: AsyncClient, user_factory):
        user_data = user_factory()
        response = await client.post("/api/v1/auth/register", json=user_data.model_dump())
        assert response.status_code == 201
        assert "access_token" in response.json()
```

**Frontend:**
```typescript
describe('LoginForm', () => {
  it('emits submit event', async () => {
    const wrapper = mount(LoginForm)
    await wrapper.find('input[type="email"]').setValue('test@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.emitted()).toHaveProperty('submit')
  })
})
```

## UI Guidelines

**Terminal Theme:**
- Primary: `#00ff00` (terminal green)
- Always use custom UI components: `UButton`, `UCard`, `UInput`, `UModal`
- TailwindCSS utilities only, no inline styles
- Effects: `.flicker`, `.terminal-glow`, `.crt-screen`

```vue
<UCard title="Vault Management" glow crt>
  <UInput v-model="name" label="Vault Name" />
  <UButton variant="primary">Create</UButton>
</UCard>
```

## Key APIs (v2.3.0)

**Storage Space:** `GET /storage/vault/{vault_id}/space`
- Returns: `used_space`, `max_space`, `available_space`, `utilization_pct`

**Pregnancy Debug (superuser):**
- `POST /pregnancies/debug/force-conception?mother_id=&father_id=`
- `POST /pregnancies/{id}/debug/accelerate`

**Exploration Loot:**
- Items sorted by rarity (legendary → common)
- Overflow tracked in `RewardsSchema.overflow_items`

## Environment Setup

**Backend** (`backend/.env`):
```bash
SECRET_KEY=your-secret-key
POSTGRES_SERVER=localhost
POSTGRES_DB=fallout_db
AI_PROVIDER=ollama
REDIS_HOST=localhost
```

**Frontend** (`frontend/.env.local`):
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Important Rules

1. **NEVER push to git without explicit user approval**
2. Run tests before committing: `pytest` (backend), `pnpm test` (frontend)
3. Coverage: >80% backend, >70% frontend
4. Follow existing patterns - don't introduce new architectures
5. Generate types after backend changes: `pnpm run types:generate`
6. Use semantic commits: `feat:`, `fix:`, `chore:`
7. Branches: `feat/`, `fix/`, `chore/` prefixes
8. **Never merge to master without approval**

## Deployment

**CI/CD:** Auto-build on push to `master` → Docker Hub
- Images: `elerevil/fo-shelter-be:latest`, `elerevil/fo-shelter-fe:latest`

**TrueNAS Staging:**
- Frontend: https://fallout.evillab.dev
- Backend: https://fallout-api.evillab.dev
- Update: `docker compose pull && docker compose up -d`

## Asset Management

### External Image Assets
Room images and other game assets are often fetched from external wikis.

**Download Script:** `scripts/download_room_images.py`
- Fetches high-resolution images from the Fallout Wiki.
- Handles pagination and lazy loading.
- Usage: `uv run scripts/download_room_images.py`

**Storage Policy:**
- For local development: Served via FastAPI static mounting (`/static/room_images/`).
- Future production: Assets will be stored and served via MinIO/RustFS.
- Always use `app.utils.room_assets.get_room_image(name)` to resolve URLs.

---

*Agent guide for Fallout Shelter project | Last updated: 2026-01-26*
