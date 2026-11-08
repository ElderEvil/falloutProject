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
| ORM clocks | `backend/app/models/base.py` uses `app.utils.time.utcnow()` for creation/update/deletion. All naive-UTC producers go through `app/utils/time.py` (`utcnow`, `as_utc`, `as_naive_utc`); direct `datetime.utcnow` and naive `.replace(tzinfo=None)` are banned by `tests/test_architecture/test_clock_perimeter_guard.py`. | Move persisted datetime fields and their defaults/onupdate hooks to aware UTC together with SQLModel/SQLAlchemy types. Keep the API and worker engines in `backend/app/db/session.py` pinned to UTC. |
| Deadlines and elapsed time | `models/{exploration,training,crafting_order,pregnancy,incident,vault_quest,game_state}.py` compare stored dates with naive current time. CRUD queries use matching naive bounds. | Audit both Python and SQL operands: completion thresholds, returns, pause/resume, offline ticks, breeding/cooldowns, age/death, retention and room/weapon cooldowns. Replacing defaults alone leaves mixed arithmetic. |
| Offset stripping | `Pregnancy.is_due` and arena event snapshots normalize through `app.utils.time.as_utc()`; offset stripping outside `app/utils/time.py` is guarded. | Review each occurrence for its input contract. Convert an aware instant with `astimezone(UTC)`; only label a naive value UTC when the legacy contract establishes UTC. |
| Exploration JSON | `models/exploration.py` emits bare ISO strings in `events[].timestamp` and `loot_collected[].found_at`. `services/exploration_service.py` and `exploration/expedition_scenario_service.py` write `trail[].t` and scenario event timestamps. | **Decision: stored JSON stays bare naive UTC.** Keep historical text byte-stable; new writers keep the bare format via `serialize_naive_utc_datetime`; readers accept bare and explicit offsets. `exploration/event_generator.py` normalizes parsed history with `as_utc` for its clock comparison, so legacy naive text and an aware clock compare safely; stored text stays untouched. |
| Other JSON and delivery | `dweller.bio_entries[].created_at` comes from `services/bio_service.py`; notification metadata is extensible JSON. `game_loop_service.py` derives delivery `event_id` text from `last_tick_time`; `gamestate.recent_tick_ids` stores opaque identifiers. | **Decision: stored JSON stays bare naive UTC; identity stays byte-stable.** `bio_entries[].created_at`, notification metadata `created_at`, `event_id` and `recent_tick_ids` keep their current bare/opaque form. Do not rewrite history or recompute identity from aware values. |
| Canonical API output | `schemas/training.py` uses `utils/serialize.py` to emit UTC `Z` strings for naive and aware inputs, including nullable completion. | **Decision: every API datetime field emits UTC `Z`.** Training is the reference; add the same field serializers to the remaining schemas. The round-trip tests cover naive UTC, UTC, positive/fractional and negative offsets, and present/absent values. |
| Other API output | Exploration and broadcast schemas rely on ordinary datetime serialization. Game-control, quest-member, incident and notification delivery paths also call `isoformat()` directly. `system/info` already emits an aware value. | **Decision: no bare or `+00:00` API output.** Route every datetime field through `serialize_utc_datetime`/`serialize_optional_utc_datetime` (including `system/info.build_date`, which changes from `+00:00` to `Z`). Regenerate frontend types when the API changes. |
| Browser parsing | `frontend/src/core/utils/time.ts:parseUtcMs` and radio parsing accept naive UTC and explicit offsets. Training consumes its already-normalized API output. `CraftingPanel.vue` now reuses `parseUtcMs` for both progress endpoints and its countdown; some other views still use `new Date(value)` directly. | Land compatible readers first: avoid double suffixes and local-time interpretation. Reuse `parseUtcMs`; cover old and new strings, offsets, phone/browser timezone differences and reload. Crafting regressions cover legacy/aware strings, live progress and reload; the wider browser-reader audit remains open. |
| Calendar periods and credentials | `services/progression/objectives/refresh_service.py` computes UTC daily/weekly boundaries. JWT helpers turn datetime expirations into numeric claims; Redis uses TTL/opaque keys as well as date-based caches. | **Decision: calendar keys and credentials are not instants.** Keep UTC day/week/reset semantics, numeric JWT `exp`, `%Y-%m` month keys and TTLs unchanged; do not convert them to datetime strings. Review password-reset DB deadlines with the rest of `user`. |

