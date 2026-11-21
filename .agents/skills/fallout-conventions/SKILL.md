---
name: fallout-conventions
description: Use when changing falloutProject's schema, enums, feature flags, endpoints or frontend modules. Lists the CI gates and what each one charges per change, so a schema or flag edit is costed before it fails CI.
---

# falloutProject conventions — the gates and their price

Each gate below fails the PR, not a warning. This is the cost inventory; authoritative rules remain
`AGENTS.md` and the domain docs it links. Size targets and feature intake are in `AGENTS.md`
("Feature intake and size policy").

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
- **`app/tests/test_db/test_utc_migration_contract.py` pins the total count** of `UTCDateTime` columns and
  tables. Adding a `UTCDateTime` column to a table already in the inventory bumps only the column count;
  a new table bumps both. Count from model metadata, never by arithmetic.
- **Migrations are chain-checked**: a test asserts one head and that specific revisions stay in the
  ancestry. Never assert `get_heads() == [<newest>]`.
- **Models must be imported in `app/models/__init__.py`** or autogenerate cannot see them.
- Backfills and data-bearing columns follow `AGENTS.md` ("Data-bearing columns & backfills"); transaction
  ownership follows `docs/backend/SERVICE_LAYER.md`.

## Enums

Adding any PostgreSQL enum value costs **three edits in one commit**:

1. the `StrEnum` member in `app/core/enums.py`;
2. a hand-written migration — `ALTER TYPE ... ADD VALUE` works in a transaction, `DROP VALUE` does not
   exist, so the downgrade is a documented no-op;
3. `PG_ENUM_LABELS_SNAPSHOT` in `app/tests/test_db/test_enum_drift.py` — same commit.

**`NotificationType` costs one extra edit:** `NOTIFICATION_CATEGORY_BY_TYPE` in
`app/core/notification_preferences.py`. Unknown types default to always-enabled, so omission is silent.
The notification-preference contract is in `docs/backend/GAME_MECHANICS.md`.

Enums live only in `app/core/enums.py`; importing them from `app.models.*` fails an architecture test.

## Feature flags

Four edits: `FeatureConfig` in `core/game_config.py`, `FeaturesResponse`, `get_features`, and
`tests/test_api/test_system.py` (asserted as an **exact dict**, so it breaks until updated). Then
regenerate the OpenAPI types. Prod reads flags from the `backend-env` secret via `envFrom` — a `kubectl
patch` needs a `rollout restart` to take effect.

## Endpoints and layers

- Endpoints parse params, call one service, map exceptions. **No queries, no `app.crud` imports** — the
  guard test ratchets per-file CRUD imports against a baseline. A new endpoint file must add zero.
- Dependency direction is endpoints → services → CRUD, never endpoints → CRUD. Details and the baseline
  ratchet are in `AGENTS.md` rule 11 and `docs/backend/SERVICE_LAYER.md`.

## Frontend

- `node scripts/check-boundaries.mjs` hard-fails on `core/` importing `modules/`. A store used by a core
  component (feature flags, side panel) belongs in `core/stores/` and fetches via `@/core/utils/api`.
  `modules/` importing `core/` is fine. Ownership rules are in `frontend/AGENTS.md`.
- Types come from `@/core/types/api.generated`. Regenerate with `pnpm run types:generate` (it needs the
  local backend on `:8000`); never hand-write them.
- Shared logic is one owner: duplicate computations move to the store, and one component owns polling.

## Local verification before pushing

Backend, from `backend/`:

```bash
uv run pytest app/tests -q
uv run alembic heads
uv run ruff check .
```

Frontend, from `frontend/`:

```bash
node scripts/check-boundaries.mjs
pnpm run typecheck
pnpm run lint
pnpm run format:check
pnpm run test:run
```

Concurrency/lock tests need a reachable PostgreSQL
(`podman compose -f docker-compose.infra.yml up -d db redis` from the repository root); otherwise they
skip and prove nothing. `format:check` and the boundary script are separate gates from lint — CI runs
both and they fail independently.

## Deploy

Dispatch `deploy-hetzner.yml` with a versioned tag whose backend and frontend images the release workflow
already pushed. Migrations run in a Job before application images change; a failed Job aborts the rollout.

Enable `maintenance_mode=true` (which requires `run_migrations=true`) for the baseline cutover,
incompatible schema changes, and any lock-taking migration or table rewrite. It stops both writers and
takes a verified pg_dump. Compatible changes can deploy without it: index-only DDL is the documented
exception — use the `autocommit_block` + `postgresql_concurrently` pattern in
[the deployment runbook](../../../docs/DEPLOYMENT.md#concurrent-index-ddl). Concurrent index DDL does
**not** make other lock-taking migrations safe.

The `production-migration` environment needs an approval after you restore the generated dump into
isolated infrastructure and rehearse the migration/rollback there. A 422 "no pending deployment requests"
only means the request is no longer actionable — it can have been approved or consumed already. Verify the
workflow run, the migration Job and `/readiness` before treating the deploy as successful; see
[Release Preflight](../../../docs/DEPLOYMENT.md#release-preflight).

Postgres must never be `rollout`-ed (RollingUpdate + RWO PVC double-mounts) — delete the pod instead.
Inline SQL through `sh -c` breaks on quoting: write the SQL to a file and pipe it into `psql -f -`.
