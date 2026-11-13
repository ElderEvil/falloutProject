# Fallout Shelter — Development Roadmap

_Last updated: 2026-11-11_

## Current direction

Connect existing gameplay before adding new systems. The next gameplay release theme is **The Continuity
Update**; Semantic Release chooses the version. Existing mechanics should lead naturally into useful next
decisions. The 3.0 platform boundary has shipped ([details](#platform-boundary-30-shipped-31-gated)); the
remaining platform work (3.1) waits on upstream support.

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

## Platform boundary: 3.0 shipped, 3.1 gated

**v3.0 shipped on 2026-11-10** as v3.0.0; v3.0.1 followed with atomic dweller-death and game-tick
fixes. It is a runtime and database boundary, not a feature release:

- Python 3.14 only — `requires-python = ">=3.14,<3.15"`, `.python-version`, both Docker stages,
  Ruff/ty targets and a single CI leg.
- SQLModel 0.0.48 / SQLAlchemy 2.1 with aware UTC — migration `4b3cbd7b15ff` converted the 122
  application timestamp columns to `timestamptz`; `app/utils/time.py` is the single clock source and
  `UTCDateTime` normalizes SQLite storage.
- UUIDv7 for new rows; existing UUIDv4 rows stay valid and resolvable.
- pwdlib/Argon2 replaces passlib, with bcrypt rehash-on-login.

Evidence: the production-clone rehearsal (restore → migrate → tick → downgrade → pinned v2.295.1) is
recorded in the [3.0.0 runbook](releases/3.0.0.md#4-production-clone-rehearsal); the conversion
contract lives in the [UTC migration preparation](backend/UTC_MIGRATION.md).

**Deviation kept visible:** the boundary shipped ahead of journeys
[#1034](https://github.com/ElderEvil/falloutProject/issues/1034) and
[#1112](https://github.com/ElderEvil/falloutProject/issues/1112); only #928 was closed. A maintainer
playtest on current master (2026-11-11) reported the game working, which is a smoke check, not the
recorded journey evidence the journeys still require. Journeys stay the active work; the
[implementation plan](plans/2026-11-08-3.0-platform-boundary.md) records the shipped phases.

Remaining 3.0 follow-ups:

- The opt-in Alembic fresh-install baseline is regenerated at `4b3cbd7b15ff`
  (`alembic-squash.ini`, `squash_4b3cbd7b15ff`). Production-clone adoption and the decision to
  promote it remain outstanding; a baseline stamp alone does not prove legacy rows were converted.
- Keep the rollback pin (v2.295.1 images plus the pre-migration dump) current until post-release
  confidence is recorded through the runbook's operator checks.
- Resolve the post-deploy edge findings in
  [#1390](https://github.com/ElderEvil/falloutProject/issues/1390) and
  [#1388](https://github.com/ElderEvil/falloutProject/issues/1388).

### 3.1 — dependency majors

Milestone [3.1](https://github.com/ElderEvil/falloutProject/milestone/2), gated on upstream support:

- [Pydantic v3 #1258](https://github.com/ElderEvil/falloutProject/issues/1258), TypeScript 7, HTTPX 2
  and the remaining tooling items.
- Each waits for its ecosystem: SQLModel/PydanticAI/FastAPI for Pydantic v3, Volar/`vue-tsc` for
  TypeScript 7. The TypeScript `>=7` Dependabot ignore is the only Dependabot hold left, and uv still
  constrains `logfire`/`logfire-api` to `<5`. The `sqlmodel`/`sqlalchemy` bounds moved with the 3.0 ORM
  bump; the `multidict`, `soupsieve` and `websockets` holds were lifted in #1393.
- Upgrade on measured evidence: the
  [3.1 baseline contract](plans/2026-11-11-3.1-dependency-baseline.md) freezes the before-snapshot
  (app import, RSS, validation, typecheck) and `scripts/dep-baseline.py` reproduces it per candidate
  upgrade.
- zuvloop was benchmarked on 2026-11-11 and not adopted (~13% slower p50/p95 than uvloop on the API
  workload); re-check on a later release.

## Deferred direction and retained research

[Deferred register #1113](https://github.com/ElderEvil/falloutProject/issues/1113) indexes world/NPC/travel,
visual experiments, difficulty/Survival, multiplayer, Jev, youth/lore, console, Vue Query and 3.1 platform
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
