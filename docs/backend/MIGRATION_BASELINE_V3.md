# Migration baseline (post-3.0 schema)

**Status: promoted on 2026-11-14; `alembic.ini` now runs one baseline revision.**
Fresh databases apply `squash_4b3cbd7b15ff` and nothing else. Existing databases finish
the legacy graph, pass the guarded adoption check and are stamped to the baseline by the
maintenance deploy. The legacy history remains in `alembic-legacy.ini` for adoption and
rollback. No version is bumped manually.

The [October experiment](MIGRATION_SQUASH_EXPERIMENT.md) proved the machinery through
`b7e3d9c1a5f2`. The artifacts were regenerated on 2026-11-13 from an empty PostgreSQL
18 database replayed through `4b3cbd7b15ff`, including the 3.0 aware-UTC schema:
revision `squash_4b3cbd7b15ff`, 46 application tables (47 with `alembic_version`),
106 objective seeds and four immutable v1 prompt seeds. A maintained database newer
than the pinned legacy head is rejected; the tool never guesses that it is compatible.

> **Regeneration rule.** After promotion, new schema migrations descend from the
> baseline; do not add revisions to `app/alembic/versions/`. Regenerate the SQL,
> revision and manifest together with `scripts/build_alembic_baseline.py` only when
> re-founding the baseline; the legacy graph stays frozen at `4b3cbd7b15ff`.

## Machinery

| Artifact | Purpose |
|---|---|
| `backend/alembic.ini` and `app/alembic/baseline_versions/` | Default graph: one frozen baseline revision |
| `backend/alembic-legacy.ini` and `app/alembic/versions/` | Frozen legacy graph retained for adoption and rollback |
| `app/alembic/baseline_versions/*.sql` | Frozen schema and migration-owned content from a clean legacy replay |
| `app/alembic/baseline_versions/*.json` | Reviewed schema manifest, PostgreSQL major and exact revision pair |
| `app/alembic/baseline_tools.py` | Operator-only check, freeze and transactional adoption commands |
| `scripts/build_alembic_baseline.py` | Replays the legacy graph into a scratch database and rewrites the SQL, revision, manifest, manifest path and regression-test constants |

The command does not import the API, start workers, perform player backfills or
load content from current game catalogs. It uses the usual backend database
configuration; `--database` must match the configured database name. Connection
credentials are never accepted as command arguments or printed in results.

From `backend/`, check an existing test database:

```bash
POSTGRES_DB=fallout_squash_legacy_20261020 ASYNC_DATABASE_URI= \
  uv run python -m app.alembic.baseline_tools check \
  --database fallout_squash_legacy_20261020
```

`adopt` without `--apply` performs the same read-only check. With `--apply`, the
tool takes exclusive table locks with a five-second lock timeout, verifies the
revision and schema, and updates only the single Alembic version row inside one
transaction. Failed checks roll back; repeating adoption at the baseline is a
verified no-op. The tool requires the rehearsed PostgreSQL major, exact column
properties/order, constraints/names, indexes and ordered enum labels. Physical
column-number gaps from dropped legacy columns are ignored. It deliberately
rejects drift rather than accepting an operator override. Views, functions,
extensions, roles, privileges, RLS policies and other custom database objects are
outside this manifest's scope; inventory and validate any such objects separately
before a real cutover. Stopping all writers remains part of the maintenance plan.

The existing local clone fails this check because it has recorded drift. Its
earlier experimental stamp bypassed these checks to prove marker/data preservation
on a disposable copy; do not copy that manual stamp into a deployment Job.

## Release preparation gates

- [x] Record the legacy head, baseline revision and PostgreSQL major: `4b3cbd7b15ff`,
  `squash_4b3cbd7b15ff`, PostgreSQL 18. The source commit/image digest and supported
  upgrade sources remain to be recorded. The baseline and legacy head represent the
  same schema and migration-owned seed state.
- [ ] Inventory every maintained database's revision and custom database objects.
  Reconcile drift through reviewed, data-safe migrations or an explicitly documented
  operational procedure. The October differences include missing defaults/indexes,
  nullable `exploration.unclaimed_loot`, constraint names and enum ordering. Audit
  and backfill actual NULLs before adding `NOT NULL`; never stamp around these checks.
  If a difference is intentionally accepted, update the canonical baseline and
  both installation paths to agree, then repeat the comparisons.
