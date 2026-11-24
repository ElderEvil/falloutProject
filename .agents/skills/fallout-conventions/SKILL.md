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

- **Workflow lint needs shellcheck on PATH.** `prek run actionlint` reports `SC####` findings only when
  `shellcheck` is installed; without it a workflow passes locally and fails the `repository-checks` gate
  (e.g. `SC2129` on consecutive `>> "$GITHUB_OUTPUT"` appends — group them in `{ ...; } >> ...`). Verify
  with shellcheck present, or read the failed job log rather than trusting a clean local run.

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

## Merge and release traps

- `gh pr merge --squash` takes its subject from the branch's **first commit**, not the PR title — retitling
  does not change the release bump. Pass `--subject` when the bump matters.
- Check `baseRefName` before merging a stacked PR: GitHub silently points a child PR at the parent branch,
  and `--delete-branch` then orphans the commit.
- Rebasing someone else's branch: re-fetch, compare against the SHA the worktree started from, push with
  `--force-with-lease`. A stale rebase force-push deletes their commits.
- Never hand-create git tags; semantic-release owns them.
- `run_migrations=true` is required whenever the release carries a migration. With it false the deploy
  succeeds and ships code whose models expect missing columns (symptom: 500 on `/vaults/` with
  `column vault.scenario_key does not exist`).

## Local test runs — measured pitfalls

- `cd backend && uv sync` first: `backend/.venv` drifts and an old fastapi fails every import with
  `Depends() got an unexpected keyword argument 'max_concurrency'`.
- A fresh worktree lacks `backend/.env` (gitignored) → conftest dies with `KeyError: 'POSTGRES_USER'`.
- **`prek`'s `ty` hook is a CI gate** (changed backend files, excluding `app/(tests|alembic|crud)`), so a
  clean ruff run proves nothing: `ty check --output-format concise --exit-zero-on-warning <files>`.
- ruff bans `assert` (S101) — narrow optionals with an explicit `raise`, never `assert x is not None`.
- `test_architecture/test_ci_hook_scope.py` fails locally with `prek: command not found` (127);
  environmental, CI supplies prek via `uv run`.
- `conftest.py` has two vault fixtures — `vault` (own) and `user_with_vault` / `room_in_vault` /
  `dweller_in_vault` (another vault). Mixing `dweller` with `room_in_vault` silently tests a cross-vault
  flow; run the full suite after adding a cross-vault invariant.

## Frontend toolchain traps

- lightningcss rejects `var(--token/N)` in the production build; use
  `color-mix(in srgb, var(--token) N%, transparent)`.
- `vi.mock(` factory helpers must be imported before any non-inert app import (mockImportOrderGuard), with
  the component under test imported statically after them — not via `await import()` inside each test.
- `new Audio(url)` needs a constructable stub (`vi.stubGlobal('Audio', AudioStub)`).
- jsdom 31 returns `''` from `getComputedStyle()` on a detached node, so VTU `isVisible()` ignores
  `v-show`: mount with `{ attachTo: document.body }` and unmount after, do not weaken the assertion.
- Frontend tests run through `pnpm test:run <paths>` (`vp test`); there is no bare `vitest` binary.

## Code prose and test size

- Prefer one terse line over a paragraph; delete comments that narrate what the code plainly does. Keep
  invariants, ordering constraints and measured facts — with the number that justifies them.
- Fewer lines is a deliverable: feature delivery time outranks completeness.
- **FastAPI endpoint docstrings are the public OpenAPI descriptions** — shorten them, never drop them.
  `app/tests/**` ignores ruff `D`/`DOC`; `app/` enforces the Google convention.
- Tests: one per distinct failure mode. Merge near-identical cases, drop assertions on framework defaults.
  Trim cases, never the assertions inside a case that survives.

## Architecture guards beyond the endpoint layer

- Services never issue raw `select()`/`execute()` — SQL lives in `app/crud/<entity>.py`.
- A `*_service.py` module must own persistence, orchestration or an external boundary; pure functions
  belong in `app/utils/` (e.g. `utils/broadcast_script.py`).
