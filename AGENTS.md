# Fallout Shelter - Agent Development Guide

> **Repo:** `D:\Projects\falloutProject` | **Stack:** FastAPI + Vue 3 + PostgreSQL + Redis

This file is written for agentic coding agents working in this repository.

## Repo Structure

```
backend/app/      # FastAPI (api, core, crud, models, services, utils)
frontend/src/     # Vue 3 (modules, core, components, stores, services)
```

## Rules Files (Cursor/Copilot)

- No `.cursorrules`, `.cursor/rules/**`, or `.github/copilot-instructions.md` found in this repo (as of 2026-02-01).

## Backend (Python/FastAPI)

### Setup & Dev

```bash
cd backend
uv sync --dev
uv run fastapi dev main.py              # http://localhost:8000
uv run alembic upgrade head
```

### Lint / Format

Authoritative config: `backend/pyproject.toml` (`[tool.ruff]`, line-length=120, target=py313).

```bash
cd backend
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .
uv run prek run                          # CI uses this (see .github/workflows/backend-ci.yml)
```

### Tests (pytest)

Authoritative config: `backend/pyproject.toml` (`[tool.pytest.ini_options]`, coverage defaults).

```bash
cd backend
uv run pytest app/tests                  # all backend tests
uv run pytest app/tests -v --tb=short    # CI style

# Single test (recommended patterns)
uv run pytest app/tests/test_file.py
uv run pytest app/tests/test_file.py::TestClass::test_method
uv run pytest -k "name_substring"
```

### Backend Code Style

- **Formatting**: 120 char line length (ruff).
- **Quotes**: use double quotes in Python.
- **Typing**: add type hints for new functions; prefer `UUID4`/Pydantic types where applicable.
- **Import order** (see `backend/app/api/deps.py`): stdlib → third-party → local `app.*`.
- **Architecture**: endpoint → service → crud → DB (see `Service Layer` below).

### Service Layer (MANDATORY)

All business logic MUST live in service classes, not in endpoint functions. Endpoints are thin HTTP handlers — they parse request params, delegate to services, and map exceptions to HTTP responses.

**Rule of thumb:** If an endpoint function contains more than 3 lines of non-trivial logic (validation, orchestration, side effects) beyond calling a service, that logic needs to move into a service.

**Existing services:**
| Service | File | Covers |
|---|---|---|
| `auth_service` | `backend/app/services/auth_service.py` | Login, token refresh, password mgmt, email verification |
| `chat_service` | `backend/app/services/chat_service.py` | Chat with dweller, objective generation |
| `room_service` | `backend/app/services/room_service.py` | Build, destroy, upgrade rooms |
| `vault_service` | `backend/app/services/vault_service.py` | Initiate vault, resource updates, medical transfer |
| `death_service` | `backend/app/services/death_service.py` | Death, revival, permanent death |
| `dweller_service` | `backend/app/services/dweller_service.py` | Dweller updates with room-based status |
| `training_service` | `backend/app/services/training_service.py` | Start/cancel/complete training |
| `quest_service` | `backend/app/services/quest_service.py` | Quest lifecycle, party management |
| `exploration_service` | `backend/app/services/exploration_service.py` | Send/recall/complete explorations |
| `radio_service` | `backend/app/services/radio_service.py` | Recruitment, radio mode |
| `relationship_service` | `backend/app/services/relationship_service.py` | Relationships, compatibility, breeding |
| `user_service` | `backend/app/services/user_service.py` | Registration, profile, AI usage |
| `breeding_service` | `backend/app/services/breeding_service.py` | Pregnancy, delivery, conception |
| `incident_service` | `backend/app/services/incident_service.py` | Incident spawning, resolution |
| `game_loop` | `backend/app/services/game_loop.py` | Game tick processing, pause/resume |
| `notification_service` | `backend/app/services/notification_service.py` | WebSocket/broadcast notifications |
| `conversation_service` | `backend/app/services/conversation_service.py` | Voice chat, audio processing |

**Service pattern:**

```python
# ❌ BAD — business logic in endpoint
@router.post("/login")
async def login(...):
    user = await crud.user.authenticate(...)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    ...

# ✅ GOOD — thin endpoint, business logic in service
@router.post("/login", response_model=Token)
async def login_access_token(...):
    try:
        return await auth_service.login(...)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
```

### Avoid Nested try-except

Do NOT nest try-except blocks inside other try blocks. This makes error handling hard to follow and can mask failures.

```python
# ❌ BAD
try:
    result = await some_agent.run(...)
    try:
        usage = result.usage()
    except Exception:
        logger.warning("...")
    return result
except Exception:
    logger.exception("Fallback")

# ✅ GOOD — extract inner block into a helper
def _extract_usage(result) -> ...:
    try:
        return result.usage()
    except Exception:
        logger.warning("...")
        return None

try:
    result = await some_agent.run(...)
    usage = _extract_usage(result)
    return result, usage
except Exception:
    logger.exception("Fallback")
```