This is a source audit, not proof that every historic JSON payload has the same shape. On the clone,
sample known event/loot/trail/bio fields and notification payload producers by version. Malformed,
unknown or explicitly offset values need an explicit policy; never infer a timezone from a plausible
wall clock. Correct any demonstrably non-UTC legacy cohorts in a separate, identified data repair.

## Comparison and query-bound inventory

Audited 2026-11-08 at `2bf102dc`. **Snapshot, not proof of completeness**: re-run the inventory on the
cutover commit. This is the per-site checklist B4 executes and does not change runtime behaviour. The
producer side is automated (`app/utils/time.py`, guarded by
`tests/test_architecture/test_clock_perimeter_guard.py`); the consumer inventory below is grep-derived and
must be revalidated, not assumed exhaustive. Every entry is one of:

- **C** — Python consumer: compares or subtracts a stored datetime and the clock.
- **Q** — SQL bound: a datetime parameter passed into a `WHERE`/`UPDATE`.
- **J** — serialized boundary: JSON payload, SSE frame, or identity/dedup string.
- **A** — API output.

Today every stored value and every clock read is naive UTC, so C and Q are naive-vs-naive. B4 changes the
columns to `timestamptz`; the DB then returns aware values and an aware clock can meet them. Never leave a
mixed pair.

### C — model deadline and elapsed-time properties

| Site | Today | B4 action |
| --- | --- | --- |
| `Exploration.elapsed_time_seconds`, `time_remaining_seconds`, `return_time_remaining_seconds`, `should_generate_event` | stored fields minus `utcnow()` | both operands aware; keep `as_utc` only for legacy/SQLite input |
| `Training.time_remaining_seconds`, `is_ready_to_complete` | `estimated_completion_at` vs clock | both aware |
| `CraftingOrder.time_remaining_seconds` | `estimated_completion_at` vs clock | both aware |
| `VaultQuestCompletionLink.return_time_remaining_seconds`, `start_return` | `return_completes_at` vs clock | both aware |
| `Incident.elapsed_time`, `should_spread` | `start_time` vs clock | both aware |
| `GameState.calculate_offline_time`, `is_user_online`, `pause`, `resume`, `update_tick` | `paused_since`, `resumed_at` vs clock | one clock; both aware |
| `Pregnancy.is_due`, `progress_percentage`, `time_remaining_seconds` | already normalized with `as_utc` | reference implementation; keep |
| `WorldLocation.is_cleared`, `time_remaining_seconds`, `is_dispatchable` | `now` parameter from caller | caller passes `utcnow()`; both aware |
| age helpers in `app/utils/dwellers.py` and `app/options/races.py` | `as_naive_utc` on both sides | keep; finalize awareness after the `UTCDateTime` decision below |
| `Weapon.last_maintenance_trial_at` shifts (`crud/weapon.shift_trial_clocks`) | `min(stored + paused, now)` | both operands same type |

### Q — SQL query bounds

