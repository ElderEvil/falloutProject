# B6 aware-UTC restore rehearsal

Date: 2026-11-09
Environment: local Podman, PostgreSQL 18, SQLAlchemy 2.1.8, SQLModel 0.0.48.

This is a **local, data-bearing rehearsal**, not a production dump. It exercises the
pre-B4 snapshot -> restore -> B4 conversion -> API readiness -> tick -> downgrade path.

## Input artifact

- Dump: `/tmp/opencode/b6-pre-b4.dump` (1,704,003 bytes)
- SHA-256: `2c3fbdfeae47782ff17176c9241ad2f3c55a82c921b31279dbd4ed9c3e72c86e`
- Archive entries: 440
- Revision: `f9e8d7c6b5a4` (pre-B4)

The dump was produced by restoring the local B4 database into an isolated source
database, downgrading to `f9e8d7c6b5a4`, and dumping the result.

## Restore drill

`scripts/restore-drill.sh --dump /tmp/opencode/b6-pre-b4.dump --expected-revision f9e8d7c6b5a4 --keep`

- Archive verification: ok
- Scratch restore: ok
- Tables: 47
- Vaults: 63
- Users: 36
- Dwellers: 1,386
- Result: PASS

## B4 conversion

`alembic upgrade head` on the restored clone:

- `f9e8d7c6b5a4` -> `4b3cbd7b15ff`: **1.65s**
- Timestamp columns: 122 `timestamp without time zone` -> **122 `timestamptz`**
- Row counts unchanged: vaults 63, users 36, dwellers 1,386
- Sample instant preserved:
  - before: `2026-09-14 09:43:05.834044` (`timestamp without time zone`)
  - after: `2026-09-14 09:43:05.834044+00` (`timestamp with time zone`)

## Application readiness and tick

- Readiness: HTTP 200, `status=ready`, PostgreSQL healthy, Redis healthy, database `fallout_restore`
- One live vault tick: **0.39s**
- Tick phases/updates: `apprenticeships`, `arena`, `breeding`, `crafting`, `dweller_snapshot`,
  `dwellers`, `events`, `explorations`, `happiness`, `radio`, `resources`, `storage`, `training`

## Rollback

- `alembic downgrade f9e8d7c6b5a4`: **1.66s**
- Timestamp columns: 122 `timestamp without time zone`
- `alembic upgrade head` again: **1.64s**
- Timestamp columns: 122 `timestamptz`

## Limitations

- The input is a local data-bearing database, not a production snapshot.
- The pinned v2 image rollback, public traffic gate and k3s datastore were not exercised.
  Those require the production dump, the last verified v2 image, and the deployment workflow.
- Timings are local hardware measurements. Re-measure on the production clone before finalizing
  the migration `lock_timeout`/`statement_timeout` values.
