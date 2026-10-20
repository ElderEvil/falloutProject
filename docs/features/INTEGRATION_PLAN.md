# Integration and player flow

Approved direction: 2026-10-20. Connect existing gameplay before introducing new systems. The next
release theme is **The Continuity Update**; Semantic Release remains the version authority.

## Outcome and delivery order

Players understand what changed, make a meaningful decision, and continue into the next useful action
without remembering every subsystem or searching every page. Ordinary production remains automatic;
objective/quest claims and consequential spending/equipment decisions remain explicit.

Keep one gameplay journey in implementation at a time. Small independent reviews and necessary maintenance
may proceed alongside it. A new system is deferred until the three journeys below have recorded gameplay
evidence. Existing-mechanic changes still need a demonstrated problem and bounded scope.

| Order | Journey and tracker | Completion evidence |
| --- | --- | --- |
| 1 | [First session to quests #1034](https://github.com/ElderEvil/falloutProject/issues/1034) | Fresh non-boosted standard-vault UI playthrough: staffing/housing → actual newcomer → equipment → first exploration → funded Office path → eligible quest party. Record time, waiting, income/spending and remaining friction. The short opening tour ends at the first exploration handoff; later objectives/contextual lessons carry the rest. |
| 2 | [Expedition outcomes #928](https://github.com/ElderEvil/falloutProject/issues/928) | Dispatch/site decision → return → accurate granted/claim/report/overflow states → useful inventory, recipe, equipment, care or next-mission action. Preserve context and deferred decisions. |
| 3 | [Returning-player continuity #1112](https://github.com/ElderEvil/falloutProject/issues/1112) | Existing Briefing surfaces an urgent problem and useful ready work; notifications open the relevant entity/action. Training, crafting and incident outcomes lead to assignment/equipment/recovery. Reading a notification never substitutes for settling a decision. |

Each implementation PR should name the journey gap, reproduce it first if it is a bug, change the smallest
existing flow, and provide relevant regression/browser evidence. Do not open a new issue for every research
bullet; extract one bounded implementation scope when it is selected for delivery.

## First session

Consolidate [tutorial coverage #1027](https://github.com/ElderEvil/falloutProject/issues/1027),
[momentum playtest #1042](https://github.com/ElderEvil/falloutProject/issues/1042) and the spotlight repair
under #1034. Preserve the original reports and numeric evidence. Remeasure on current master before tuning:
starter grants, named residents, explicit claims, objective renewal and production accounting have changed
since the v2.223.0 playtest. Its suggested passive caps, price changes and timing policy are alternatives,
not approved fixes.

Reassess [unfinished spotlight PR #1060](https://github.com/ElderEvil/falloutProject/pull/1060) against the
actual current UI. It explicitly reports unresolved manual-playtest failures despite historical green
checks. Fix anchors/prerequisites/context before extending contextual lessons. Preserve skip/resume/replay,
per-vault state, dialog suspension, quiet polling, keyboard/touch and reduced motion. Update
[ONBOARDING.md](../frontend/ONBOARDING.md) only as behavior is verified; its current coverage is historical.

## Expedition outcomes

Use [the existing continuity research](GAME_FLOW_CONTINUITY_RESEARCH.md), preserving its source baseline.
For every finding, record resolved, reproducible or unverified on current master. Its objective-claim
observation has been superseded by explicit claims and batch collection (#1110).

Initial source checks on 2026-10-20 still found the exploration report's close action labeled “Collect
Rewards” and no specific recipe-unlocked/crafting-complete destination in notification routing. Those are
source observations, not a newly completed runtime audit. Verify settlement before correcting wording;
do not unify quest and exploration settlement merely to give them identical buttons.

Review/playtest [site visibility #1098](https://github.com/ElderEvil/falloutProject/pull/1098) and
[room/dweller/chat context #1100](https://github.com/ElderEvil/falloutProject/pull/1100) as focused existing
work. Neither is approved for merge by this plan. #1100 does not preserve transient detail tabs, scroll
or unsent chat drafts across expansion; retain that limitation in review.

Outcome handoffs must use current inventory/crew/eligibility. An old report is historical; its item may
have been sold or equipped. Do not identify an exact rewarded copy by name alone. Explain retained medical
stock and overflow rather than promising nominal rewards at full capacity. Preserve later resolution,
ownership and duplicate-settlement protections.

## Returning-player continuity

Extend the existing Overseer Briefing and route construction. Critical incidents and shortages outrank
opportunities; do not let a larger ready-work list hide emergencies. Current state drives actionability,
independently of bell read/unread status. A stale/deleted target needs a useful fallback.

Choose a bounded handoff using existing operations: ready claim, crafting collection/equipment, completed
training/reassignment, unresolved outcome, or incident recovery. No new dashboard, generic opportunity
engine, automatic claims, equipment selection or staffing policy is approved by this plan.

## Supporting engineering and operations

- [Service ownership and compaction #740](https://github.com/ElderEvil/falloutProject/issues/740) absorbs
  [#1032](https://github.com/ElderEvil/falloutProject/issues/1032). Reconcile merged overflow, item-factory
  and departure work (#1075, #1077, #1094) before starting another batch. Preserve the source analysis in
  [service-compaction-analysis.md](../../.omo/service-compaction-analysis.md), rejected abstractions,
  concurrency guarantees and transaction boundaries. Count actual duplication removed, not module moves.
- [Operational correctness #885](https://github.com/ElderEvil/falloutProject/issues/885) remains independent.
  Inventory actual production before asserting repository gaps are live failures. Prioritize reproducible
  images, migration/rollout order, readiness and demonstrated recovery as warranted; cluster changes or
  deployments are outside this planning change.
- Keep dependency/pre-commit PRs in maintenance. At review time #1091 had a failing frontend check and
  #1101 a failing title check; recheck current CI before action. Green historical CI does not approve merge.

Preserve endpoints → services → CRUD, frontend module boundaries, catalog item factories, server-owned
eligibility, explicit transaction ownership, tick-session compatibility and progression toast/modal plus
bell delivery. This plan does not relax AGENTS.md or game-domain invariants.

## Deferred research and experiments

[Deferred register #1113](https://github.com/ElderEvil/falloutProject/issues/1113) owns the shared recovery
index and reopening conditions. Closed sources remain readable; closure means deferred/consolidated,
not implemented. All original open-item bodies are in the
[pre-consolidation snapshot](../planning/BACKLOG_SNAPSHOT_2026-10-20.md).

| Area | Preserved sources | Condition before scheduling |
| --- | --- | --- |
| FAQ/design/flavour research | #982 | A specific current journey needs the finding; validate its dated hypothesis. Preserve the decision against permanent Endurance-dependent HP disadvantage. |
| Storage server-state experiment | #1051, PR #1109 | One shared storage-items read replaces existing ownership and machinery, including the count. Preserve auth isolation, cancellation-before-invalidation, unknown/zero/retained data and real mutation coverage. No library adoption is implied. |
| 3.0 ORM/UTC and Alembic baseline | #915, PR #1107 | Separate platform milestone, aware-UTC migration, enum validation and production-clone rehearsal. Regenerate the baseline after final schema changes. |
| World taxonomy, travel, capacity and NPCs | #862, #863, #893 | Choose a bounded milestone after existing flow is proven. Keep classification, world/version compatibility, visibility, atomic limits and separately approved travel policy distinct. |
| Asset pipeline, scenes, actors and surroundings | #817, #818, #819, #820, PR #1024 | A real flow needs the improvement and an isolated experiment proves quality/effort/performance. Preserve fresh-animation direction, fallbacks and provenance. |
| Difficulty presets / Survival | #838, #839 | Validate Standard first; decide scoped settings, irreversible mode behavior and export-economy implications. |
| Jev AI | #924 | Choose one evaluated advisory slice after core flow. Preserve its earlier priority as history, calibrated fallback, bounded provider calls and independent safe sessions; no calls inside locked ticks. |
| Youth usefulness / lore | #1084 | Playtest current apprenticeship and choose one improvement. Preserve player feedback and rare mutant easter-egg idea; proposed mechanics remain undecided. |
| Multiplayer | #1057, PR #973 | Explicit later multiplayer milestone. Preserve consent/blocking/auth/concurrency contracts; messaging is a feature-gated polling prototype. |
| Superuser terminal | #1041 | Demonstrated need beyond existing CLI/debug tools; preserve authorization and audit requirements. |

### Recovering closed PR experiments

No source branch is deleted. Exact heads were fetched and verified before closure:

| PR | Preserved commit | Retained limitation |
| --- | --- | --- |
| [#1109](https://github.com/ElderEvil/falloutProject/pull/1109) | `9930c26b1cd4c79df16a3187f56c20cd3316f112` | Count composable still 115 lines; provider/query setup and a parallel storage read add ownership. |
| [#1107](https://github.com/ElderEvil/falloutProject/pull/1107) | `e512307ea51141818f9b195aba8ad04715d93714` | Frozen prototype through `b7e3d9c1a5f2`; local drift and later schema changes require a new manifest/rehearsal. No cutover. |
| [#1024](https://github.com/ElderEvil/falloutProject/pull/1024) | `b4fc314cb16c234fb0283db6c929e3183e38efe9` | Standalone Arena-tier-1/Response-size-3 study; public preview would ship. No live gameplay integration. |
| [#973](https://github.com/ElderEvil/falloutProject/pull/973) | `ccc87b844acbd9f37e39f5d32e3bf67fe8c7c5fa` | Combined end-to-end experiment; flag off, polling rather than live DM push. |

Inspect the linked PR description, files and reviews before recovery. Fetch `pull/NUMBER/head` from origin
and verify `FETCH_HEAD` against the recorded SHA; original branch names are recorded in the snapshot and
#1113. The planning workspace also retains `refs/archive/integration-2026-10-20/pr-NUMBER` for each head.
Start a fresh branch from current master and recover only the justified slice. Revalidate contracts and
checks; do not rebase an entire old experiment into production by default.

## Evidence and phase exit

For each journey, record version/commit, permissions, initial state, actions, actual outcomes, waiting,
friction and evidence links. Distinguish source inspection, mocked browser tests, simulated time and live
play. At minimum verify the changed flow on desktop/phone and relevant reload/resume, capacity, stale
state, duplicate delivery and vault-switch boundaries. Backend defects require tests before fixes.

The phase ends when a fresh standard-vault journey, an expedition return/use journey and a returning-player
session demonstrate clear outcomes and useful next actions, with known limitations recorded. Unit counts,
closed issue counts and new mechanics are not substitutes for that evidence. Revisit expansion choices
then; reopening a source requires its recorded condition and a bounded implementation scope.

## Preservation record

- GitHub consolidation verified on 2026-10-20: 23 open issues became 6 (three journey trackers,
  engineering, operations and the deferred register); 9 open PRs became 5. Nineteen source issues and
  four experimental PRs were closed with disposition/recovery links. Closed source bodies remain
  unchanged, none of the deferred PRs was merged, and all four source branches were verified on origin.
- [Historical roadmap](../ROADMAP_ARCHIVE_2026-10-20.md): complete prior roadmap, retained as dated evidence.
- [Original open-item snapshot](../planning/BACKLOG_SNAPSHOT_2026-10-20.md): all 23 issue bodies, all 9 PR
  descriptions, exact PR heads and captured discussion/reviews for the four deferred PRs.
- Original GitHub bodies/discussions remain intact below added planning notices or at closed source items.
- Existing specialist docs remain reference material. Their historical priority/status text is superseded
  by this plan; their mechanics and distinct unresolved decisions remain binding where applicable.
- No feature implementation, tests, migration, deployment, release bump, remote branch deletion, push or
  merge is performed by the planning consolidation.
