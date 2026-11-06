# Aware-UTC migration preparation

Baseline: v2.287.1 (`d842b2c7`), Alembic `c8f2a1b3d4e5`, audited 2026-11-06.
This is a local schema inventory, conversion contract and cutover plan, with compatible-reader
follow-up recorded below. It adds no migration, keeps the naive-UTC storage/clock contract, and
does not claim a production-clone rehearsal.
The release gates remain in [the roadmap](../ROADMAP.md#30-platform-release-plan).

## Current schema

A fresh PostgreSQL 18 database upgraded through the existing revisions contains **122 timestamp
columns in 39 tables**, all `timestamp without time zone`. None has a SQL-side default; writers use
Python defaults or explicit values. `?` below means nullable. Recount on the actual clone before
writing the migration: this snapshot does not establish the quality of historical production data.

```sql
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND data_type LIKE 'timestamp%'
ORDER BY table_name, column_name;
```

| Table | Timestamp columns (`?` = nullable) |
| --- | --- |
| `account_merge` | `created_at` |
| `ai_settings` | `created_at?`, `updated_at?` |
| `arena_match_event` | `created_at?`, `updated_at?` |
| `arena_state` | `created_at?`, `fight_started_at?`, `last_fight_at?`, `updated_at?` |
| `broadcast` | `created_at`, `updated_at?` |
| `chatmessage` | `created_at` |
| `craftingorder` | `cancelled_at?`, `completed_at?`, `created_at?`, `estimated_completion_at`, `started_at`, `updated_at?` |
| `dweller` | `apprentice_started_at?`, `birth_date?`, `created_at?`, `death_timestamp?`, `deleted_at?`, `departed_at?`, `departure_eligible_at?`, `despair_since?`, `exit_requested_at?`, `updated_at?` |
| `dwellerlocation` | `created_at?`, `updated_at?` |
| `expeditionrun` | `created_at?`, `finished_at?`, `updated_at?` |
| `exploration` | `created_at?`, `end_time?`, `paused_at?`, `position_as_of?`, `return_completes_at?`, `return_started_at?`, `start_time`, `updated_at?` |
| `gamestate` | `created_at?`, `daily_objectives_period?`, `last_activity_time`, `last_presence_at?`, `last_tick_time`, `paused_at?`, `resumed_at?`, `updated_at?`, `water_empty_since?`, `weekly_objectives_period?` |
| `incident` | `created_at?`, `end_time?`, `start_time`, `updated_at?` |
| `incident_event` | `created_at?`, `updated_at?` |
| `incident_participant` | `created_at?`, `updated_at?` |
| `junk` | `created_at?`, `updated_at?` |
| `llminteraction` | `created_at?` |
| `notification` | `created_at`, `read_at?` |
| `oauth_account` | `created_at?`, `updated_at?` |
| `outfit` | `created_at?`, `updated_at?` |
| `pet` | `created_at?`, `updated_at?` |
| `pregnancy` | `conceived_at`, `created_at?`, `due_at`, `updated_at?` |
| `quest` | `created_at?`, `updated_at?` |
| `relationship` | `created_at?`, `updated_at?` |
| `room` | `created_at?`, `last_rush_at?`, `updated_at?` |
| `team` | `created_at?`, `updated_at?` |
| `team_member` | `created_at?`, `updated_at?` |
| `training` | `completed_at?`, `created_at?`, `estimated_completion_at`, `started_at`, `updated_at?` |
| `user` | `created_at?`, `deleted_at?`, `email_changed_at?`, `password_reset_expires?`, `updated_at?`, `username_changed_at?` |
| `userprofile` | `created_at?`, `updated_at?` |
| `vault` | `arena_morale_awarded_at?`, `created_at?`, `deleted_at?`, `last_exit_request_at?`, `updated_at?` |
| `vault_recipe_unlock` | `unlocked_at?` |
| `vault_theme` | `crafted_at?` |
| `vaultlocationstate` | `cleared_at?`, `created_at?`, `reclear_available_at?`, `updated_at?` |
| `vaultquestcompletionlink` | `completed_at?`, `return_completes_at?`, `return_started_at?`, `started_at?` |
| `vaultslot` | `created_at?`, `updated_at?` |
| `weapon` | `created_at?`, `last_maintenance_trial_at?`, `updated_at?` |
| `worldlocation` | `created_at?`, `updated_at?` |
| `worldsnapshot` | `created_at?`, `updated_at?` |

`birth_date` is a game-clock instant used for accelerated age calculations, not a calendar-only
SQL `date`. Preserve it as a timestamp. Preserve existing NULLs; do not fill missing history with
migration time or another legal-looking default.

## Runtime, JSON and API boundaries

Paths in this section are relative to the repository root.

| Boundary | Current evidence | Required cutover work |
| --- | --- | --- |
| ORM clocks | `backend/app/models/base.py` uses `datetime.utcnow()` for creation/update/deletion. Other models and CRUD/services also use naive UTC, including `datetime.now(UTC).replace(tzinfo=None)`. | Move persisted datetime fields and their defaults/onupdate hooks to aware UTC together with SQLModel/SQLAlchemy types. Keep the API and worker engines in `backend/app/db/session.py` pinned to UTC. |
| Deadlines and elapsed time | `models/{exploration,training,crafting_order,pregnancy,incident,vault_quest,game_state}.py` compare stored dates with naive current time. CRUD queries use matching naive bounds. | Audit both Python and SQL operands: completion thresholds, returns, pause/resume, offline ticks, breeding/cooldowns, age/death, retention and room/weapon cooldowns. Replacing defaults alone leaves mixed arithmetic. |
| Offset stripping | `Pregnancy.is_due` drops tzinfo without first converting an aware value to UTC; `services/combat/arena_service.py` relabels event dates with `replace(tzinfo=UTC)`. | Review each occurrence for its input contract. Convert an aware instant with `astimezone(UTC)`; only label a naive value UTC when the legacy contract establishes UTC. |
| Exploration JSON | `models/exploration.py` emits bare ISO strings in `events[].timestamp` and `loot_collected[].found_at`. `services/exploration_service.py` and `exploration/expedition_scenario_service.py` write `trail[].t` and scenario event timestamps. | Keep historical payload text intact for this cutover; make readers accept legacy naive UTC and explicit offsets before new writers emit aware values. `exploration/event_generator.py` accepts legacy naive UTC and normalizes aware event timestamps to naive UTC for its current clock comparison without modifying history. Preserve that compatibility during the coordinated clock cutover. |
| Other JSON and delivery | `dweller.bio_entries[].created_at` comes from `services/bio_service.py`; notification metadata is extensible JSON. `game_loop_service.py` derives delivery `event_id` text from `last_tick_time`; `gamestate.recent_tick_ids` stores opaque identifiers. | Inventory real metadata keys on the clone. Do not blanket-rewrite JSON strings, user text, event IDs or deduplication keys. Preserve replay/reconnect identity and normalize only known temporal fields when reading them. |
| Canonical API output | `schemas/training.py` uses `utils/serialize.py` to emit UTC `Z` strings for naive and aware inputs, including nullable completion. | Preserve this contract. The new schema round-trip tests cover naive UTC, UTC, positive/fractional and negative offsets, and present/absent completion values. |
| Other API output | Exploration and broadcast schemas rely on ordinary datetime serialization. Game-control, quest-member, incident and notification delivery paths also call `isoformat()` directly. `system/info` already emits an aware value. | Specify which outputs become UTC `Z` or explicit `+00:00`; preserve instants, optional values and consumers of old cached payloads. Regenerate frontend API types when the API changes, even if datetime still maps to string. |
| Browser parsing | `frontend/src/core/utils/time.ts:parseUtcMs` and radio parsing accept naive UTC and explicit offsets. Training consumes its already-normalized API output. `CraftingPanel.vue` now reuses `parseUtcMs` for both progress endpoints and its countdown; some other views still use `new Date(value)` directly. | Land compatible readers first: avoid double suffixes and local-time interpretation. Reuse `parseUtcMs`; cover old and new strings, offsets, phone/browser timezone differences and reload. Crafting regressions cover legacy/aware strings, live progress and reload; the wider browser-reader audit remains open. |
| Calendar periods and credentials | `services/progression/objectives/refresh_service.py` computes UTC daily/weekly boundaries. JWT helpers turn datetime expirations into numeric claims; Redis uses TTL/opaque keys as well as date-based caches. | Retain UTC day/week/reset semantics. Do not reinterpret epoch numbers, elapsed durations, TTLs or opaque IDs as naive datetime strings. Review password-reset DB deadlines with the rest of `user`. |

This is a source audit, not proof that every historic JSON payload has the same shape. On the clone,
sample known event/loot/trail/bio fields and notification payload producers by version. Malformed,
unknown or explicitly offset values need an explicit policy; never infer a timezone from a plausible
wall clock. Correct any demonstrably non-UTC legacy cohorts in a separate, identified data repair.

## Conversion contract

Legacy typed values follow the documented naive-UTC contract. The proposed conversion explicitly
interprets those values as UTC, independently of the migration connection's timezone:

```sql
ALTER TABLE <table>
  ALTER COLUMN <column> TYPE timestamptz
  USING <column> AT TIME ZONE 'UTC';
```

A plain type cast interprets naive values using the session timezone and can shift their instants.
PostgreSQL stores `timestamptz` as instants; it does not retain the original timezone name. See the
[PostgreSQL datetime types](https://www.postgresql.org/docs/18/datatype-datetime.html) and
[AT TIME ZONE semantics](https://www.postgresql.org/docs/18/functions-datetime.html#FUNCTIONS-DATETIME-ZONECONVERT).
Use explicit UTC in the DDL even when the engine is already UTC-pinned. In the eventual revision,
group column alterations by table, preserve nullability and constraints, and audit dependent indexes,
views, triggers and any newly introduced defaults. Measure lock/rewrite behavior on the clone rather
than assuming the operation is cheap. SQLAlchemy model declarations must use timezone-capable types;
see [DateTime](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.DateTime).

The inverse expression for the typed value is `USING <column> AT TIME ZONE 'UTC'` when converting
`timestamptz` back to `timestamp`. The test proves that expression for sample old and new aware writes;
it does not prove that an old application can consume all state written by a new release.

## Executable evidence

`backend/app/tests/test_db/test_utc_migration_contract.py` creates only a connection-local temporary
table, reusing the existing `explorationstatus` enum without changing it. It covers:

- Schema timestamp inventory versus SQLModel metadata on a migrated database.
- Explicit UTC conversion across UTC, Kyiv, New York and Chatham session timezones, winter and DST
  transition dates, leap day and microsecond precision; nullable values, enum values and JSON unchanged.
- A negative control showing the incorrect implicit-cast result in a non-UTC session.
- SQL deadlines one microsecond before, exactly at and after the cutoff, before and after conversion.
- A late duplicate-key failure after DDL, followed by savepoint rollback and reloaded original rows/types.
- The inverse expression after writing a non-UTC-offset aware value.
- Actual `TrainingRead` JSON serialization/deserialization with legacy and aware input dates.

Use a disposable, migrated PostgreSQL database. From `backend/`:

```bash
# Point only at the disposable database, using its actual port/credentials.
export ASYNC_DATABASE_URI='postgresql+asyncpg://postgres:<password>@127.0.0.1:<port>/fallout_utc_preparation'
uv run alembic upgrade head
UTC_MIGRATION_REQUIRE_POSTGRES=1 uv run pytest app/tests/test_db/test_utc_migration_contract.py -n 0 -ra
```

CI requires PostgreSQL for these cases on both Python 3.13 and 3.14; an unavailable or non-PostgreSQL
connection fails rather than silently skipping. Ordinary local runs can skip the integration cases
when PostgreSQL is unavailable; the API-schema round-trip cases still run. Temporary tables are
transaction-scoped and connection-local, so parallel test workers do not share rehearsal rows.

These are SQL conversion and API contracts against the current pinned dependencies, not tests of an
Alembic revision that has not been written. When the real revision exists, invoke that revision in the
migration regressions and exercise real domain rows, API/worker deadlines and JSON readers under the
new ORM versions. Do not remove this distinction from the release evidence.

## Compatible-reader follow-up

The first reader slice fixes crafting progress and exploration event intervals while keeping writers,
API output and storage unchanged. Crafting progress now shares `parseUtcMs` with its countdown.
Exploration converts explicit offsets to UTC before removing tzinfo for the existing naive-UTC clock;
it leaves legacy naive values and the event/loot/trail JSON, unknown fields and identity strings intact.
Malformed event timestamps continue to fail at the existing parse boundary.

Regressions cover legacy naive UTC, `Z`, positive fractional-hour and negative offsets; exploration
checks one microsecond before, at and after the event interval. Crafting checks progress/countdown
agreement while time advances and after remount. Shared parser cases cover fractional seconds and
elapsed countdown clamping. Run frontend cases under different process timezones to detect accidental
local-time interpretation:

```bash
cd frontend
TZ=America/New_York pnpm run test:run tests/unit/core/utils/time.test.ts tests/unit/components/crafting/CraftingPanel.test.ts
TZ=Asia/Kathmandu pnpm run test:run tests/unit/core/utils/time.test.ts tests/unit/components/crafting/CraftingPanel.test.ts
```

The adjacent training deadline readers use ordinary `Date` parsing against the existing canonical
`Z` output described above. Exploration countdowns already reuse the shared time helpers; Arena journal
readers also use `parseUtcMs`. This slice does not complete the wider audit: generic date formatting,
notification absolute-time tooltips, home ordering and chat history still include direct `Date` parsing.
Notification reconnect/deduplication behavior, real browser/phone displays and production JSON sampling
remain separate validation work before cutover. No subscription or delivery owner changes here.

## Ordered implementation and cutover

1. Finish the roadmap's gameplay gates before the runtime/database cutover. Compatibility tests and
   this preparation can run earlier. Reconfirm dependency GA/support and test the chosen SQLModel /
   SQLAlchemy versions separately; the current bounds stay in place here.
2. Land browser and serialized-history reader compatibility while output/storage remain unchanged.
   Test old bare-UTC and new offset-aware values, unknown JSON fields, notification reconnects and
   cache/played/deduplication identity. Keep one canonical UTC policy; extend existing utilities.
3. Implement the coordinated ORM/clock/CRUD/API change and an append-only Alembic revision with the
   explicit conversion above. Name Alembic's transaction as the DDL owner; helpers must not commit.
   Include bounded lock/statement timeouts based on clone measurements. Do not roll old naive-clock
   workers together with aware-clock workers against the converted schema.
4. Restore a production dump into isolated infrastructure using
   [`scripts/restore-drill.sh`](../../scripts/restore-drill.sh). Verify old revision/image readiness,
   record archive hash/size and image digests. Use `--keep` for a staged drill so the script retains
   its scratch containers/network; run the exact candidate image's migration only against that clone,
   then explicitly remove the retained infrastructure after verification.
   A fresh schema is useful but does not replace this data-bearing rehearsal. Record NULL counts,
   non-NULL UTC instants/checksums by primary key, enum labels, row counts, indexes and JSON samples.
5. Exercise paused and active explorations, nullable completion, training/crafting/quest boundaries,
   breeding/cooldowns, age/death, objective period rollover and API/worker sessions. Verify clocks are
   aware end to end, API dates preserve instants and the selected enum/schema drift checks pass.
   Inject late migration failure on the clone and verify the old schema/data can still start on the v2
   image. Also rehearse recovery after a committed schema change, not just savepoint rollback.
6. Regenerate the Alembic fresh-install baseline only after the final schema settles. Preserve an
   upgrade bridge from the deployed v2 revision and compare fresh-install and upgraded-clone schemas.
   A baseline stamp alone does not establish that legacy rows were converted.
7. For production, select and record the actual last-verified v2 image/digests at the window. Use
   `maintenance_mode=true` in the existing deployment workflow: stop API and worker/scheduler writers,
   verify no other Jobs/CLI/cron writers are active, and create the verified pre-migration dump after
   quiescence. Keep writers stopped if migration or verification fails. See
   [deployment and recovery](../DEPLOYMENT.md#backup--restore) for the current workflow and restore drill.
8. Migrate, validate revision/schema/instants, start the matching new API and worker, then check readiness,
   real gameplay deadlines and desktop/phone date displays before reopening play. Release notes need
   the reviewed breaking-change declaration; Semantic Release owns the version.

## Recovery boundaries

- **Before commit:** failed DDL must roll back in the migration transaction. The temporary-table test
  verifies a savepoint analogue, not a production outage/recovery drill. Verify revision and schema
  before starting the pinned old writers.
- **After commit, before reopening:** stop every writer and restore the quiesced snapshot with the
  matching v2 image, configuration and revision. Rehearse the restore/readiness path on the clone.
  Do not treat application-image rollback or the inverse column expression as sufficient recovery
  for ORM, JSON and baseline changes.
- **After new player progress:** restoring the old snapshot discards post-window activity. Keep a
  post-failure backup, quantify/reconcile the affected work, and require an explicit recovery decision;
  never promise automatic lossless rollback. Old event payloads and identity keys remain intact so
  recovery does not depend on an unreviewed JSON rewrite.

No maintenance window, production backup/restore, ORM upgrade or timestamp migration is performed by
this preparation. Keep the rehearsal results and remaining gates attached to the eventual cutover PR.
