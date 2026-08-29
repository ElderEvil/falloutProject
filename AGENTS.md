# Fallout Shelter - Agent Development Guide

> **Repo:** `D:\Projects\falloutProject` | **Stack:** FastAPI + Vue 3 + PostgreSQL + Redis
>
> Agentic-coding guide. Keep every line here because removing it would cause a mistake the agent couldn't infer from code.

## Orientation

| Topic | Source |
|---|---|
| Setup, run, env vars | `README.md` |
| Design tokens & UI theme | `frontend/src/assets/tailwind.css`, `docs/frontend/STYLEGUIDE.md` |
| Deployment | `docs/DEPLOYMENT.md` |
| Roadmap & theming | `docs/ROADMAP.md`, `CHANGELOG.md` |
| Project skills | `.agents/skills/` (load the matching one, e.g. `fastapi`, `pytest`, `vue-best-practices`, `sqlmodel`) |

Stack rules: `uv` (Python), `pnpm` (Node). Python uses double quotes; TypeScript/Vue uses single quotes, no semicolons.

## Backend (Python/FastAPI)

### Commands (from `backend/`)

```bash
uv sync --dev
uv run ruff check .          # lint; add --fix to autofix
uv run ruff format .         # 120-col formatting
uv run pytest app/tests      # full suite (~4.5 min)
uv run pytest <file>::<Test>::<method>   # single test
uv run alembic upgrade head  # apply migrations
uv run fastapi dev main.py   # dev server :8000
```

CI gate: `uv run prek run` (see `.github/workflows/backend-ci.yml`).

### Architecture (MANDATORY)

Business logic lives in **services**, never endpoints. Endpoints are thin: parse params → call a service → map exceptions to HTTP.

Rule of thumb: if an endpoint has >3 lines of non-trivial logic beyond a service call, move it into a service.

### Background task session compatibility

Dramatiq game-tick actors create raw SQLAlchemy `AsyncSession` instances via
`sqlalchemy.ext.asyncio.async_sessionmaker`. These sessions do not provide
SQLModel's `.exec()` method. CRUD/services used by `game_tick`,
`process_vault_tick`, or other `task_session()` actors must use
`.execute(...).scalars()` unless the session factory explicitly sets
`class_=sqlmodel.ext.asyncio.session.AsyncSession`. Any session-factory or CRUD
refactor in this path requires a regression test using the raw SQLAlchemy
session type.

Error handling:
- Prefer custom exceptions in `backend/app/utils/exceptions.py` over ad-hoc `HTTPException`.
- Endpoints map service exceptions: `ValidationException`→400, `ResourceNotFoundException`→404, `ResourceConflictException`→409, `VaultOperationException`→400.
- Log with `logging.getLogger(__name__)`; use `logger.exception(...)` for unexpected errors.
- Do **not** nest try-except; extract inner blocks into helpers.

Ownership checks: use `get_user_vault_or_403` / `verify_dweller_access` from `app.api.deps`, never inline vault-ownership checks.

### DB Enums & Alembic Migrations (MANDATORY)

When adding/removing/renaming a Python `StrEnum`/`IntEnum` mapped to a PostgreSQL enum column:

1. **Autogenerate does NOT detect enum value changes** — write the migration manually with `op.execute()` (e.g. `ALTER TYPE notificationtype ADD VALUE 'DWELLER_DIED'`).
2. PG constraints: `ADD VALUE` works in a transaction; there is **no `DROP VALUE`** (recreate the type); rename via `ALTER TYPE ... RENAME VALUE`.
3. **Regression guard:** update `PG_ENUM_LABELS_SNAPSHOT` in `backend/app/tests/test_db/test_enum_drift.py` in the SAME commit; run `uv run pytest app/tests/test_db/test_enum_drift.py`.

> **Outage trap:** a member added to the Python enum but never migrated → `InvalidTextRepresentationError` → poisoned connection pool → crash-loop. Always migrate before using a new enum member.

## Frontend (Vue 3 / TypeScript)

### Commands (from `frontend/`)