| Site | Bound | B4 action |
| --- | --- | --- |
| `Pregnancy.get_unavailable_mother_ids` | `updated_at >= utcnow() - cooldown` | aware UTC parameter |
| `Pregnancy.get_due_by_vault` | `due_at <= utcnow()` | aware UTC parameter |
| `ExpeditionRun.get_recent_terminal` | `finished_at >= since` (anti-farm `utcnow() - 7d`) | aware UTC parameter |
| `LLMInteraction.total_tokens_since`, `aggregate_tokens`, `aggregate_by_operation` | `created_at >= since` (month start) | aware UTC month start |
| `Incident.get_resolved_before` | `end_time <= cutoff` | aware UTC cutoff |
| `Dweller.get_aging_youth` | `birth_date <= born_before` | aware UTC threshold |
| `Dweller.get_permanently_dead_before` | `death_timestamp <= cutoff` | aware UTC cutoff |
| `Dweller.get_soft_deleted_before`, `count_soft_deleted`, pool eligibility | `deleted_at` / pool clock | aware UTC parameter |
| `Notification.get_expired_batch` | `created_at <= read/unread cutoff` | aware UTC cutoffs |
| `QuestCRUD.get_expired_party_links` | `expires_at <= now` | aware UTC parameter |
| `QuestCRUD.get_arrived_party_links` | `return_completes_at <= now` | aware UTC parameter |
| `WorldLocation.get_elapsed_reclears` | `reclear_available_at <= now` + Python recheck after lock | aware UTC parameter |
| `Broadcast.get_today_broadcast`, `count_trigger_on_date`, `get_audio_keys_before` | `created_at` day range / `< before` | aware UTC bounds |
| `Weapon.list_due_for_trial` | `last_maintenance_trial_at <= cutoff` | aware UTC cutoff |
| `utils/dweller_lifecycle` eligibility | `departure_eligible_at <= now` | aware UTC parameter |

A bound must match the column type. After B4 the column is `timestamptz`, so pass aware UTC. Before B4 the
column is naive, so pass naive UTC. PostgreSQL casts a mismatched parameter through the session timezone;
the contract test must keep proving the conversion under a non-UTC session.

### C — service, tick and background comparisons

| Area | Sites | B4 action |
| --- | --- | --- |
| Exploration return | `exploration/expedition.py` (`return_completes_at <= utcnow()`) | both aware |
| Spatial movement | `exploration_service._settle_movement`, `_advance_return`, `_forward_position`, `resume_from_encounter`, `advance`, `pause_for_encounter` (`now`, `position_as_of`, `start_time`) | one clock; both aware |
| Quests | `progression/quests/service.py` (`started_at + duration`, `return_completes_at`) | both aware |
| Incidents | `combat/incident_round.py`, `incident_service.py`, `incident_spawning.py`, `incident_tick.py` (`start_time`, presence window) | both aware |
| Arena | `combat/arena_service.py` (`fight_started_at`, `arena_morale_awarded_at`) | both aware |
| Dweller ticks | `game_tick/dwellers_tick.py` (`water_empty_since`, `apprentice_started_at`, exploration deadlines) | both aware |
| Storage tick | `game_tick/storage_tick.py` (`now - latest` maintenance cooldown) | both aware |
| Game loop | `game_loop_service.py` (`resumed_at > paused_since`, tick windows), `resource_manager_service.py` tick/activity arithmetic | one clock; both aware |
| Crafting / training | `crafting_service.py`, `training_service.py` (`estimated_completion_at`) | both aware |
| Room rush | `room_rush_service.py` (`last_rush_at`, rush deadline, `_effective_stacks`) | both aware |
| Exit requests | `exit_request_service.py` (`despair_since` grace, daily cap, `last_exit_request_at`) | both aware |
| Departures | `departure_pool_service.py` (`departure_eligible_at`) | both aware |
| Age / lifecycle | `dweller_service.py`, `family/breeding_service.py`, `family/death_service.py`, `utils/dwellers.py` | aware thresholds |
| Scenarios / CLI | `family/apprentice_scenario_service.py`, `family/family_scenario_service.py`, `cli/family_scenario.py`, `cli/simulate_exploration.py` | one clock |
| Map | `map/discovery.py` (`get_elapsed_reclears(utcnow())`), `map/reads.py` | aware UTC |
| Objectives | `progression/objectives/refresh_service.objective_periods` (returns naive midnights), `guidance.py` | **Decision: return aware UTC midnights** at B4; keep UTC day/week semantics and update callers that compare with stored periods |
| Quota / usage | `quota_service.py` month start, `ai_usage_service.py` month string | month boundary is a UTC date, not an instant; keep semantics |
| Users | `user_service.py` cooldown, `auth_service.py` password reset expiry | both aware; password reset already `as_utc` |
| Broadcast | `broadcast_service.py` day bounds and date seed | UTC date semantics; seed format must stay stable |
| Cleanup / retention | `cleanup_service.py`, `dweller_recycling_service.py` | aware UTC cutoffs |