### Vault Ownership Checks

Use `get_user_vault_or_403` from `app.api.deps` for vault ownership verification instead of inline checks.

```python
# ❌ BAD — inline vault ownership check
@router.post("/vaults/{vault_id}/pause")
async def pause_vault(vault_id, user, db_session):
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, ...)
    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, ...)
    ...

# ✅ GOOD — use Depends(get_user_vault_or_403)
@router.post("/vaults/{vault_id}/pause")
async def pause_vault(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    ...
):
    ...
```

### Backend Error Handling

- Prefer the custom HTTP exceptions in `backend/app/utils/exceptions.py` (e.g., `ResourceNotFoundException`,
  `AccessDeniedException`) over ad-hoc `HTTPException`.
- Log with `logging.getLogger(__name__)` inside services; use `logger.exception(...)` for unexpected errors.
- Endpoints catch service exceptions (subclasses of `HTTPException`) and map them: `ValidationException` → 400,
  `ResourceNotFoundException` → 404, `ResourceConflictException` → 409, `VaultOperationException` → 400.

## Frontend (Vue 3 / TypeScript)

### Setup & Dev

```bash
cd frontend
pnpm install
pnpm run dev                              # http://localhost:5173 (runs types:generate first)
pnpm run types:generate                   # requires backend running at :8000
```

### Lint / Format / Types

Authoritative config:

- `frontend/vite.config.ts` (`fmt`: 100 cols, single quotes, no semicolons, 2 spaces)
- `frontend/oxlint.json` (lint rules and ignore patterns)
- `frontend/tsconfig.app.json` (strict: true, strictTemplates: true)

```bash
cd frontend
pnpm run lint
pnpm run lint:fix
pnpm run format
pnpm run format:check
pnpm run typecheck
```

### Tests (Vitest)

Authoritative config: `frontend/vitest.config.ts` (jsdom; includes `tests/**/*.test.ts`).

```bash
cd frontend
pnpm run test                             # watch
pnpm run test:run                          # once (CI equivalent)

# Single test
pnpm run test -- tests/unit/stores/auth.test.ts
pnpm run test -- -t "test name substring"
pnpm run test -- --coverage

```

### Frontend Code Style

- **Formatting**: 100 char line width; single quotes; no semicolons; 2-space indent (`frontend/vite.config.ts` under `fmt`). Run `pnpm run format` or `pnpm exec vp fmt src`.
- **Imports**: prefer `@/` aliases (`frontend/tsconfig.app.json` paths); order roughly: Vue/core → third-party → `@/` → relative.
- **Naming**:
  - Components/types: `PascalCase`
  - Composables: `useXxx`
  - Stores: `useXxxStore` (Pinia composition-style)
- **Architecture**: Store → Service → API.

### Frontend Error Handling

- Use helpers in `frontend/src/core/utils/errorHandler.ts` (e.g., `getErrorMessage`, `handleStoreError`).
- Avoid swallowing errors silently; log context in stores/services.

## UI Guidelines (Terminal CRT Theme)

- Primary color: `#00ff00`.
- Prefer the repo UI components (see `frontend/src/components/ui/`): `UButton`, `UCard`, `UInput`, `UModal`, etc.
- Tailwind utilities only; avoid inline styles.
- Use CRT effects classes where appropriate: `.flicker`, `.terminal-glow`, `.crt-screen`.
- Design token source of truth: `frontend/src/assets/tailwind.css` and `frontend/STYLEGUIDE.md`.

## Bug Fix Workflow (MANDATORY)

When a bug is reported:

1. **Write a failing test first** that reproduces the bug.
2. **Delegate the fix to subagents** (provide the failing test file + repro steps).
3. **Prove the fix** by running the test and ensuring it passes (and run the relevant suite).

## Release Version Bump Workflow

When cutting a release branch or version bump:

1. Update backend version in `backend/pyproject.toml`.
2. Regenerate the backend lockfile: `cd backend && uv lock`.
3. Update frontend version in `frontend/package.json`.
4. Sync frontend lockfile when needed: `cd frontend && pnpm install`.
5. Commit backend and frontend version changes separately (backend `pyproject.toml` + `uv.lock`, frontend `package.json`).
6. Push the release branch and keep unrelated files untracked.

## Repo Guardrails

1. Never push to git without explicit approval.
2. After backend API changes: regenerate frontend API types: `cd frontend && pnpm run types:generate`.
3. Prefer small, test-backed changes; follow existing patterns (don't introduce new architectures).
4. Commit messages: `feat:`, `fix:`, `chore:`; branch prefixes: `feat/`, `fix/`, `chore/`.

---

_Last updated: 2026-06-18_