- Never add entries to a guard's baseline — fix the code, and shrink baselines with each batch.

## Events and transaction boundaries

- **Never emit a game event while an uncommitted transaction has written the vault row.** Objective
  evaluators handle the event on a second session and take `vault.lock_for_update(...)`, so the handler
  waits for the emit's transaction while the emit waits for the handler — a deadlock that ends only when
  `idle_in_transaction_session_timeout` (5 min) rolls the work back, with the player seeing a hang.
- Pattern: call `deposit_caps(..., commit=False, emit_event=False)` inside the transaction, commit, then
  `event_bus.emit(...)` with the credited amount (rush payout and demolition both do this). Pass
  `emit_event=True` only when the caps update commits itself.
- A hang that leaves `idle in transaction` holders on `vault` blocks worker ticks too, so it fails loudly
  across the vault — check `pg_stat_activity` for `wait_event_type='Lock'` before blaming the request path.

## Alembic autogenerate drift

- `alembic check` requires byte-match with model metadata: column types (`Text` vs `String`), nullability,
  indexes (`BaseUUIDModel` auto-indexes `id`), and FK naming per the sibling-model convention.
- Always branch from **current** origin/master: master gains migrations between feature branches, so
  re-check `down_revision` and single-head state before pushing.
- Verify migrations against a throwaway scratch Postgres pod, never the `fallout` namespace DB.

## Test Postgres isolation

- Each xdist worker gets its own database (`<db>_w<worker>`, migrated once per session, dropped at
  teardown) from `app/tests/test_alembic/_support.py::live_pg_engine`. Never add a local copy of that
  fixture — seven existed, all pointed at the shared DB, and let workers collide on unique keys.
- `str(URL)` renders the password as `***` (SQLAlchemy masks it): hand a DSN to another process or
  engine with `render_as_string(hide_password=False)`, and escape `%` as `%%` when Alembic consumes it,
  because it passes the value through configparser.
- A test that commits a real `user`/`vault` must register it with `track_created_identity(...)`; module
  teardown deletes tracked rows before `live_pg_engine` counts `user`/`vault`/`dweller` and fails the
  module that leaves them behind. Reference content is not counted — seeding rewrites it by design.

## Frontend dependency upgrades (Vite+)

- Upgrading Vite+ means bumping the **catalog pair**: `vite-plus: X` and
  `vite: npm:@voidzero-dev/vite-plus-core@Y`, where Y encodes the bundled Vite — they no longer share a
  version. Read Y from `npm view vite-plus@X dependencies.vite`.
- `@vitest/coverage-v8` and `@vitest/ui` must match the vitest that vite-plus bundles.
- `minimumReleaseAge: 10080` gates every bump; a fresh release fails install with
  `ERR_PNPM_NO_MATURE_MATCHING_VERSION`. Wait for maturity rather than excluding it casually.
- `pnpm run typecheck` is `vue-tsc --noEmit`, so it keeps covering `.vue` files; tsrs powers type-aware
  `vp lint` rules only and does not replace it.

## Diagnosing CI and deploy failures (host facts)

- CI SSH probe failures: suspect ufw rule `22/tcp LIMIT IN` before fail2ban — ufw caps new SSH connections
  per source and shared runner IPs trip it. Fix with `ufw delete limit 22/tcp` then `ufw allow 22/tcp`.
- The workflow's fail2ban hint (`mode=aggressive, maxretry=3`) is stale; `fail2ban-client status sshd`
  showing zero bans clears it as a suspect.
- Prove world reachability with `check-host.net/check-tcp`; `tcpdump` is not installed on the production
  host, so local captures need an install first.
- CI logs: `gh run view <run-id> -R ElderEvil/falloutProject --log-failed`.
- Background shells lose exported env on reset — `set -a; source <env>; set +a` inside the background
  command itself.
- A subagent's "verified" is a self-report; re-check external effects (merges, pushes, tags) yourself.