### J / A — serialized and identity boundaries

These decisions are the contract; do not re-open them per site during B4.

| Boundary | Current behaviour | Decision |
| --- | --- | --- |
| Exploration JSON (stored) | `events[].timestamp`, `loot_collected[].found_at` via `serialize_naive_utc_datetime`; `trail[].t` via the helper in `expedition_scenario_service.py` and raw `isoformat()` in `exploration_service.py` | **Bare naive UTC, forever.** Never rewrite stored text; new writers use `serialize_naive_utc_datetime`, including the `exploration_service` trail. |
| Exploration JSON reader | `event_generator.py` parses `events[].timestamp` and normalizes via `as_utc` | **Accept bare and explicit offsets.** Never modify stored text. |
| Bio entries | `bio_entries[].created_at` legacy naive | **Bare naive UTC** (stored JSON policy). |
| SSE: exploration | `coordinator.py` return deadlines | **UTC `Z`** via `serialize_utc_datetime`. |
| SSE: incidents | `incident_service.py` start/end `isoformat()` | **UTC `Z`**; optional values stay `null`. |
| SSE: arena | `arena_service._event_snapshot` emits `+00:00` | **UTC `Z`** (changes from `+00:00`). |
| SSE: exploration members | `exploration_service.py` created/updated `isoformat()` | **UTC `Z`**. |
| Notification metadata | `notification_service.py` `created_at.isoformat()` | **Bare naive UTC** in stored metadata; API `notification.created_at` is **UTC `Z`**. |
| Tick frame | `event_id = last_tick_time.isoformat()`; `recent_tick_ids` opaque | **SSE tick payload stays bare naive UTC** for `event_id` and its `last_tick_time`; identity must not change. |
| Game-state API | `get_vault_status` returns `last_tick_time` | **UTC `Z`** — this is an API timestamp, not the SSE identity; keep it separate from `event_id`. |
| API canonical | `schemas/training.py` emits `Z` | **UTC `Z`**; use it as the template for every schema. |
| API default | Most schemas rely on Pydantic default serialization | **UTC `Z`** via explicit field serializers; no bare or `+00:00` output. |
| API `system/info` | `build_date` aware `+00:00` | **UTC `Z`** (changes from `+00:00`). |
| Credentials / calendar keys | JWT `exp` numeric; `%Y-%m` month keys; TTLs | **Unchanged**; not instants. |
| Frontend | `parseUtcMs` accepts naive and offsets; some views call `new Date(value)` | **Accept all three forms** (bare, `Z`, offset); migrate remaining `new Date` call sites before B4. |

### SQLite-backed domain tests

SQLite has no timezone storage: `DateTime(timezone=True)` still returns naive values there, so naive/aware
comparisons would fail after reload even when PostgreSQL is correct. Do not leave that to per-site
normalizers.

**Chosen contract: one `UTCDateTime` `TypeDecorator`** (implemented in `app/utils/types.py`) wraps every
timestamp column at B4:

- `impl = DateTime(timezone=True)` keeps PostgreSQL DDL as `timestamptz` and Alembic's view of the type
  unchanged; set `cache_ok = True`.
- `process_bind_param`: convert with `as_utc()`; on SQLite strip `tzinfo` after conversion so the stored
  text stays naive UTC and lexicographic range comparisons keep working; on PostgreSQL bind the aware value.
- `process_result_value`: re-attach UTC on SQLite (`value.replace(tzinfo=UTC)`); on PostgreSQL return the
  driver's aware value.