- [x] Replay the final legacy graph into a new, empty PostgreSQL reference database.
  Use migration-owned seeds only; never freeze production player rows, passwords
  or administrator prompt edits. The SQL, baseline revision and manifest were
  regenerated together on 2026-11-13, including the tool's `MANIFEST` path and the
  frozen regression test IDs. The SQL excludes `alembic_version`, dump session
  settings and psql directives; the original `item_type IN (...)` check expression
  is retained. Bootstrap passwords stay generated at execution time. No mutable ORM
  metadata was used to build the baseline.
- [x] Generate the release manifest from that reference with the tool's `freeze`
  command. The 2026-11-13 manifest records `legacy_revision=4b3cbd7b15ff`,
  `baseline_revision=squash_4b3cbd7b15ff`, PostgreSQL 18 and the full schema state.
  A future release must regenerate the manifest and SQL together rather than
  overwriting this artifact.
- [ ] Test a fresh baseline install, offline SQL replay, legacy-to-baseline adoption,
  repeated adoption, unsupported-revision/schema rejection, and later migration
  upgrade/downgrade. Compare schema and all migration-owned seeds. Verify each
  production clone's row counts/content hashes before and after adoption, excluding
  only `alembic_version`. **Fresh install, schema/seed equality and the eight
  integration tests pass on 2026-11-13; the production-clone comparison remains.**
- [ ] Rehearse the full backup restore and rollback using the immutable release
  images and production-like clones. Run the full backend/frontend suites, enum
  drift guard and container smoke tests on the final runtime/dependency versions.
  The October rehearsal used Python 3.13/PostgreSQL 18 and is not evidence for the
  planned 3.0 Python/SQLAlchemy runtime.
- [x] Package both graphs, SQL and manifest in the release image, and point the
  deploy Job, init containers, worker/CLI paths, development tasks and docs at the
  baseline graph. The deploy migration Job now runs `baseline_tools prepare` before
  `alembic upgrade head`; adoption is gated on `maintenance_mode=true`.

Example manifest generation after replaying the final legacy head, from `backend/`:

```bash
POSTGRES_DB=baseline_release_reference ASYNC_DATABASE_URI= \
  uv run python -m app.alembic.baseline_tools freeze \
  --database baseline_release_reference --output /private/release-baseline.json
```

## Legacy graph status (frozen 2026-11-14)

Every maintained database is adopted: production at the v3.0.2 cutover and the local
development database on 2026-11-14. No entry point runs `alembic-legacy.ini`; the deploy
migration Job classifies the database with `baseline_tools prepare` and upgrades the
baseline graph. The legacy files are therefore reference/test-only:

- `alembic-legacy.ini` and `app/alembic/versions/` keep the historical replay used by
  `app/tests/test_alembic/*` and `scripts/build_alembic_baseline.py`.
- `baseline_tools` still accepts a database at `4b3cbd7b15ff` for one more release, so a
  restored v3.0.x dump can be adopted rather than upgraded.

Deletion checklist after the next release (target 3.2):

- [ ] Confirm no maintained database reports `4b3cbd7b15ff` from `prepare`/`check`.
- [ ] Delete `alembic-legacy.ini`, `app/alembic/versions/`, the generator, the `freeze`
      command, and the legacy replay tests in the same PR; shrink the image check.
- [ ] Keep the migration-on-test coverage that protects live behavior; retire only the
      historical replay, recording the coverage delta per the test-pruning policy.
- [ ] Release tags up to `v3.1.1` remain the recovery path for pre-squash dumps.

## Regenerating the artifacts

From the repository root, with a PostgreSQL server reachable through `backend/.env`
(and either `psql`/`pg_dump` on `PATH` or a running PostgreSQL container):

```bash
python3 scripts/build_alembic_baseline.py
```

The script drops and recreates the scratch database (`--database`, default
`fallout_baseline_ref`), replays the legacy graph, dumps the schema and the
objective/prompt seeds, and rewrites `baseline_<head>.sql`, the baseline revision,
`baseline_<head>.json`, the `MANIFEST` path and the regression-test constants. It
refuses a multi-head legacy graph, never touches another database, and does not
commit. `--keep` retains the scratch database; `--skip-migrations` reuses one that is
already at the legacy head. Objective IDs come from the legacy migrations' `uuid4()`
calls, so a regeneration changes them; the regression test compares seed content
without those IDs.

