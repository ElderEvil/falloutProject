---
name: fallout-conventions
description: Use when changing falloutProject's schema, enums, feature flags, endpoints or frontend modules. Lists the CI gates and what each one charges per change, so a schema or flag edit is costed before it fails CI.
---

# falloutProject conventions — the gates and their price

Every gate below fails the PR, not a warning. Know the price before starting.

## When to use

- Adding a table, column, enum value, feature flag, endpoint or frontend module.
- Debugging a CI failure that passes locally.
- Estimating how long a schema change will take.

## When not to use

- Pure logic changes inside one service; test-only PRs.

## Schema / migrations

- **New revisions go in `backend/app/alembic/baseline_versions/`.** `alembic.ini` sets
  `version_locations` there; a file in `alembic/versions/` is invisible — `heads` never moves and the
  revision silently never runs. Confirm with `uv run alembic heads`: exactly one head.
- **Timestamps must be aware**: `sa.DateTime(timezone=True)` / the repo's `UTCDateTime`. Copying an older
  migration body produces plain `TIMESTAMP`; SQLite tests pass and **CI's `alembic check` fails on drift**.
  Price: one red CI run per occurrence.
- **`app/tests/test_db/test_utc_migration_contract.py` pins the total count** of `UTCDateTime` columns and
  tables. Adding timestamp columns means bumping both numbers in the same commit. Count from model
  metadata, never by arithmetic.
- **Migrations are chain-checked**: a test asserts one head and that specific revisions stay in the
  ancestry. Never assert `get_heads() == [<newest>]`.
- **Models must be imported in `app/models/__init__.py`** or autogenerate cannot see them.

## Enums

Adding a `NotificationType` (or any PG enum) value costs **four edits in one commit**:

1. the `StrEnum` member in `app/core/enums.py`;
2. a hand-written migration — `ALTER TYPE ... ADD VALUE` works in a transaction, `DROP VALUE` does not
   exist, so the downgrade is a documented no-op;
3. `PG_ENUM_LABELS_SNAPSHOT` in `app/tests/test_db/test_enum_drift.py` — same commit;
4. `NOTIFICATION_CATEGORY_BY_TYPE` in `app/core/notification_preferences.py` (unknown types default to
   always-enabled, so omission is silent).

Enums live only in `app/core/enums.py`; importing them from `app.models.*` fails an architecture test.

## Feature flags

Four edits: `FeatureConfig` in `core/game_config.py`, `FeaturesResponse`, `get_features`, and
`tests/test_api/test_system.py` (asserted as an **exact dict**, so it breaks until updated). Then
regenerate the OpenAPI types. Prod reads flags from the `backend-env` secret via `envFrom` — a `kubectl
patch` needs a `rollout restart` to take effect.

## Endpoints and layers

- Endpoints parse params, call one service, map exceptions. **No queries, no `app.crud` imports** — the
  guard test ratchets per-file CRUD imports against a baseline. A new endpoint file must add zero.
- Dependency direction is endpoints → services → CRUD, never endpoints → CRUD.

## Frontend

- `node scripts/check-boundaries.mjs` hard-fails on `core/` importing `modules/`. A store used by a core
  component (feature flags, side panel) belongs in `core/stores/` and fetches via `@/core/utils/api`.
  `modules/` importing `core/` is fine.
- Types come from `@/core/types/api.generated` — regenerate from `app.openapi()` offline, never hand-write.
- Shared logic is one owner: duplicate computations move to the store, and one component owns polling.

## Local verification before pushing

```bash
cd backend && uv run pytest app/tests -q && uv run alembic heads && uv run ruff check app
cd frontend && node scripts/check-boundaries.mjs && pnpm run typecheck && pnpm run lint \
  && pnpm run format:check && pnpm run test:run
```

`format:check` and the boundary script are separate gates from lint — CI runs them and they fail
independently. Local SQLite also cannot exercise `FOR UPDATE`, so row-lock behaviour is only proven in
production or with a real Postgres.

## Deploy

Dispatch `deploy-hetzner.yml` with the release tag. Migrations present → `run_migrations=true` **and**
`maintenance_mode=true` (that path takes a verified pg_dump). No migration → plain dispatch. The
`production-migration` environment needs approval; `current_user_can_approve` flips to `false` once you
have approved, so a 422 "no pending deployment requests" is success, not failure.

Postgres must never be `rollout`-ed (RollingUpdate + RWO PVC double-mounts) — delete the pod instead.
Inline SQL through `sh -c` breaks on quoting: write the SQL to a file and pipe it into `psql -f -`.
