# Migration baseline for 3.0

**Status: machinery ready for review; production cutover scheduled for 3.0.**
Shipping these files does not stamp any database, change the default migration
graph, or alter deployment/startup commands. No version is bumped manually.

The [October experiment](MIGRATION_SQUASH_EXPERIMENT.md) proved a baseline through
`b7e3d9c1a5f2`, with revision `squash_b7e3d9c1a5f2`. Those IDs are prototype
artifacts. **Regenerate and rehearse them at the final schema boundary for 3.0**,
including the planned timestamp/UUID/enum changes, before using this process on
maintained databases. A maintained database newer than the pinned legacy head is
rejected; the tool never guesses that it is compatible.

## Machinery shipping ahead of the cutover

| Artifact | Purpose |
|---|---|
| `backend/alembic.ini` and `app/alembic/versions/` | Unchanged default legacy graph, including historical backfills and regression tests |
| `backend/alembic-squash.ini` | Opt-in graph with one frozen baseline |
| `app/alembic/baseline_versions/*.sql` | Frozen schema and migration-owned content from a clean legacy replay |
| `app/alembic/baseline_versions/*.json` | Reviewed schema manifest, PostgreSQL major and exact revision pair |
| `app/alembic/baseline_tools.py` | Operator-only check, freeze and transactional adoption commands |

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

- [ ] Identify and record the final legacy head, baseline revision, source commit,
  immutable backend image digest, PostgreSQL major and supported upgrade sources.
  Complete all schema changes required by 3.0 in the legacy graph first; resolve
  multiple heads before freezing. The baseline and that legacy head must represent
  the same schema and migration-owned seed state.
- [ ] Inventory every maintained database's revision and custom database objects.
  Reconcile drift through reviewed, data-safe migrations or an explicitly documented
  operational procedure. The October differences include missing defaults/indexes,
  nullable `exploration.unclaimed_loot`, constraint names and enum ordering. Audit
  and backfill actual NULLs before adding `NOT NULL`; never stamp around these checks.
  If a difference is intentionally accepted, update the canonical baseline and
  both installation paths to agree, then repeat the comparisons.
- [ ] Replay the final legacy graph into a new, empty PostgreSQL reference database.
  Use migration-owned seeds only; never freeze production player rows, passwords
  or administrator prompt edits. Regenerate the SQL, baseline revision and manifest
  together, including the tool's `MANIFEST` path and the frozen regression test IDs.
  The SQL must exclude `alembic_version`, dump session settings and psql directives;
  preserve the tested check-expression handling. Bootstrap passwords stay generated
  at execution time. Do not read mutable ORM metadata to build a historical baseline.
- [ ] Generate the release manifest from that reference with the tool's `freeze`
  command. Its output path must not already exist. Review the artifact diff rather
  than overwriting a previously released baseline. This command freezes the manifest,
  not the schema SQL; both artifacts must be regenerated and tested together.
- [ ] Test a fresh baseline install, offline SQL replay, legacy-to-baseline adoption,
  repeated adoption, unsupported-revision/schema rejection, and later migration
  upgrade/downgrade. Compare schema and all migration-owned seeds. Verify each
  production clone's row counts/content hashes before and after adoption, excluding
  only `alembic_version`.
- [ ] Rehearse the full backup restore and rollback using the immutable release
  images and production-like clones. Run the full backend/frontend suites, enum
  drift guard and container smoke tests on the final runtime/dependency versions.
  The October rehearsal used Python 3.13/PostgreSQL 18 and is not evidence for the
  planned 3.0 Python/SQLAlchemy runtime.
- [ ] Package both graphs, SQL and manifest in the release image. Update the deploy
  Job, API init container, worker/CLI migration paths, development tasks and docs
  together so every post-cutover entry point uses the baseline graph. The current
  default remains legacy until that release change is reviewed.

Example manifest generation after replaying the final legacy head, from `backend/`:

```bash
POSTGRES_DB=baseline_release_reference ASYNC_DATABASE_URI= \
  uv run python -m app.alembic.baseline_tools freeze \
  --database baseline_release_reference --output /private/release-baseline.json
```

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
uv run alembic -c alembic.ini upgrade head
uv run alembic -c alembic.ini current --check-heads
uv run python -m app.alembic.baseline_tools check --database "$POSTGRES_DB"
uv run python -m app.alembic.baseline_tools adopt --database "$POSTGRES_DB" --apply
uv run python -m app.alembic.baseline_tools check --database "$POSTGRES_DB"
uv run alembic -c alembic-squash.ini current --check-heads
```

These commands refer to the current explicit config names. If the release promotes
the baseline to `alembic.ini`, retain an explicit legacy config and update the
sequence and all entry points in the same release PR. Do not run the current
deployment workflow unchanged: it assumes one graph and cannot cross this boundary.

## Fresh installs and recovery

A new empty database uses `alembic -c alembic-squash.ini upgrade head`, without
adoption. Future migrations descend from the baseline, not the archived graph.
Both graphs remain packaged until upgrade support is intentionally retired.

If adoption fails before commit, the legacy marker is unchanged. Inspect the
failure with writers stopped. If only the marker changed successfully and no
subsequent schema/data changes occurred, restoring the recorded legacy marker
with `alembic -c alembic.ini stamp --purge LEGACY_REVISION` reverses that marker
operation; first revalidate the recorded schema. This does not undo the legacy
upgrades from step 2 or any 3.0 data changes.

After schema/data changes or resumed player writes, use the rehearsed recovery
procedure with a compatible schema and application image. A backup restore may
discard writes made after the backup; do not describe it as a lossless rollback.
The baseline rejects downgrade below itself, and `downgrade -1` is not the recovery
path for crossing the 3.0 boundary. Leave writers stopped until recovery is verified.