```bash
pnpm install
pnpm run dev                  # :5173 (runs types:generate first)
pnpm run types:generate       # requires backend at :8000; run after backend API changes
pnpm run lint && pnpm run typecheck
pnpm run test:run             # CI-equivalent (or: pnpm run test -- <file>)
```

### Conventions

- Naming: components/types `PascalCase`, composables `useXxx`, stores `useXxxStore` (Pinia composition-style).
- Architecture: Store → Service → API; prefer `@/` aliases.
- Error handling: use `frontend/src/core/utils/errorHandler.ts` (`getErrorMessage`, `handleStoreError`); log context, don't swallow errors.

## UI (Terminal CRT Theme)

- Primary: `#00ff00`; use repo components (`UButton`, `UCard`, `UInput`, `UModal`, …); Tailwind utilities only (no inline styles); CRT classes where fitting (`.flicker`, `.terminal-glow`, `.crt-screen`).
- Design tokens live in `frontend/src/assets/tailwind.css` and `docs/frontend/STYLEGUIDE.md`.

## Bug Fix Workflow (MANDATORY)

1. Write a failing test reproducing the bug first.
2. Fix, then prove it by running the test (and the relevant suite).

## Releases

- **Version authority:** Semantic Release chooses versions — never bump manually.
- **No root `package.json`:** release tooling runs from CI via a pinned `npx --package` invocation (`.github/workflows/release.yml`), so the repo root has no npm manifest or lockfile; frontend deps stay in `frontend/` (pnpm) and backend deps in `backend/` (uv). Keep it that way — do not reintroduce a root `package.json` or `npm ci` for release purposes.
- **Theming (v2.42+):** each release is named after its headline feature (e.g. "The Family Update"); theme recorded in `docs/ROADMAP.md` and as the `CHANGELOG.md` release title. A theme may span backend + frontend; it does not constrain which workstreams ship.
- ROADMAP stays **future-plans-first**; history lives in `CHANGELOG.md`.

## Guardrails

1. Never push to git without explicit approval.
2. After backend API changes: `cd frontend && pnpm run types:generate`.
3. Small, test-backed changes; follow existing patterns; commit messages `feat:`/`fix:`/`chore:`; branch prefixes `feat/`/`fix/`/`chore/`. When touching Python, use `ty` and fix clear, local diagnostics as incremental cleanup; it is not a reason to widen unrelated work.
4. **Architecture over simplification (MANDATORY):** the layered structure always wins over the LOC/file-count rules below. Backend: `models/`, `schemas/`, `crud/`, `services/`, thin routers in `api/v1/endpoints/` — **no all-in-one routers** (no business logic or schema definitions in endpoint files; endpoints parse params → call service → map exceptions). Frontend: `modules/<name>/` with `components/`, `composables/`, `stores/`, `models/`, `api/`. Never merge layers into one file to save lines; never declare schemas/models inline in a router or endpoint.
5. **Net-LOC & file-count rule (v2.35+):** every update must have a negative net source-LOC change — compact/remove existing code (DRY) before adding; don't count generated files, lockfiles, or format-only changes. Prefer fewer files too: do not split into more modules/files unless readability genuinely suffers — but never below the architecture floor from rule 4.
6. **DRY / KISS / YAGNI:** one source of truth per fact; the simplest thing that works; no speculative abstractions, no "we might need this later" code. A new abstraction must pay for itself by removing more than it adds.
7. **Fail fast, minimize try-except (soft but binding):** the codebase favors fail-fast — let errors propagate to a single handler, don't wrap every call. Keep try-except blocks few and shallow: one per operation boundary at most, never nested; extract inner blocks into helpers. Prefer returning early / raising over defensive wrapping.
8. **Frontend simplification heuristic (in order):** does it need to exist? → stdlib → native platform → installed dep → one line → the minimum that works.

## Dev Environment (Agent Quick-Start)

In Zed, use the project tasks: `Fallout: Run Podman infrastructure`, then `Fallout: Run backend server` and `Fallout: Run frontend server`. The backend task applies migrations before starting FastAPI; use `Fallout: Stop Podman infrastructure` when finished.

---

_Last updated: 2026-08-23_