Domain code, fixtures and tests therefore always see aware UTC datetimes on both backends. That is what
lets the full SQLite suite stay green without dialect branches in services; `as_utc`/`as_naive_utc` remain
only at true boundaries (legacy JSON strings, config values, raw-SQL fixtures). Raw SQL that bypasses the
ORM is still responsible for its own UTC handling.

Validate the decorator before converting columns: a round-trip test on both backends that binds an aware
`+02:00` value, reads it back and asserts the instant, plus a range query against a 15-minute threshold.

### Mixed-type traps

1. Do not flip `utcnow()` to aware before the columns are `timestamptz`: an aware clock against a naive
   DB value raises `TypeError`.
2. `objective_periods()` returns naive midnights. At B4 it returns aware UTC midnights; persisting a naive
   midnight into a `timestamptz` column would reinterpret it through the session timezone.
3. `shift_trial_clocks()` uses `min(stored + paused, now)`; both operands must have the same awareness.
4. `GameState.resume()` and `resource_manager_service` compare `resumed_at` / `last_tick_time` against
   other stored values; one clock and one awareness per comparison.
5. `event_id` and `recent_tick_ids` are identity, not human timestamps. A format change breaks SSE replay.
6. `Notification.get_expired_batch` receives cutoffs computed by `cleanup_service`; after B4 the cutoffs
   and `created_at` must both be aware.
7. `WorldLocation.get_elapsed_reclears` rechecks eligibility in Python after the `FOR UPDATE`; keep the
   SQL bound and the Python recheck on the same type.
8. `Pregnancy.is_due` is the reference for a correct awareness-safe comparison; use the same shape rather
   than reintroducing `replace(tzinfo=None)` at call sites.
9. SQLite cannot prove production behavior on its own: `DateTime(timezone=True)` still returns naive
   values there. Prove the ORM contract with the `UTCDateTime` round-trip test above, and prove the SQL
   conversion with the PostgreSQL contract test under a non-UTC session timezone.
10. `system/info` is the only production clock read that intentionally keeps an aware value
    (`datetime.now(UTC)`); do not "normalize" it away.

### B4 is one coordinated deployment

These are internal implementation steps, not separately deployable increments. A 2.x release may ship
compatible **readers** only. After that, B4 ships in one maintenance window with every writer stopped.

1. **Pre-deploy (2.x, readers only):** land frontend `parseUtcMs` usage, JSON/SSE readers that accept bare
   and offset values, and the API field serializers in read-only form. Do not change writers or the clock.
2. **Quiesce:** enter `maintenance_mode=true`; stop API, worker, scheduler and any other writer; verify no
   other Jobs, CLI or cron writers are active.
3. **Back up:** take and verify the pre-migration snapshot while writers are stopped.
4. **Schema + models, one change:** convert the 122 columns with `USING <col> AT TIME ZONE 'UTC'` and switch
   model declarations to `UTCDateTime` in the same deployment.
5. **Clock + consumers, same deployment:** flip `utcnow()` to aware UTC and update every C comparison and
   Q bound to aware UTC. No mixed pair may run in production.
6. **Writers/serializers:** apply the output decisions above; keep JSON history and identity strings
   byte-stable.
7. **Start under maintenance:** start the matching API and worker with play still closed, then verify
   revision/schema/instants, a real tick, deadlines, SSE replay and desktop/phone timestamps.
8. **Reopen:** open play only after those live checks pass.
9. **Rollback:** keep the pinned v2 image and pre-migration snapshot. Rolling back after new progress
   restores the snapshot and discards post-window activity — state that explicitly in the release notes.

Acceptance gates for the B4 PR:

- `alembic check` clean after the model type change; `test_enum_drift.py` green.
- `tests/test_db/test_utc_migration_contract.py` passes under a non-UTC session timezone.
- JSON readers accept legacy bare strings and explicit offsets; stored history is unchanged.
- Tick `event_id` and `recent_tick_ids` formats are unchanged.
- Full suite green on 3.13 and 3.14, plus the production-clone rehearsal evidence.

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
