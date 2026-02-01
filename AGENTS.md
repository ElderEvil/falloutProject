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
uv sync --all-extras --dev
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
- **Architecture**: controller/endpoint → service → crud → DB.

### Backend Error Handling

- Prefer the custom HTTP exceptions in `backend/app/utils/exceptions.py` (e.g., `ResourceNotFoundException`,
  `AccessDeniedException`) over ad-hoc `HTTPException`.
- Log with `logging.getLogger(__name__)` inside services; use `logger.exception(...)` for unexpected errors.

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
- `frontend/oxlint.json` (format: 100 cols, single quotes, no semicolons, 2 spaces)
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

- **Formatting**: 100 char line width; single quotes; no semicolons; 2-space indent (`frontend/oxlint.json`).
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

## Repo Guardrails

1. Never push to git without explicit approval.
2. After backend API changes: regenerate frontend API types: `cd frontend && pnpm run types:generate`.
3. Prefer small, test-backed changes; follow existing patterns (don’t introduce new architectures).
4. Commit messages: `feat:`, `fix:`, `chore:`; branch prefixes: `feat/`, `fix/`, `chore/`.

---

*Last updated: 2026-02-01*
