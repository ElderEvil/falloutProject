# Fallout Shelter — Development Roadmap

_Last updated: 2026-11-05_

## Current direction

Connect existing gameplay before adding new systems. The next release theme is **The Continuity Update**;
Semantic Release chooses the version. Existing mechanics should lead naturally into useful next decisions.

The [integration plan](features/INTEGRATION_PLAN.md) defines scope, evidence, constraints and recovery.
Keep **one gameplay journey in implementation at a time**, with necessary maintenance alongside it.
This phase is planning and integration work; it does not claim the journeys are already verified.

## Delivery order

| Order | Journey | Outcome | Tracker |
| --- | --- | --- | --- |
| 1 | First session to quests | A fresh standard vault teaches useful actions, supports the Office path and hands off to an eligible quest party. The short intro ends at the first exploration handoff; contextual lessons continue later. | [#1034](https://github.com/ElderEvil/falloutProject/issues/1034) |
| 2 | Expedition return to useful outcomes | Clear granted/claim/report/overflow states lead into equipment, crafting, care or the next mission with context preserved. | [#928](https://github.com/ElderEvil/falloutProject/issues/928) |
| 3 | Returning-player continuity | The existing Briefing prioritizes urgent problems and ready work; notifications and completion surfaces lead to the relevant action. | [#1112](https://github.com/ElderEvil/falloutProject/issues/1112) |

Start with an authenticated non-boosted-vault playthrough on current master. Reconcile the historical
starter momentum report and tutorial coverage before choosing fixes; later work changed starter rewards,
claims and objective accounting. Repair demonstrated anchors, prerequisites and handoffs in small PRs.

The existing [flow research](features/GAME_FLOW_CONTINUITY_RESEARCH.md),
[tutorial reference](frontend/ONBOARDING.md) and [balance playtests](backend/BALANCE_PLAYTEST.md) provide
starting evidence. Their dated findings and PR statuses need rechecking rather than automatic implementation.

## Existing PR queue

- Plan [site discovery alerts and playable encounters #1193](https://github.com/ElderEvil/falloutProject/issues/1193).
  This supersedes closed [site discoverability #1098](https://github.com/ElderEvil/falloutProject/pull/1098);
  its branch and recovery head remain recorded in the issue. Review and playtest
  [room/dweller/chat context #1100](https://github.com/ElderEvil/falloutProject/pull/1100) separately.
- Reassess [unfinished spotlight repair #1060](https://github.com/ElderEvil/falloutProject/pull/1060)
  through journey 1; historical green checks did not resolve the reported manual-playtest failures.
- Keep dependency and pre-commit updates in maintenance; resolve their actual current CI/review findings.
- Deferred experiments #1109, #1107, #1024 and #973 leave the active PR queue with exact recovery heads,
  source branches, findings and limitations preserved in the [integration plan](features/INTEGRATION_PLAN.md).

No PR is approved for merge by this roadmap.

## Supporting work

- [Backend ownership and proven compaction #740](https://github.com/ElderEvil/falloutProject/issues/740):
  consolidate #1032, reconcile already-shipped batches and support the selected journey. Keep architecture,
  transaction/concurrency guarantees, rejected alternatives and measured duplication removal explicit.
- [Operational correctness #885](https://github.com/ElderEvil/falloutProject/issues/885): verify the live
  inventory before changes; prioritize reproducible deployments, migration sequencing and recovery as warranted.
  Repository evidence and remaining live checks are tracked in
  [`deployment/k3s/README.md`](../deployment/k3s/README.md#issue-885-closure-evidence).
- Fix demonstrated correctness/security blockers promptly. Avoid unrelated rewrites or library migrations.

## 3.0 platform release plan

3.0 is a deliberate, reversible runtime and database boundary, not a routine version bump. The boundary
is split so the app major does not wait on upstream dependency schedules.

**v3.0 — runtime and database boundary** ([tracker #1259](https://github.com/ElderEvil/falloutProject/issues/1259);
target: late 2026 / early 2027)

- Python 3.14 baseline: `requires-python`, CI, container images and development tasks.
- SQLModel 0.0.48 + SQLAlchemy 2.1 with the aware-UTC migration (`timestamp → timestamptz` + backfill).
- Alembic baseline regeneration and a production-clone migration/rollback rehearsal.
- One maintenance window, a rollback pin, and a `BREAKING CHANGE:` commit so Semantic Release produces 3.0.0.
- Starts only after journeys [#1034](https://github.com/ElderEvil/falloutProject/issues/1034) and
  [#1112](https://github.com/ElderEvil/falloutProject/issues/1112) are verified/closed; #928 is closed.

**v3.1 — dependency majors** ([milestone](https://github.com/ElderEvil/falloutProject/milestone/2); 2027,
gated on upstream support)

- [Pydantic v3 #1258](https://github.com/ElderEvil/falloutProject/issues/1258), TypeScript 7, HTTPX 2,
  UUIDv7 and the remaining tooling items.
- Each waits for its ecosystem: SQLModel/PydanticAI/FastAPI for Pydantic v3, Volar/`vue-tsc` for TypeScript 7.
- Evaluate [zuvloop](https://github.com/Kludex/zuvloop) after the Python 3.14 baseline. It requires Python
  3.14+, is a young native Zig/libuv loop, and would replace uvloop on the API plus the worker loop factory.
  Benchmark FastAPI/Uvicorn, Dramatiq, asyncpg/Redis compatibility, image size and connection footprint before
  deciding; do not add it during the 3.0 boundary.

No v3.0 date is announced until the tracker's gates are green. Keep the Dependabot pre-3.0 ignores
(`sqlmodel >=0.0.45`, `sqlalchemy >=2.1`, `typescript >=7`) until each boundary opens.

### Preparation and remaining gates

Tracker #1259 was closed on 2026-10-31 with its release checklist still unchecked. Its closed state
does not establish that the boundary shipped. Use the evidence below when reassessing release readiness.
Compatibility preparation may proceed alongside the selected gameplay journey; switching the baseline
and migrating persisted timestamps remain gated on the journeys above.

| Gate | Current state | Required next evidence |
| --- | --- | --- |
| Python 3.14 compatibility | `requires-python` admits 3.13 and 3.14; backend tests, Alembic checks and image smoke run for both. Package versions stay pinned in the shared lockfile. | Both CI runtimes stay green; the final baseline PR changes `.python-version`, Docker defaults, Ruff/ty targets, hook runtime and setup documentation together. |
| Production runtime | `.python-version`, release-image selection and Docker defaults remain 3.13. | An explicit baseline switch after gameplay verification; compatibility CI alone does not complete this gate. |
| Gameplay | #1034 and #1112 remain open; #928 is closed. | Authenticated standard-vault desktop/phone playthroughs, recovery boundaries and recorded remaining friction. |
| ORM and aware UTC | SQLModel `<0.0.45`, SQLAlchemy `<2.1`; naive UTC remains the documented contract. | Inventory schema and serialized timestamps, then test conversion, comparisons, API round trips and background ticks against PostgreSQL before changing the bounds. |
| Migration and recovery | `scripts/restore-drill.sh` provides an isolated restore foundation. | Run the final migrations on a production clone, prove enum/schema consistency and application readiness, and rehearse recovery with the pinned v2 image and matching database snapshot. Regenerate the Alembic baseline only after the final schema change. |
| Release | No 3.0 cutover is established by this preparation. | Schedule the maintenance window, pin rollback artifacts and use a reviewed `BREAKING CHANGE:` release commit. |

The next database slice starts with `TimeStampMixin`/`SoftDeleteMixin` in `app/models/base.py`,
the UTC-pinned API and task engines in `app/db/session.py`, and deadlines in exploration, training,
pregnancy, crafting, incidents and quest returns. Include timestamps embedded in exploration JSON,
not just typed SQL columns. Explicitly interpret existing naive values as UTC during backfill; changing
column types or replacing `datetime.utcnow()` alone does not establish correct elapsed-time behavior.
PostgreSQL checks must cover preserved instants under a non-UTC session timezone, nullable timestamps,
deadline boundaries, enum labels and API offset handling. Do not mix this with the runtime preparation PR.

A fresh PostgreSQL 18 database migrated to `c8f2a1b3d4e5` on 2026-11-05 contains **122 timestamp
columns across 39 tables**, all `timestamp without time zone`. This is a schema inventory, not a
production-data audit or migration rehearsal. Reproduce the inventory before designing the conversion:

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND data_type LIKE 'timestamp%'
ORDER BY table_name, column_name;
```

## Deferred direction and retained research

[Deferred register #1113](https://github.com/ElderEvil/falloutProject/issues/1113) indexes world/NPC/travel,
visual experiments, difficulty/Survival, multiplayer, Jev, youth/lore, console, Vue Query and 3.0 platform
research with reopening conditions. Earlier priority labels are historical during this integration phase.
Closing a deferred source does **not** mean it shipped or its findings were rejected.

- [Integration plan and recovery inventory](features/INTEGRATION_PLAN.md)
- [Complete prior roadmap](ROADMAP_ARCHIVE_2026-10-20.md), preserved with its distinct decisions and links
- [Pre-consolidation issue/PR snapshot](planning/BACKLOG_SNAPSHOT_2026-10-20.md)
- [Release history](../CHANGELOG.md)

## Phase completion

Record real gameplay evidence for all three journeys: version, initial state, actions, outcomes, waiting
and remaining friction. Verify desktop/phone and relevant resume, capacity, stale-state, duplicate-event
and vault-switch boundaries. Write failing regressions before bug fixes and run the relevant checks.

Preserve automatic ordinary production, explicit objective/quest claims, deliberate spending/equipment
choices, deferable overflow, server authority, layer boundaries and progression toast/modal delivery.
Revisit new-system priorities only after the journeys demonstrate clear outcomes and useful next actions.