**Manifest scope.** `schema_state` covers columns, constraints, indexes and enum labels.
The current schema has no views, functions, triggers, policies or extensions. If one is
added, extend `schema_state` or adopt `alembic_utils` before regenerating; otherwise the
manifest will not detect drift in it.

## Regenerated artifacts (2026-11-13)

Reference: an empty PostgreSQL 18.6 database replayed through `4b3cbd7b15ff`.

| Artifact | Value |
| --- | --- |
| Legacy head | `4b3cbd7b15ff` |
| Baseline revision | `squash_4b3cbd7b15ff` |
| Schema | 46 application tables, 31 enums, 167 indexes |
| Seeds | 106 objective rows, 4 prompt rows, bootstrap admin/test user, demo vault and slot |
| Fresh install | `uv run alembic upgrade head` |
| Validation | normalized schema equal to the legacy replay; objective/prompt rows equal; bootstrap identity rows equal; 9 integration tests pass, including `alembic check` on the baseline graph |

The SQL retains the original `item_type IN (...)` check instead of pg_dump's
equivalent array cast, so replay stores the same expression as the legacy chain.

## Maintenance sequence for an existing database

Run these steps with the final rehearsed image, configs and manifest, in the
existing maintenance deployment flow. The shell examples assume the target's
normal host/user/password configuration is already injected and `POSTGRES_DB`
names the intended database. Clearing `ASYNC_DATABASE_URI` makes that name take
effect; retain a deliberately configured full URI instead if the environment
requires one, and verify its database agrees with `--database`.

1. Stop ingress writes, API replicas, workers, schedulers and other database
   writers; record replica counts. Create a verified full backup and retain its
   source revision and image digest. Confirm an isolated restore drill has passed.
2. With the explicit legacy config, upgrade the target to the frozen legacy head
   and run `current --check-heads`. Do not execute the baseline's `upgrade` on an
   existing database. Finish required backfills and validate their results.
3. Run `baseline_tools check --database "$POSTGRES_DB"`. Stop on any failure and
   keep writers stopped. The check does not reconcile drift or prove player-data
   backfill correctness. Capture before-adoption counts/hashes and schema evidence.
4. Adopt with `baseline_tools adopt --database "$POSTGRES_DB" --apply`. Run the
   check again and compare the evidence; only `alembic_version` may differ.
5. Run baseline `current --check-heads`, then deploy the rehearsed API/worker
   images with matching migration/init-container config. Restore the recorded
   replicas and ingress only after schema/version checks succeed. Smoke-test
   health, login, vault/dweller reads and critical player commands.
6. Record the database name, revision pair, image digest, backup location,
   comparison results and completion time. Retain the legacy graph while any
   maintained database or supported upgrade path still needs it.

The operator commands, once the preceding gates have passed:

```bash
uv run alembic -c alembic-legacy.ini upgrade head
uv run alembic -c alembic-legacy.ini current --check-heads
uv run python -m app.alembic.baseline_tools check --database "$POSTGRES_DB"
uv run python -m app.alembic.baseline_tools adopt --database "$POSTGRES_DB" --apply
uv run python -m app.alembic.baseline_tools check --database "$POSTGRES_DB"
uv run alembic current --check-heads
```

The deploy workflow performs the same sequence in its migration Job: `baseline_tools
prepare` classifies the database and, only under `maintenance_mode=true`, adopts the
legacy head; `alembic upgrade head` then runs against the baseline graph. A legacy
database without maintenance mode fails instead of stamping under live writers.

## Fresh installs and recovery

A new empty database uses `alembic upgrade head` (default `alembic.ini`), without
adoption. Future migrations descend from the baseline, not the legacy graph.
Both graphs remain packaged until upgrade support is intentionally retired.

If adoption fails before commit, the legacy marker is unchanged. Inspect the
failure with writers stopped. If only the marker changed successfully and no
subsequent schema/data changes occurred, restoring the recorded legacy marker
with `alembic -c alembic-legacy.ini stamp --purge LEGACY_REVISION` reverses that
marker operation; first revalidate the recorded schema. This does not undo the
legacy upgrades from step 2 or any 3.0 data changes.

After schema/data changes or resumed player writes, use the rehearsed recovery
procedure with a compatible schema and application image. A backup restore may
discard writes made after the backup; do not describe it as a lossless rollback.
The baseline rejects downgrade below itself, and `downgrade -1` is not the recovery
path for crossing the 3.0 boundary. Leave writers stopped until recovery is verified.
