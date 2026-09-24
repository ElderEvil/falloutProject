# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:** — _backend service-layer rewrite: vault-batch (#572), game-loop split (#573), and
incidents tick-orchestration (#574) merged; incidents batch closed with per-incident commit policy (see P0)._

**Also in progress (frontend):** component-library migration to shadcn-vue (full) started 2026-09-22 — Phase 0
spikes plus the visual-test safety net; see "Frontend Component-Library Migration" below.

---

## Active Priorities

### P0 — Backend service-layer architecture rewrite

Re-establish the CRUD/repository → service → endpoint boundaries before expanding backend mechanics. The current
service layer mixes orchestration, direct SQL/session work, transport concerns, and broad exception recovery; rewrite
it incrementally by domain rather than performing a risky all-at-once reorganization.

- [ ] **Chat and AI batch** — unify text, streaming, and audio validation/orchestration; move persistence and
  provider-boundary handling behind focused collaborators; preserve the existing public service entry points while
  rewriting `chat_service`, `services/chat/*`, conversation, AI, quota, and prompt flows.
  - **In progress:** shared chat quota enforcement, API-boundary quota headers, and text endpoint domain-error
    propagation; text, streaming, and voice token accounting now read the agent usage property.
  - **Voice boundary:** typed service results preserve JSON/MP3 output; empty-audio validation and notification
    orchestration live in the service, and domain failures retain their status through the API handler.
  - **Access boundary:** text, voice, streaming, and history now share vault ownership validation with API
    dependencies; owners and superusers are allowed, while foreign/missing dwellers are rejected before chat work.
  - **Persistence boundary:** quota/prompt queries live in CRUD; text, streaming, and voice commit happiness,
    usage, and both messages together. Agent fallback and optional place discovery use savepoints so they cannot
    roll back the enclosing conversation or release its quota lock. Prompt activation remains append-only.
    Typed streaming events carry validated token, completion, and error records through the service while the
    WebSocket boundary preserves the client protocol. Text and voice now share the same provider runner, fallback,
    prompt construction, usage extraction, and execution records.
- [ ] **Vault and game-loop batch** — separate tick orchestration, vault state transitions, resource calculations,
  room operations, and notifications; keep transaction and concurrency behavior explicitly test-backed.
  - **Shipped (#572):** the last CRUD-side flows moved into services — `dweller.move_to_room` (+
    `auto_assign_to_best_room`, first slice of the Dweller/social batch) into `DwellerService`, the `item_base`
    sell/caps flow into new `ItemService` (sale events publish only after commit); the five `vault_crud` legacy
    delegates (`deposit_caps`/`withdraw_caps`/`recalculate_*`/`is_enough_*`) deleted and the vault-with-counts
    reads moved into `VaultService`. The dead `toggle_game_state` endpoint and orphaned `GameStatusEnum` were
    removed (live pause is `POST /game/vaults/{id}/pause|resume`); `get_highest_special` and
    `calculate_room_capacity` centralized in `room_assignment_policy`.
    Already done earlier: objective-seeding delegation, storage CRUD helpers + item `create_many`, seed tables in
    `services/vault_seed.py`, vault economy core (`deposit/withdraw`, `is_enough_*`, recalculation) canonical in
    `VaultService`, room build/destroy/upgrade orchestration canonical in `RoomService`.
  - **Shipped (#573):** `game_loop.py` tick decomposed the same way (878 → ~280-line facade over
    `services/game_tick/` dwellers + family collaborators), plus a `@pytest.mark.slow` tick perf probe
    (normal vs boosted vault) showing the split is perf-neutral.
- [ ] **Incidents and combat batch** — isolate incident state transitions, combat calculations, persistence, and
  player-facing events.
  - **Shipped (#569, #571, #574):** math, publishing, round engine, spawning, and tick orchestration
    extracted behind the facade (`incident_service.py` 888 → ~310-line facade over `services/combat/`;
    `process_vault_incidents` / `process_all_vaults_incidents` in `combat/incident_tick.py`). Commit policy
    decided: per-incident atomicity retained intentionally (background-loop survival; notifications/SSE drain
    post-commit per #449). Single-commit-per-tick parked pending perf evidence. Guards hold the ground: any new
    raw SQL or transport exception fails CI.
- [ ] **Dweller/social batch** — reorganize relationships, breeding, happiness, death, assignment, training, and
  lineage around explicit domain services and CRUD operations.
- [ ] **Quest/exploration/reward batch** — separate quest settlement, objective evaluation, exploration state,
  reward delivery, and prerequisite rules.
  - **Shipped (#702):** prerequisite rules are now a policy (`progression/quests/requirements.py`) and the quest +
    objective services live in a `progression/` domain package behind thin facades (see the SHIPPED section below).
    Remaining: quest reward settlement and exploration state still live in `reward_service` / `exploration_service`.
- [ ] **Infrastructure batch** — clean up health checks, storage, email, WebSocket/streaming, notifications, and
  backfill services without hiding operational failures.
- [ ] **Upward-dependency elimination (Area 2)** — nothing below the API layer may import `app.api`.
  - **Shipped #581:** pregnancy vault-access check moved out of CRUD; `get_static_game_data` relocated to
    `app/core/game_data.py`; `test_lower_layers_do_not_depend_on_api` scans `crud/` + `services/` (no baseline).
  - ⬜ **CRUD commit deferral (narrow, corrected scope)** — the earlier "CRUD never commits" framing was too broad.
    `SERVICE_LAYER.md`'s target is aspirational and explicitly grandfathers legacy CRUD commits; `notification.create`
    and `CRUDBase.update` already commit by default (`commit: bool = True`). Deferring the commit is only justified
    where a service must compose **multiple** mutations into one atomic unit (an internal commit would force a
    premature partial commit) — and it must not become flush-only, which silently loses a mutation for any caller
    that forgets to commit. So: keep CRUD committing by default; add a `commit` opt-out only for methods a service
    actually composes, characterization tests first. No notification / relationship / quest-party method qualifies.
    (A `crud/notification.py` attempt was reverted for exactly this reason.)
  - ⬜ **CRUD business logic** — item/room/dweller rules still in CRUD (`item_base.convert_to_junk`, `room` formula
    evaluator/build-price, `dweller` template reservation + XP curve), `mixins.complete` completion orchestration,
    and `quest.get_multi_for_vault` which writes on a read path.
- [ ] **Endpoint hygiene (Area 3)** — map `DomainError` to HTTP in one API-boundary handler instead of per-endpoint
  `except DomainError -> HTTPException` remaps (auth, training, relationship, user, game_control, pregnancy, quest,
  exploration, radio); thin the fat handlers (`game_control.get_game_balance_settings`, `dweller` revive/dead-list,
  `quest.start_quest`); stop endpoints issuing `select()`/`db_session.get()` and calling CRUD for state changes.
- [ ] **Debug surface** — shipped #583: the unauthenticated, state-mutating `/debug` router is replaced by
  `fo-cli debug` commands (evaluators wired as at startup); remaining `/pregnancies/debug/*` routes to reassess.
- [ ] **Oversized-module splits (Area 4)** — seam maps ready for `vault_service` (807), `crud/dweller` (760),
  `reward_service` (635), `breeding_service` (601), `family_scenario_service` (570), `ai_service` (563),
  `exploration/rewards_service` (557), `dweller_ai` (540), `map_service` (483), `arena_service` (464),
  `health_check` (462) — plus `relationship_service`/`notification_service`/`radio_service`
  (all >400). Use the `combat/` + `game_tick/` facade pattern; deleting a grandfathered top-level name requires
  removing its `SERVICE_NAME_GRANDFATHER` entry in the same commit. (`progression/objectives/evaluators` is no
  longer on this list — split into a `base`/`concrete`/`manager` sub-package, no file above ~270 lines.)
- [ ] **Service topology and ownership (Area 4)** — make a domain package the default unit of discovery and
  change. `services/` contains game-domain application operations only: `vault/`, `dwellers/`, `family/`,
  `exploration/`, `combat/`, `progression/`, `chat/`, `simulation/`, and `notifications/`. Place external
  adapters in `integrations/` (AI, storage, email), protocol delivery in `realtime/` (WebSocket/SSE), one-off
  backfills/cleanup jobs in `operations/`, and cross-cutting event infrastructure in `core/`.
  - A package may expose a small number of independently addressable public operations; it does not need a
    mandatory aggregate facade. Its internal modules use role names (`policy`, `lifecycle`, `rewards`, `events`),
    never catch-all `common`/`helpers`/`shared` modules. A domain may call another domain's documented public
    operation, but never reach into its internals; use semantic post-commit events for decoupled side effects.
  - Migrate incrementally, retaining a root compatibility facade only while callers move to the canonical path;
    tests must target that canonical module so monkeypatches do not silently diverge. Preserve one public
    transaction owner per operation and keep persistence queries in CRUD. Do not introduce a `BaseService`,
    service registry, generic repository, or global shared-service package.
- [ ] **Duplication clusters (Area 4)** — ranked: item builders (`reward_service` vs `exploration/rewards_service` vs
  vault seeding), health/radiation appliers (`event_service` trio vs `radiation_service` vs `incident_round`),
  `notify_owner` + `create_and_send` repetition, `LETTER_TO_STAT` vs `ABILITY_TO_STAT_MAP`, prod helpers duplicated
  into test utils/factories, CRUD "get dwellers by vault" variants.
  - **Ranked extraction backlog** (highest payoff first; one focused commit per cluster):
    1. ~~**XP/level-up settlement**~~ — shipped: `leveling_service.settle_level_up` is the single surfacing entry
       point (emits `DWELLER_LEVEL_UP` + notifies the owner) and every XP path uses it — the canonical
       `DwellerService.add_experience` (quest rewards), `game_tick/dwellers_tick` work XP,
       `combat/incident_round.award_combat_xp` (parked via `commit=False`, drained post-commit),
       `combat/arena_service`, and `exploration/rewards_service`. Locked by
       `tests/test_services/test_xp_settlement.py` (all five paths + deferred queue/drain/discard).
    2. **Exploration departure** — `exploration_service` validates, clears `room_id`, deducts supplies, and sets
       `EXPLORING` inline while `dweller_service` owns room/status transitions; departure already cancels active
       training inline (staged, no commit, so dispatch stays atomic). Remaining: extract a transaction-friendly
       "begin exploration"/availability policy instead of calling the commit-owning update service directly.
    3. **Overflow take/sell settlement** — `combat/incident_service` and `exploration/rewards_service` run parallel
       lock-owner → pop-item → reject-medical → capacity/caps → persist → commit flows; `loot_overflow_service`
       already holds shared primitives and is the natural home for an owner-agnostic settlement helper/protocol.
    4. **Item construction** — `utils/item_factory.py` (`build_weapon`/`build_outfit`) serves rewards, crafting,
       incidents, and seeds, but exploration builds weapons/outfits/junk inline in `exploration/rewards_service`
       (catalog-field/asset-URL drift risk). Normalize exploration loot into catalog-shaped data, then use the
       shared factory; add a shared junk builder if useful.
  - **Secondary:** composable no-commit medical-stock operation (`vault_service` vs `exploration_service`
    transfer/deduction); expedition availability policy (`is_available_for_expedition` /
    `is_in_vault_and_active` — responder, explorer, and dehydration eligibility share TODOs pointing at it);
    pure credit calculation for deferred reward caps (`reward_service` vs `vault_service`). Not duplication:
    `exploration_service` → modular exploration package and `incident_service` → `incident_tick` delegation are
    compatibility/orchestration facades.

**Rewrite rules:** keep each batch below 100 files; preserve public service singleton names during migration; add
characterization/regression tests before changing behavior; move reusable queries into existing CRUD modules instead
of introducing a second generic repository layer; remove broad exception handling unless it represents a documented,
recoverable boundary.

**Success criteria:** endpoints are thin, services contain domain orchestration only, CRUD owns persistence queries,
transport exceptions stay in the API layer, transaction boundaries are explicit, and each batch passes its focused
suite plus the full backend suite.

- [x] ~~**Advisory-lock connection pinning**~~ — shipped (#688). The lock now rides a dedicated
  `AsyncConnection` for its whole block (`db_locks.hold_advisory_lock`), so intermediate commits cannot move it,
  and a real-PostgreSQL integration test commits between acquire and release. The failure was worse than
  "latent": when the session's connection is closed on the commit that releases it (fresh or null-pooled
  engine), the lock is dropped mid-tick, so the serialization did not hold at all rather than merely leaking.
  The arena tick also discarded whether the lock was acquired and fought regardless — now it skips.

### P1 — Quest mechanics, rewards, and objectives

The progression loop must be correct and balanced before it grows. Quest rewards and mechanics need an end-to-end
audit; objectives need deliberate in-game validation rather than relying only on automated coverage.

- [x] ~~**Sequenced starter objectives & progress-relative quest gates**~~ — shipped (#700 + the quest-requirement
  branch): the ordered `starter` arc (current step derived, never written on completion), dweller-LEVEL +
  equipment gates validated against the dwellers SENT on the quest, progressive reveal beyond the vault's max
  dweller level + 10, the backend-owned Office gate, and pre-Office Next-step surfacing all landed. One locked
  decision was reversed: the three high-gate quests (Against the Odds 46, A Poorly-Thought-Out Plan 44, A Gathering
  of Ghouls 27) keep their LEVEL gates — enforced against the party, matching the real game — rather than being
  re-authored to progress gates (plan §WS2c). Plan: `.omo/plans/quest-objective-progression.md` (complete).
- [ ] **Quest correctness audit** — inventory every supported quest type and completion path; verify eligibility,
  lifecycle transitions, reward calculation/claiming, storage transfer, notifications, and repeat/duplicate-claim
  protection. Add a regression test for every bug found before changing the implementation.
  - **In progress:** `building`, `population`, and state-based `training` quests now settle directly from validated
    vault progress; `exploration` and `combat` retain the timed-party path. `quest_type` remains presentation metadata.
  - **Shipped:** generic `ITEM` delivery now covers weapon/outfit/junk plus quantity-honoring generic rows;
    medication `ITEM`s (Stimpak/RadAway) route to dweller stock so treatment can spend them, the Legendary Dweller
    `ITEM` materializes a canonical legendary template, and the storage view shows generic supplies in their own
    tab. Remaining: lunchbox opening (no open mechanic exists yet — a feature, not a correctness fix).
  - **Known bug (next PR):** the quest-detail modal's Start Quest button calls `assignQuest` (link visibility) instead
    of the start flow, so timed quests never get `started_at` and never actually start. Route the action through the
    parent: state quests (`building`/`population`/`training`) start directly, others assign a party first. Pre-existing
    in the deleted `QuestDetailView`; carried into `QuestDetailModal` by the modal conversion.
- **Verified gap:** chains persist predecessor links and hide locked entries; **requirement-driven unlock feedback
  shipped** — the chain lock reason names the actual predecessor ("Complete 'Getting Started' first"), surfaced on
  both the read path and the start rejection. An explicit chain lifecycle (beyond predecessor gating) remains open.
- [ ] **Objective balance review** — enumerate active objective templates and their targets/rewards; identify dead,
  trivial, or excessively grindy objectives and tune from observed normal-vault progression rather than assumptions.
- [ ] **Quest reward reconciliation** — establish a single reward contract shared by backend settlement, API responses,
  notifications, and frontend presentation so caps, items, XP, and objective progress agree exactly.
- [ ] **Notification click-through investigation** — collect cases where a notification opens an unexpected screen,
  tab, entity, or state; trace route construction and query-prop handling from notification metadata through the
  destination view. Add targeted regression coverage before changing navigation behavior.

**Order:** fix quest/reward correctness first, then tune objective balance from the same playtest evidence; do not add
new quest kinds until the existing loop is trustworthy. Investigate click-through failures after the playtest yields
reproducible cases, unless they block a core progression action.

## Low-Hanging Fruit — Immediate User-Facing Improvements

These items are small, scoped changes that deliver noticeable player value without requiring new systems or heavy
architecture. They are ordered by a rough impact/effort ratio, and they respect the v2.35+ constraint that every
update reduce net source LOC (features that add code must first offset it by removing or compacting existing code).

### P2 — Deferred player-facing improvements

- [ ] **Lifetime statistics reliability** — define and document the difference between dwellers created and
      children born through breeding; ensure a user profile exists before statistic events so increments are not
      silently lost; reconcile historical birth/death counters where source records permit an accurate backfill.
      Treat unrecoverable history as unavailable rather than zero, and verify the mortality rate against the
      lifetime dweller denominator across existing accounts.
- [ ] **Living biographies** — build on shipped template bios with action-driven updates for exploration, marriage,
      and dialogues. Start with the structured-entry storage decision (JSONB vs side-table).
  - **Effort:** medium–large.
  - **Effort:** medium–large.
- [ ] **Bio retention tuning** — the 12-entry cap drops `dialogue` entries first; tune the drop order once real
      conversation volume shows what players care about keeping.

### P2 — Quality of Life

- [ ] **Incremental `ty` cleanup** — run `ty` on touched Python files and resolve clear, local diagnostics as part of
      ordinary changes. Keep this non-blocking and avoid widening feature work solely to chase pre-existing type debt.

---

## Planned

> Completed work lives in `CHANGELOG.md`; this file is future-plans-first.

### Boosted Vault Rarity & Race/Faction Diversity — remaining scope (HIGH PRIORITY)

**User request**: boosted vaults should feel special, and vaults should not be 100% human. Boosted seeding landed,
but the diversity targets below are still open.

- [ ] **Boosted vault rarity boost** — vault initiation already seeds more dwellers (and apprentices) for boosted
  vaults; extend the seeding tables so boosted vaults get a higher rare/legendary share than the normal roll.
- [ ] **Race diversity targets** — non-human share in seeded/generated populations: **~15% ghouls, ~10% synths,
  ~5% super mutants** (humans the remaining ~70%). Apply to vault initiation seeding and radio recruitment
  rolls; breeding inherits race from parents (ghoul/synth/mutant lineages stay consistent).
- [ ] **Faction assignment** — seeded dwellers get lore-plausible factions from the existing faction options
  (vault_dweller dominant, others rare), so the identity dossier and future faction perks have data to work
  with.
- [ ] **Consistency** — race/faction live in `visual_attributes` today; the Race & Faction Gameplay Mechanics
  fragment is where modifiers/perks hook in. This item only diversifies **who exists**; it does not change
  mechanics.

**Reuse:** vault initiation seeding, radio recruitment rolls, `backend/app/options/` race/faction definitions,
breeding service. **Blocker:** none hard — seeding tables and roll weights are self-contained; coordinate with
the identity-metadata work so race is read from one source of truth.

### Outfit SPECIAL Bonuses — SHIPPED (v2.123.0)

Outfit SPECIAL bonuses are live: `models/outfit.py` carries `strength`…`luck` (0-7),
`utils/item_factory.build_outfit` maps catalog values, and `effective_stat` folds the equipped outfit's
bonus in. The bonus is effective-only, never persisted: 10 stored + 5 outfit = 15 effective, not capped.
Migration `alembic/versions/2026_09_18_0003-c3d4e5f6a7b8_add_outfit_special_bonuses.py`; tests in
`tests/test_services/test_outfit_special_bonuses.py`; evidence commit `b80231af`.

### Dweller Detail — Item-Improved Stats Display (idea, Target: TBD)

Show on the dweller detail page which stats are improved by equipped items. Outfit SPECIAL bonuses are
effective-only today (`effective_stat` folds the equipped outfit's bonus in, never persisted) — surface the
item-derived portion (base vs effective, e.g. "STR 10 → 15 (+5 from Vault Suit)") so an overseer can see why
a stat reads higher than the dweller's stored SPECIAL. Effective-only presentation, nothing persisted;
coordinate with the identity-dossier work so the presentation is shared rather than page-local.

### Radiation & Medical Reliability

The irradiated-water overhaul shipped: drought radiation accrues at 1% of max health per tick after a grace period,
saturates at the dweller's own `max_health` (never a flat cap, and it no longer kills), and is cured by the one-shot
**Treat Irradiated Dwellers** action. Outfit resistance applies to external radiation only, because drinking the water
is the ingestion path. Invariants live in `docs/backend/GAME_MECHANICS.md`; the mechanics reference is
`docs/backend/RADIATION.md`. Remaining work:

- [ ] **Rad-X** — design and implement a distinct temporary radiation-resistance treatment; define stacking,
  duration, inventory ownership, exploration behavior, and player-facing progression feedback before adding it to
  loot or production.
- [ ] **RadAway economy check** — a saturated dweller needs roughly two doses to clear, so confirm Medbay output and
  storage cap keep treatment affordable at realistic dweller counts; tune the recovery action if playtests disagree.
- [ ] **Dweller assignment policy on the update path** — `PUT /dwellers/{id}` still accepts `room_id`, so a client can
  bypass room capacity and assignment rules; route it through the shared assignment policy or drop the field in favour
  of the dedicated move endpoints.

### Contamination Team — fire & radiation responders (SHIPPED — mechanic + surfacing + hazard gear, Target: TBD)

A dedicated hazard-response outfit for the vault: a **fire team** that answers fire-hazard incidents —
kinda firefighters — and a **radiation incident response team** for rad leaks and irradiated zones.
Inspiration: UA "DUDES OF HAZMAT - Toxic Waste Chase" (music video) — hazmat-suit energy, sirens, toxic
chase vibes. Design doc: `docs/backend/CONTAMINATION_TEAM.md`.

**Shipped** (PR to `master`):

- **Team forming** — a dweller earns a place by fighting three incidents of a contamination type (fire,
  radiation); the first three hold the team, later qualifiers wait on a bench, and each milestone lands in
  `bio_entries`. Membership records identity, never position, so a future movement system consumes the
  roster instead of invalidating it. A fallen member frees their place to the senior bench member.
- **Participation ledger** — `incident_participant` credits each defender once per incident, inside the
  round's single commit, so a long incident cannot count twice and a failed round leaves no trace.
- **Outfit hazard resistance** — `fire_resist` / `radiation_resist` columns, fire resistance applied in
  `apply_damage`, a declared radiation share overriding the legacy type/name table, shown on item cards.
  Ships the **firefighter suit**, the **hazmat suit** the resist table had always anticipated, and the
  legendary both-hazard responder outfit.
- **Two fixes it depended on** — equip now invalidates the wearer's cached relationship (it had silently
  zeroed *all* outfit radiation protection, including power armor); runtime spawns roll from
  `game_config.incident.get_spawn_weights()` instead of hardcoding radscorpions, so `FIRE` — fully
  implemented with its own containment math — actually spawns.
- **Membership is now a mechanic** — active team members matter during their hazard incident: each
  active member present adds 20% to vault response/containment power (`TEAM_RESPONSE_BONUS`), and a
  matching active member takes 20% less incident damage (`TEAM_HAZARD_RESIST`; radiation-team members
  also take less radiation gain). Bench/reserve members get no bonus; non-matching or non-hazard
  incidents are unaffected.
- **Surface the join** — joins, bench places, and bench→active promotions create a
  `HAZARD_TEAM_JOINED` notification and surface as a toast in addition to the bell, closing the
  progression-visibility red-line gap.
- **Hazard gear** — boosted vaults start with spare Firefighter and Hazmat suits in storage, and a
  dweller earning an ACTIVE place on the matching team is auto-equipped with an available spare (fire
  team → Firefighter suit, radiation team → Hazmat suit). Bench members are not equipped; there is no
  auto-unequip on leaving.

**Next, in rough order:**

1. **The ask** — the dweller raises their own bench promotion through chat when a place opens ("subtle but
   present", reusing the `ActionSuggestion` accept/dismiss card). Semantics still open: announcement,
   consent gate, or teammate suggestion.
2. **Dispatch** — deferred by design to the Jev classifier; until then the team is a designation.
3. **Firefighter art** — the firefighter suit currently reuses the engineer-armor asset as a placeholder;
   real turnout gear (helmet, reflective stripes) is uncommissioned.
4. **Real-time movement (long term)** — response gains latency, so *where* the team stands starts to
   matter; the team gets a home (Fire Station / Hazmat Bay) as a muster point rather than a roster.

### Incident pacing & spread + SSE round events (deferred from the incidents UI redesign)

The room-state combat overlay shipped (waves 1–3: `defeat` shape, `contain`/flame, aftermath + failure
surfacing; net source-LOC −221). Two tasks were explicitly deferred with their findings recorded; both need
sign-off before scheduling:

- **Pacing & spread** — cooldown floor (1h measured from the latest incident's `end_time`) then a linear spawn
  ramp: `chance_per_hour = min(cap, cap * hours_since_last / ramp_hours)` per tick, proposed `cap = 0.25` and
  `ramp_hours = 6` (~4%/h at 1h → 25%/h at 6h+). Re-enable spread (`max_spread_count = 5`, `spread_duration` 60s)
  with the escalation UI it produces (`rooms_affected > 1`), and reset the ramp baseline on return so absence
  never dumps an incident on login. **Every parameter is proposed, not agreed.** Touches `core/game_config.py`
  defaults, `combat/incident_spawning.should_spawn_incident`, spread re-enablement + escalation UI, and
  cooldown/ramp/spread test coverage.
- **SSE round-event publishing** — push per-round events from `combat/incident_round.process_incident` (same
  numbers already written to the journal) so the battle log updates without the 5s refresh. Must satisfy the
  reconciliation contract first: monotonic per-incident sequence (the journal order, not the UUID), de-dup after
  reconnect, strict sequence ordering (never arrival), and a refetch fallback from `incident.events` — the journal
  stays the source of truth, the stream is an optimisation.

### Shared roster machinery — one roster model for quest, incident, and hazard teams — SHIPPED (#683)

`Team` / `TeamMember` is now the single roster primitive: quest parties, incident responder crews, and the
earned hazard teams all ride it, with the shared availability/eligibility policy in
`utils/dweller_availability.py`. `Team` gained a third purpose (`hazard_team`), active hazard places map to
`slot_number` 1-3 and the bench to a NULL slot, and the standalone `HazardTeamMember` table was migrated
across and dropped. The contamination/hazard naming split is retired internally (service/endpoint modules);
the public roster route and schema names are unchanged.

### Version 3.0 Platform Modernization

3.0 will be a deliberate runtime and tooling boundary — Python 3.14, native TypeScript 7, UUIDv7 identifiers —
rather than a routine dependency refresh. The work should
land as one compatibility pass with migration notes, updated CI/container tooling, and a rollback plan.

- [ ] **Python 3.14 baseline** — raise the supported backend runtime from the current 3.12–3.13 range, then verify
  FastAPI, Pydantic, SQLModel, Dramatiq, database drivers, and production images across the supported environments.
- [ ] **UUIDv7 identifiers** — use Python's standard-library `uuid.uuid7()` for new time-sortable identifiers where
  it improves database locality; preserve existing IDs and define the PostgreSQL/default/migration strategy before
  changing model factories or public API contracts.
- [ ] **HTTPX 2 evaluation** — test the HTTPX 2 API and compatibility with FastAPI's test transport and application
  integrations; adopt it if the release and dependency ecosystem are ready, otherwise stay on the latest supported
  stable release and record the decision.
- [ ] **TypeScript 7 (native) transition** — the frontend rides the TypeScript 6 bridge (`^6.0.3`); when the TS 7
  native compiler (`tsgo`) is stable, switch the typecheck gate, `vue-tsc`/Volar, type-aware Oxlint
  (`oxlint-tsgolint`), and `openapi-typescript` onto it and re-baseline the typecheck gate. Volar's adoption of the
  native API is the compatibility gate — keep the TS 6 bridge until then.
- [ ] **Transactional command integrity** — make every player economy/state command that reads then writes shared
  state atomic. Start with revival (the current separate caps and dweller commits permit a concurrent free revive),
  then cover the existing medical and breeding lock follow-ups. Lock the authoritative vault/dweller row, perform
  all mutations in one outer transaction, and prove each boundary with a real-PostgreSQL concurrency test.
- [ ] **Durable command idempotency** — deduplicate retried state-changing REST commands with a PostgreSQL record
  keyed by authenticated user, command/route, and an idempotency key; return the recorded result for a duplicate.
  Apply this before expanding revival, claiming, trading, quest, and world-map commands. Redis-only or process-local
  deduplication is insufficient because retries can cross workers or deployments.
- [ ] **End-to-end observability** — extend the existing Logfire setup beyond Pydantic AI to instrument FastAPI,
  SQLAlchemy/asyncpg, Redis, Dramatiq, and outbound HTTP. Trace a player action from request through transaction,
  queue, and WebSocket notification; scrub tokens and player content before export, define error/latency alerts, and
  do not add a parallel Sentry pipeline unless Logfire demonstrably cannot meet an alerting need.
- [ ] **Vue server-state pilot** — trial `@tanstack/vue-query` in one data-heavy module (dwellers or crafting) while
  retaining Pinia for client/UI state. Evaluate query caching, mutation invalidation, retries, polling, and optimistic
  updates against the existing bespoke loading/error flows before any wider migration.
- [ ] **Password-hash modernization** — evaluate `pwdlib[argon2]` as the new-password default; retain verification
  for existing bcrypt hashes and upgrade a hash only after a successful login. Do not force-reset accounts merely to
  change algorithms.
- [ ] **3.0 upgrade rehearsal** — update `uv.lock`, `pnpm-lock.yaml`, CI, development tasks, container images, and
  documentation; run the full backend/frontend suites plus migration and rollback checks before declaring the
  boundary complete.
- [ ] **Tauri desktop app** — package the existing Vue UI for Linux and Windows, connecting to the hosted FastAPI
  backend over HTTPS with secure real-time connections; backend services and data stay on the server, and the app
  requires an internet connection. Configure desktop origins/CORS, login persistence, reconnect behavior, and
  external links; validate installable builds against the hosted backend. Evaluate macOS, native notifications,
  and automatic updates as follow-ups.

Python 3.14 is the first version with standard-library UUIDv7 support, making it the natural point to evaluate the
identifier change rather than adding another compatibility dependency now.

### Frontend Design-System Consolidation (Target: TBD)

**Focus**: Make the terminal UI coherent by having shared primitives consume the same surface, spacing, border, and
interaction tokens instead of compensating with page-level CSS.

- ⬜ Define and document the canonical canvas, panel, inset-control, hover, and overlay surface roles.
- ⬜ **Grey-surface policy (recorded 2026-09-20)** — grey backgrounds on quest/objective cards silently
  disappeared during an earlier styling pass. Decide deliberately which UI parts carry a grey surface, on what
  condition (card kind, state, emphasis tier), and which shade, then enforce it through the surface-role tokens
  above instead of per-feature CSS. Purely a future design decision — no immediate change.
- ⬜ Align `UButton`, `UInput`, `USelect`, `UModal`, cards, and badges to those roles, including visible focus and
  disabled states.
- ⬜ Replace repeated feature-local button and control styling as related screens are touched; favor smaller shared
  variants over new one-off CSS.
- ⬜ Add an icon affordance to form labels where it makes an identity or game concept easier to scan, while keeping
  labels as the accessible source of meaning.

#### Intent & emphasis adoption (see STYLEGUIDE → "Intent & Emphasis Semantics")

- ⬜ **Long tail** — ~30 files still hand-roll glow values (~150 declarations, ~15 distinct radii). Convert to the
  token scale as each screen is touched; replace Tailwind arbitrary `text-shadow-[…]` values on sight; hover
  responses on non-interactive surfaces get removed in the same pass.

**Success criteria**: new management screens can be assembled from shared primitives without custom surface fixes,
and equivalent controls look and behave the same across the vault.

### Frontend Component-Library Migration — shadcn-vue (P1, started 2026-09-22)

**Focus**: replace the 16 hand-rolled primitives in `frontend/src/core/components/ui/` with
[shadcn-vue](https://www.shadcn-vue.com/) (Reka UI + Tailwind v4, copy-paste ownership) so behaviour and
accessibility stop being bespoke. Full migration: `U*` files are deleted as their consumers move; feature code
imports shadcn primitives directly.

**Scale (verified 2026-09-22):** 188 `.vue` / 39,655 LOC; 16 primitives (1,473 LOC); 150 raw native controls
across 64 files; ~320 arbitrary-value utilities; 123 files with scoped `<style>`; ~48 component/view test files
assert exact Tailwind classes; no visual-regression net. Effort: **Large (10–16 weeks)**, deliberately chosen
over the cheaper 3–6 week "reka-ui inside the `U*` wrappers" path.

**Accepted tradeoffs:** `SidePanel`, `VaultPageShell`, `TerminalMetric`, `RewardCard`, and `PageHeader` have no
shadcn equivalent and stay bespoke; shadcn's `@layer base` reset must be trimmed, not adopted verbatim, or it
repaints the CRT theme; the a11y payoff is per call site (each of the 150 raw elements is migrated
individually); six new UI dependencies must be offset by a net LOC reduction.

Plan: `.omo/plans/shadcn-vue-component-library-migration.md` · Skills: upstream `shadcn-vue` (generic) +
repo overlay `.agents/skills/shadcn-vue-repo/SKILL.md` (CRT token bridge, Vite+/pnpm constraints, migration rules).

- ⬜ **Phase 0** — toolchain + theme-bridge spikes on one `Button`; visual net (dev `ui-catalog` route + aria
  snapshots); mount helper; characterisation tests for the 7 untested primitives; CI freeze on class-assertion
  tests.
- ⬜ **Phase 1** — deps + `cn()`/tailwind-merge extension; token-alias layer; trimmed base reset; delete the
  legacy `--color-primary/secondary/accent` writes in `useTheme` *(done 2026-09-22)*; fix the non-scoped
  `.scanlines` collision in `DwellerChat.css` *(done — renamed `.chat-scanlines`)*; `scripts/shadcn-post-add.mjs`
  + pinned vite override. Legacy-alias collapse moved to Phase 4 (re-measured 50 files / ~160 occurrences;
  repo policy is per-screen conversion and class-asserting tests make a sweep noisy).
- ⬜ **Phase 2** — leaf primitives (`Button`, `Input`, `Badge`, `Card`, `Alert`, `Skeleton`, `ProgressBar`,
  `IconButton`) + first module (`ai-settings`).
- ⬜ **Phase 3** — interaction tier (`Modal`→`Dialog`, `Select`, `Tooltip`, `Tabs`, `Slider`) with behavioural
  E2E and focus/portal QA.
- ⬜ **Phase 4** — module rollout smallest→largest: storage, crafting, trading, auth, chat, map, social, vault,
  profile, progression, rooms, dwellers. Each module also converts its legacy-alias classes (`terminal-*`,
  `surface-warm/light/dark`) to canonical tokens as it is touched.
- ⬜ **Phase 5** — cleanup: dead CSS, class-assertion conversion, delete the `main.ts` registration loop +
  `global.d.ts`; require net LOC reduction.

**Kill criteria:** no facade deletion by end of Phase 3 with >60% of features still importing `U*` → declare
facets permanent; test rework > ~1.5× component rework for 3 consecutive primitives → freeze and batch-convert;
base reset still regressing after 2 targeted fixes → drop the reset and go primitives-only.

### Room Detail Part Registry (Target: TBD)

**Focus**: Consolidate how the room detail modal decides which sections exist. Today "does this room have part X" is
answered by three implicit mechanisms — category checks (`isArenaRoom`), name string-matching (`isOverseersOffice`,
vault door, radio), and derived computeds (`productionInfo`) — scattered across `RoomDetailModal`, its composables,
and `RoomActions`. Replace them with one explicit, ordered part registry.

- ⬜ **Phase 2 (separate product decisions, think first):** whether further compositions should unify where it makes
  sense — e.g. arena also showing info/dweller list — decided per part, not bundled into refactors. A full
  component-map renderer (replacing the `has(part)` gates) can ride along when a second composition change lands.

**Non-goals:** backend-declared parts (rooms.json describing UI layout — presentation stays a frontend concern); a
`role`/`slug` column on built rooms (migration for zero behavioral gain; seed-data-stable names stay, centralized);
extending the registry to `RoomGridCell` or the build menu (revisit only if the pattern proves itself).

**Success criteria**: adding a room type means adding one registry entry plus its part components; part composition
per room type is asserted by tests; no category or name checks remain outside the registry.

### Dweller Identity & Atmosphere Update (Target: TBD)

**Focus**: Turn the existing `visual_attributes` JSONB data and `backend/app/options/` lore into a legible, animated
identity layer across the vault—without adding new gameplay rules or duplicating option definitions.

- 🔄 **Typed identity metadata** — expose race, faction, state-of-being, and compatible option metadata from the
  existing options modules; validate race/faction combinations whenever visual attributes are saved.
- 🔄 **Identity dossiers** — add reusable race/faction insignia, lore-aware labels, and compact state descriptions to
  dweller cards, grid items, quest parties, exploration, and the dweller detail view.
- 🔄 **Badge & tooltip unification** — identity badges (race, faction) and demographic badges (rarity, gender, age)
  currently mix tooltip implementations (`UTooltip` vs native `title`) and visual treatments; consolidate on one
  badge component and one tooltip pattern, keeping the styleguide's informational intent (`--glow-0`, no fill).
- 🔄 **Appearance presets** — offer the existing archetypes (Vault Dweller, Brotherhood Knight, NCR Ranger, Ghoul
  Mercenary, Institute Courser, and others) as previewable appearance-editor presets; presets only populate visual
  attributes and never grant equipment or stats.
- 🔄 **Terminal motion polish** — use restrained CRT signal sweeps and faction/race accents, with reduced-motion
  support; legendary, ghoul, and synth variants should be distinctive without becoming noisy.

**Delivery**: first ship backend metadata/validation with tests, then apply the shared identity-dossier component to
existing frontend surfaces with component tests.

**Success criteria**: an overseer can immediately recognize a dweller's identity wherever that dweller appears, edit
only lore-valid combinations, and apply a preset safely—while users who prefer reduced motion see a static interface.

### Dweller Domain Schema Composition (Target: TBD)

**Focus**: Gradually make the dweller API domain easier to evolve by composing focused schemas—identity/visual,
vitals, combat, and social/lineage—while retaining a single `Dweller` database aggregate and table unless a concrete
storage lifecycle requires otherwise.

- ⬜ Extract focused Pydantic read/input schemas only where an active feature benefits from them; do not split the
  SQLModel table, CRUD ownership, or migrations speculatively.
- ⬜ Compose compact and full API responses from those shared schemas without changing existing client contracts.
- ⬜ Move the visual identity schema as part of the Dweller Identity & Atmosphere work when it removes duplication;
  defer vitals, combat, and social extraction until their respective workstreams touch them.

**Success criteria**: each dweller concern has one clear schema owner, API contracts remain backward-compatible, and
the database remains simple until its shape demonstrably needs to change.

### Dwellers Table View — Configurable Columns (Target: TBD)

**Focus**: Give the Dwellers tab a roster-style **table** view: one dweller per row, aligned and sortable columns,
with the player choosing which columns to show. Today the tab offers `viewMode: 'list' | 'grid'`
(`stores/dwellerFilter.ts`); `DwellerListRow` is a flex card row (portrait, name/level, identity badges), not an
aligned grid, and it cannot be compared column-by-column.

**Proposed columns** (grouped so related data reads together):
- **Identity** — portrait, first name, last name.
- **Demographics** — gender, age group, rarity (grouped as one badge cluster).
- **Progression** — level.
- **Vitals** — current/max HP, happiness.
- **Assignment** — room (or unassigned), status (idle, working, exploring, training, on quest).

**Configurability** (brainstorm target):
- Per-column show/hide persisted with the existing filters; sensible default set (portrait, name, level, status,
  room).
- Column presets for common intents ("Roster", "Vitals", "Assignments") instead of making everyone build a layout.
- Sticky header; row click → dweller detail; reuse `DwellerPortrait`, `DwellerRarityBadge`, `DwellerGenderBadge`,
  `DwellerAgeBadge` rather than new badge variants.

**Open questions for the brainstorm:**
- Add a third `viewMode: 'table'`, or replace the current list mode with the table?
- Which columns survive small screens — responsive subset, or horizontal scroll?
- Sorting/grouping: by level, name, room, status, rarity? Group-by-room to mirror the vault layout?
- Does the table need multi-select to feed the existing bulk actions (`DwellerBulkActions`)?

**Non-goals** (unless the brainstorm says otherwise): new backend endpoints or schema changes — every column
derives from existing compact dweller responses; an editable spreadsheet grid.

**Success criteria**: an overseer can scan and compare dwellers at a glance, pick the columns that matter, and have
that preference persist — without regressing the existing list/grid modes.

### World Map — Single-Vault Exploration (Target: TBD)

**Focus**: Preserve the wasteland map as a legible, per-vault exploration surface: discoveries, routes, and journal
context for the player's own dwellers. Feature contract: `docs/features/WORLD_MAP.md`; delivery plan:
`docs/WORLD_MAP_PLAN.md`.

**Navigation note (accepted debt):** the map is currently a **separate top-level menu item**. That is fine for
now, but it should eventually move **under Exploration** — the map is an exploration surface, not a peer of
it. Design deferred; decide the navigation shape when the exploration module next gets attention.


- 🔧 **Deployment parity** — deploy the v2.46.1 Dramatiq worker image with the discovery-unlock fix so new
  discoveries unlock live (the currently deployed worker runs pre-fix code).
- 🔧 **Easy: radiation trend in the journal** — `radiation_gain` is already persisted as a structured event
  field (`Exploration.add_event`, `event_service`), but the journal ignores it (`useExplorationHealthJourney`
  parses damage/healing out of description text), and RadAway auto-use records removal only in description
  text — unlike Stimpak's structured `health_restored`. Steps: add `radiation_removed` to `add_event` and pass
  it from `_handle_auto_heal`, extend the journey composable with a radiation series from structured fields,
  no migration (JSONB). Tests first, per the bugfix workflow.
- 🔧 **Easy: Celldweller landmark** — one seeded discoverable location with one-time loot, reusing the
  existing easter-egg pattern (`GaryOverlay`, `FakeCrashOverlay`, rename trigger). Optional, non-gating,
  never blocks progress.
- 📋 **Planned (harder): exploration events with player choices** — phases: (1) `ChoiceEventSchema`
  (prompt + options with previewed trade-offs); generator emits, journal renders, resolution is deterministic
  under the exploration seed; (2) 2–3 choice templates reusing existing combat/loot/danger outcomes — no new
  mechanics in phase 1; (3) SSE delivery plus auto-resolve with a documented default on recall/complete.
  Out: branching chains, live multiplayer effects.

Feature description: `docs/features/WASTELAND_JOURNAL.md`; delivery checklist and verification:
`docs/WORLD_MAP_PLAN.md`.

**Out of scope:** multiplayer **state** — live world simulation, async-PvP raids, cross-vault fallen dwellers,
friends, visits, and leaderboards — remains unplanned; revisit only with a separate product direction. The shared
places registry is explicitly in scope as the foundation those features would build on, without optimizing the
registry itself around them.

**Guardrails:** keep per-vault discovery/unlock state vault-local; the registry owns only shared geography (name,
coordinates, canonical lore) and no live simulation; respect the v2.35+ net-LOC constraint (claw back per-vault
nudge machinery and the duplicated place-name sources as the registry lands).

**Success criteria:** the near-term release delivers a legible per-explorer journey (loot + health-change trail +
map route), discovery events deep-link to their map marker, and neighbor vaults sit at globally-consistent
coordinates — all test-backed.

### Generic Wasteland Location Groups — Chains & Site Types (Target: TBD)

**User request**: exploration places should include the wasteland's recurring generic fixtures, not only unique named
locations — Red Rocket, Super Duper Mart, and the rest of the lore's chains and site types.

**Current state:** `backend/app/data/places/seed_places.json` holds 67 rows with `kind` of `place` (62) or `vault`
(5) — Adams Air Force Base, Diamond City, Concord, Red Rocket, … Each name is effectively a one-off row, so a place
can only exist once and new content means hand-authoring another named entry.

- ⬜ **Encounters & loot by group** — exploration event tables key off the group so a gas station plays differently
  from a military base, and balance edits land in one place.
- ⬜ **Quest and bio references** — content already names these places (`power_struggle.json` sends the player to
  the Super Duper Mart, and the bio-place backfill regex lists resolve place names), so resolve references through
  the group and keep authored quest text working as instances are added.

**Dependencies:** builds on the shared places registry (`WorldLocation` + `PlaceKindEnum`, shipped v2.83/v2.84) and
the seed strategy in `docs/WORLD_MAP_PLAN.md`. Extend `PlaceKindEnum` or add a sibling group field — do not
introduce a second world model.

**Open questions:** group as an enum (migration-guarded) vs a seeded table (content-editable); whether a group
implies a preferred map region or biome; how many instances a group may spawn; whether generic groups can be
discovered per-instance or unlock as a family.

**Success criteria:** exploration can encounter multiple distinct Red Rocket / Super Duper Mart instances sharing
group lore and encounter behaviour, and adding a new site type is a data change rather than code.

### Stalker Easter Eggs — the Quiet Zone (Phase 1 implemented; Phases 2–3 planned)

**Focus**: a layered, **ambiguous homage** to STALKER's Zone — never a canon claim. Players should recognize the
inspiration, never be told it literally exists in Fallout. Full design record and canon-safety rules:
`docs/STALKER.md`. The essence: *an ugly, fenced, irradiated place somewhere in the wasteland. Some people claim
it produces miracles. Most people who say that want to sell you something.*

**Phase 1 — implemented on branch `feat/stalker-easter-eggs` (pending PR):**

- `exclusion_zone` place group ("Restricted Exclusion Site") plus one seeded location, **The Quiet Zone**
  (`roles: ["visited"]`, group `exclusion_zone`) in `data/places/`.
- A discovery route: Moira Brown's curated `visited_places`/bio include The Quiet Zone, so recruiting her
  registers the marker through the existing `map_service.register_bio_places` path.
- Rare generated-bio rumours (`options/bios.ZONE_RUMORS`, 8 deniable first-person lines) gated by
  `bio.zone_rumor_chance` (default `0.05`, env `BIO_ZONE_RUMOR_CHANCE`), seed-reproducible and text-only
  (never touches `_bio_places`).

**Planned:**

- [ ] **Phase 2 — discovery flavour** — 1–2 tested exploration templates ("The Bolt Test", "The Red Sky"),
  several discovery names ("The No-Return Fence", "The Glass Orchard"), and a few low-value curios. Any item
  must be built through `utils/item_factory.py` (the guard test fails otherwise) and matched by
  `schemas/quest.py`'s consumable-token list if it can be granted as a reward.
- [ ] **Phase 3 — optional depth** — terminals, radio fragments, collectible survey notes, and the fake
  "wish-granting" corporate terminal. Keep every explanation contradictory.

**Rules:** no STALKER canon names, factions, creatures, or artifact names; "anomalies"/"artifacts" stay
unverified local terminology; no rewards that prove reality-warping mechanics; text-only until real mechanics
are deliberately designed.

**Not part of this group:** vodka and Nuka-Cola "Non-Stop" belong to the consumables-behaviour work — vodka must
not replace RadAway (`docs/backend/GAME_MECHANICS.md`: "RadAway is the only cure").

### Next Big Feature — Family Relations (future phases — foundation shipped)

**Focus**: Make the existing breeding/relationship systems into a visible family experience: family trees,
relationship depth, and legacy that persists across generations. This is the natural successor to the breeding
cooldown and naming fixes.

**Already shipped (v2.42.0+ — foundation, do not rebuild):**

- 🔲 **Phase 1 — graph visualization.** Replace/augment the rows panel with a real graph (parents →
  dweller + partners → children, multi-generation). Reuse lineage API as-is; no backend change. Extract
  shared lineage/tree helpers instead of duplicating traversal logic.
  **Design reference (recorded 2026-09-20):** model the tree after The Sims' family tree — horizontal
  generation rows, head portraits (small circular) connected by vertical parent→child lines, partners
  side-by-side with a link between them. The same shape should later serve the vault-level family graph
  on the relationships page.
- 🔲 **Phase 2 — stage-change celebration.** Relationship stage upgrades (especially MARRIED) currently pass
  silently except happiness math. Surface them under the progression-visibility red line: modal/toast +
  notification, same as quest/objective completion. Backend already emits the transitions; this is frontend
  surfacing + regression tests.
- 🔲 **Phase 3 — legacy & lineage.** Surface generation number, house/family name, and inherited traits
  (`_calculate_inherited_stats`) on dweller detail; consider a "founder's vault" distinction.
- 🔲 **Phase 4 — postpartum tuning.** Play-test the 6h `birth_cooldown_hours` default against high-affinity
  couples and adjust before building on top of it.

**Guardrails:** delegate to the service layer (never CRUD directly) so events, notifications, and game-loop side
effects fire exactly as they do for REST calls; respect the v2.35+ net-LOC-reduction constraint by extracting shared
lineage/tree helpers instead of duplicating map-marker logic.

**Success criteria:** a player can open any dweller's family graph, gets a visible celebration on stage
changes, and can identify multi-generation lineage from the detail view — with backend coverage for the tree and
stage-transition logic.

---

### Overseer Reports — CodeRabbit Review Follow-ups (Target: TBD)

**Focus**: Follow-ups from the CodeRabbit review of the Overseer Reports PR (#449). The two stability fixes shipped
with the PR (incident victory notification now fires only after the incident commit succeeds; `notify_owner`
swallows vault-owner lookup failures). The remaining items were deferred or recommended for a follow-up.

- 🔄 **Breeding capacity concurrency** — `check_for_conception` reads `available_slots` without locking, so two
  concurrent ticks can each reserve the last free slot and over-commit pregnancies. Enforce the capacity check and
  the pregnancy insert in one transaction (`SELECT ... FOR UPDATE` on the vault row), at the `create_pregnancy`
  boundary so every conception path is covered. Heavy lift; the in-memory SQLite test harness cannot exercise row
  locks today.
- ⚪ **Nitpicks (optional)** — route exploration-completion notifications through `notify_owner` for consistency with
  the other flows; wrap a >100-char line in `exploration.ts`.

**Guardrails:** keep the resolution-notification ordering fix (notify only after a successful commit) intact when
touching incident handling; any breeding change must keep `population_max=None` unbounded.

---

### Pydantic AI Reliability & Observability — open follow-ups

- 🔄 **Activate Pydantic AI Gateway for chat and agents**
  - Configure the deployment-only `PYDANTIC_AI_GATEWAY_API_KEY`; the existing gateway model path becomes active without
    changing agent code.
  - Retain `OPENAI_API_KEY` for native image, TTS, and transcription APIs, which remain direct OpenAI integrations.
- 🔄 **Measure before/after**
  - Baseline and report deterministic agent-contract test count, output-validation retry coverage, and Logfire trace
    completeness for one normal chat and one tool-using chat.
  - Guardrails: no agent framework major-version migration, no gameplay-rule change, and no real-provider calls in the
    unit test suite.

---

### AI Layer Upgrade — Prompts, LLM Interactions, Admin & New Usage (Delivered through Plan 4 — see `docs/backend/AI_LAYER_PLAN.md`)

**Focus**: Make the AI layer observable, configurable, and cheap — per-consumer decision whether Pydantic AI agents stay, get upgraded, or get replaced with deterministic paths. Plans 0–4 are delivered (objective-endpoint lockdown, `LLMInteraction` metadata snapshots, immutable prompt registry, usage analytics, sqladmin views); Plans 5–6 remain parked.
- 🔜 **Plan 4.5 — AI control surfaces** — player quick wins: explain monthly AI use in Profile → Analytics and show a
  calm in-chat budget signal; operator quick wins: searchable/filterable prompt and interaction audit views. Reuse
  delivered API data; defer player interaction search, cost estimates, daily graphs, polling, and new endpoints until
  privacy/retention needs are decided. Next low-cost UX follow-up: empty-chat conversation starters derived from a
  dweller’s known places; chips prefill but never auto-send. Future content-quality follow-up: separate human, ghoul,
  synth, and super-mutant bio prompt/template variants, selected from existing dweller identity with no extra runtime
  call. See `docs/backend/AI_LAYER_PLAN.md`.
- ⏸️ **Plan 5 — Pre-generation shift (LM Studio/ComfyUI batch → curated content)** + **Plan 6 — New AI usage ideas** (incident narration, quest flavor, daily digest, dweller ambient chat) — parked, need product decisions + per-operation usage headroom before shipping.

**Guardrails:** no Pydantic AI framework migration, no per-request model/temperature per prompt, no retroactive cost truth; template-first.

---

### TypeSafe Jev Classifier — Dweller Combat Triage & Radiant AI (Proposal, Target: TBD)

**Focus**: Wire TypeSafe Jev (classifier, not a language model: text in, typed judgements out, per-field
confidence) into dwellers — not chat, but combat decisions and "radiant AI" living-sim. Full model docs:
`https://pydantic.dev/docs/ai/models/typesafe/`. Complementary to the dweller chat agent — it does NOT replace it.
Design doc: `docs/backend/JEV_CLASSIFIER.md`.

**Model shape to respect:** prompt = material judged, question = field description; one judgement per field
(`bool` yes/no, `Literal`/`Enum` pick-one, `float` probability, `list` fan-out, nested `outer.inner`).
Confidence per field in `provider_details`; pick the threshold per use (act automatically = higher bar) and
calibrate on own labeled data, then pin the version (`typesafe:jev-1.13.0`) — `jev-latest` moves. Jev is bad
at arithmetic/counting/dates, multi-judgement questions, indirection, bloated state, adversarial text, and
option-order shifts — so it triages, never resolves math.

- ⬜ **Radiant `radiant_tick` (recommended first)** — new self-rescheduling Dramatiq actor modeled on
  `arena_tasks.arena_tick` (Redis lease + `task_session()`); never inline per-dweller calls into
  `process_game_tick` (one shared session across all vaults). Online-gated via `game_state.is_user_online()`.
  State text reuses `chat_tools.build_dweller_social_context` / `build_dweller_activity_briefing`; judgement
  schema modeled on `DwellerChatOutput` (e.g. `wants_rest` / `wants_social` / `wants_change` bools, or a
  pick-one activity `Literal`). Feeds `dweller_assignment_service`, `happiness_service`, and
  `exit_request_service.sync_despair_requests`; below-threshold confidence falls back to the deterministic
  formula. Surfaces via `notification_service.create_and_send` under the modal/toast red line.
- ⬜ **Combat triage (narrow seams only)** — incident-spawn triage (`incident_spawning.spawn_incident` /
  `notify_spawn`: `Literal['hold','reinforce','evacuate']` + confidence, hours-scale budget, safe);
  exploration engage/avoid (`exploration/combat_calculator.calculate_combat_outcome`, 10-min budget behind the
  existing `to_thread` boundary, formula fallback); responder suggestion (`incident_service.assign_responders`,
  player-facing ranked subset). Explicitly out: synchronous calls in `incident_round.process_incident` (2s
  all-vault advisory-locked tick), arena rounds, quests (timer-only, no combat).
- ⬜ **Measure before shipping** — accuracy, hand-off rate, and threshold on own labeled dwellers/incidents;
  wire cost through `ai_usage_service` before rollout. No-arg tools Jev can call alone get the
  `parse_action_suggestion`-style policy re-check plus `UsageLimits(request_limit=...)`; tools with args go
  behind `FallbackModel` with a language model.

**Reuse:** `DwellerChatOutput` + `validate_dweller_chat_output` (typed judgement contract),
`parse_action_suggestion` (guarded judgement → action), `AIService.get_model`, `LLMInteraction` logging,
`quota_service`, append-only `Prompt` registry (`version-prompt radiant_behavior`), `event_bus` + SSE topics.
**Guardrails:** deterministic resolvers stay in `incident_math.py` / `utils/combat.py`; new module named
`*_service.py`; CRUD owns queries (no raw `select()` in services); tick path uses `await session.execute(...)`
never `.exec()`; endpoints stay thin with `verify_dweller_access`.

**Success criteria:** idle/resting dwellers visibly want things and assignments reflect it without tick blowup;
incident spawn carries a calibrated triage recommendation; every Jev-driven outcome has a measured threshold,
a deterministic fallback, and test-backed surfacing — no per-tick network calls.

---

### Notification Delivery — Per-Tick Batching (Idea, Target: TBD)

**Focus**: Cut real-time delivery churn and make notification creation transaction-safe, without delaying urgent
surfacing.

**Idea (not yet designed):** server-generated notifications currently push one WebSocket **and** one SSE frame each,
so a busy tick can emit a burst of N frames, N re-renders, and N sounds. The `notification_service` deferral
primitive (`create_and_send(commit=False)` → `deliver_deferred_notifications()` / `discard_deferred_notifications()`)
also exists but is only wired into the incidents tick.

**Sketch to evaluate before building:**

- Split by priority: `URGENT`/`HIGH` keep immediate push; `NORMAL`/`INFO` coalesce into one per-tick batch payload.
- Frontend iterates the batch and plays the notification sound once per batch.
- Route **all** notification-producing flows through the deferred drain/discard primitive so a rolled-back
  transaction cannot leak or lose a notification (today only `incident_tick` is covered).
- Add a staleness cutoff on drain so returning from an offline stretch cannot dump a burst of stale toasts.

**Explicitly out of scope:** user-action confirmations (build/upgrade/assign success toasts) stay client-side; they
are synchronous responses to the caller's own request and gain nothing from a server queue.

**Constraints:**

- Must not violate the progression-visibility red line (`docs/backend/GAME_MECHANICS.md`): batched events still need
  modal/toast surfacing, never notification-only.
- Ticks are skipped while the vault owner is offline, so delivery timing must tolerate an idle queue.
- No double-surfacing against the existing SSE + polling + bell paths.

---

### Next Automated Release — Container Build Efficiency (Target: TBD)

**Focus**: Make release image builds faster and measure runtime-image size without changing deployment behavior.

**Planned:**

- 🔄 **Maximize reusable build cache** — replace the inline cache with a per-image registry cache in `mode=max` so
  dependency and intermediate multi-stage layers are reusable across ephemeral GitHub Actions builders.
- 🔄 **Measure before changing runtimes** — record cold and warm frontend/backend build-and-push durations plus
  published image sizes; `v2.35.0` is the initial timing baseline (26s frontend and 51s backend build-and-push).
- 🔄 **Reduce only demonstrated runtime overhead** — assess direct ownership on `COPY` for the backend and a minimal
  static frontend server only after smoke tests prove unchanged SPA routing and container behavior.

**Success criteria:** record exact before/after frontend and backend build-and-push durations plus published
image bytes, with the CI run or command used for each measurement; improve at least one metric without weakening tag
validation, cache isolation, or runtime behavior.

---

### AI Overseer — MCP Integration (Proposal, Target: TBD)

**Focus**: Expose game capabilities to external AI clients (Claude Desktop, Cursor, custom agents) through the Model
Context Protocol so an external "Overseer assistant" can read live vault state and issue high-level commands without
bespoke glue code. Full design in `docs/backend/MCP.md`. Complementary to the in-game dweller chat agent — it does
NOT replace it.

**Planned:**

- 🔄 **P0 — Read-only MCP resources** — `vault://{id}/state`, `dweller://{id}/bio`, `notifications://{user_id}` behind
  the existing JWT auth; no new tables or migrations.
- 🔄 **P1 — Safe action tools** — `assign_dweller_to_room`, `start_training`, `pause_game`/`resume_game`; routed
  through the existing service layer and quota service, with mutating tools gated behind human approval.
- 🔄 **P2 — Curated prompts** — `overseer_daily_briefing(vault_id)` and `vault_triage(vault_id)` prompt templates.
- 🔄 **P3 — Evaluate usage** — assess before adding exploration/room-building tools or a standalone bridge.

**Guardrails:** tools must delegate to services (never CRUD directly) so events, notifications, and game-loop side
effects fire exactly as they do for REST calls; in-game chat path unchanged; tool exposure is context management, not
access control — permissions live in the service layer.

**Success criteria:** an external MCP client can read live vault state and perform one safe action (e.g., start
training) with ownership checks and quota enforcement, while in-game chat behavior and test suites remain unchanged.
Resource authorization checks are part of the definition of done: loading `dweller://{id}/bio` requires resolving the
dweller and authorizing its vault (`get_user_vault_or_403` / `verify_dweller_access`), and `notifications://{user_id}`
must reject any identifier that does not match the authenticated user.

---

### Deferred Library Adoption (Reassess During a Related Feature)

- **FastAPI** — native SSE is already used; do not introduce `app.frontend()` for the separately deployed Vue SPA.
- **Pydantic / SQLModel** — the current PATCH flow already uses `exclude_unset=True`; consider `MISSING` only when an
  API genuinely needs to distinguish omitted values from explicit `null`, and use `sqlmodel_update()` only when
  touching the shared CRUD update path for another reason.
- **Tailwind CSS** — use newer semantic utilities such as native text shadows, safe alignment, pointer variants, or
  `@source inline()` only in the component that needs them. Avoid a formatting-only CRT-style rewrite.
- **Pydantic AI agent tool scaling** — the dweller chat agent's toolset is small and bounded
  (`DwellerActivityBriefing` already caps tool output); revisit only if the tool catalog grows well past ~10 tools:
  - **Search-then-execute** — replace "one schema per tool" with two tools (search for an action, execute by ID) so
    context stays flat regardless of catalog size.
  - **On-demand tool loading** — keep tools out of context until the agent actually needs them (harness-style
    `defer_loading`).
  - **Tool output limits** — cap oversized tool returns so a large export cannot eat the context window.
  - **Human approval on mutating tools** — gate write actions behind approval, distinct from read tools.

### Race & Faction Gameplay Mechanics (Target: TBD)

**Focus**: Make race and faction matter mechanically. Today they are purely cosmetic (`visual_attributes` JSONB +
AI appearance/backstory prompts + identity badges). The Combat Power Overhaul's per-type weight table is the hook:
racial modifiers and faction perks slot into the same stat-weighting shape instead of ad-hoc special cases.

- 🔄 **Racial stat modifiers** — shipped: one options-backed table (`RACE_MODIFIERS` in `options/races.py`) read
  through `options/identity_modifiers.py`, so combat, production and radiation all see the same rule with no
  per-system branching. Ghoul +2 END and radiation immunity, super mutant +3 STR/+2 END/−2 PER, synth +1 PER/+1 INT
  and 50% radiation resistance, humans the neutral baseline. Deltas are derived on read and never persisted.
- 🔄 **Faction perks** — shipped: `FACTION_PERKS` in `options/factions.py`, applied at the same choke points —
  Brotherhood +15% energy-weapon damage (Legion, Raiders and the Super Mutant Tribe get melee equivalents),
  Minutemen 15% less incident damage taken, Children of Atom +50% radiation resistance, Vault Dweller +5% and
  Institute +10% production. NCR and Railroad stay neutral until they have an honest mechanic.
  - **Remaining:** ghoul radiation healing over time; a perk for NCR/Railroad once an economy or stealth system
    exists.
- 🔄 **Dossier surfacing & filtering** — shipped: the computed modifiers ride on the dweller read shape and the
  dossier renders them under Identity Bonuses; and the appearance editor reads `GET /dwellers/identity-options`
  instead of keeping its own mirrored list — that mirror had already drifted (it offered
  `partially_feral`/`fully_feral`, which the backend never had). Filtering the roster by race and faction is
  tracked separately.
- ⬜ **Race in conversation (persona)** — how a dweller *writes and behaves*, not accent flavour: race sets a
  structured persona (register and sentence shape, lexical concreteness, emotional baseline, stance toward the
  player, topics volunteered versus dodged) appended at call time to the `chat`, `backstory` and `extend_bio`
  instructions, plus an action bias so the assignment or exploration a dweller reaches for fits its race
  (super mutants toward training and fighting, ghouls toward irradiated ground, synths toward technical rooms).
  Fallout 1/2's INT-gated dialogue is the model: SPECIAL should modulate the same persona dimensions later
  (INT → register and sentence shape, PER → observation, CHA → warmth, LCK → risk talk, STR/END → physicality,
  AGI → pace). Registry rows stay at v1 — templates reject placeholders, so the persona is composed outside the
  registry and no `version-prompt` is needed.
- ⬜ **Balance pass** — the deltas above are a first cut; revisit after play-testing normal, boosted and
  non-human-heavy vaults.

**Guardrails:** modifiers live in one options-backed source of truth; no new DB columns unless a modifier must
persist per dweller; balance pass after play-testing; net-LOC rule applies. The whole subsystem sits behind
`FEATURE_RACE_MECHANICS` (default on) and `FEATURE_FACTION_MECHANICS` (default off) in
`game_config.features`; each half reads neutral when off — ghoul radiation immunity predates both flags
and is kept either way.

**Success criteria:** race/faction choices change outcomes (combat, incidents, exploration) in legible ways, are
visible in the dweller dossier, and are covered by per-race/per-faction unit tests.

### Dweller Origins by Race — Reproduction, Radiation & Age Groups (Target: TBD)

**User request**: race should change more than stats — it should change where a dweller *came from* and what they can
do. Synths were not born, they were made; ghouls are pre-War survivors. That provenance should drive reproduction,
radiation response, and how age is modelled. Coordinates with **Race & Faction Gameplay Mechanics** (stat/perk
modifiers) and **Bio Extension** (bio templates) above; this fragment owns provenance and lifecycle.

- ⬜ **Origin model** — record *how* a dweller came to exist (born / manufactured / ghoulified / mutated) instead of
  inferring it from race. `RaceEnum` + `SynthTypeEnum` + `GhoulFeralnessEnum` + `SuperMutantMutationEnum` already
  describe state of being; provenance is the missing axis.
- ⬜ **Reproduction gating** — synths are manufactured and ghouls are sterile in lore, so breeding eligibility
  becomes a per-race rule read by the breeding service rather than the implicit "any adult pair". Breeding already
  inherits race from parents; this adds whether a pairing is possible at all, and what a mixed pair implies.
- ⬜ **Radiation response** — ghouls take no radiation damage (and may heal from it), gen-1/gen-2 synths are
  mechanical, gen-3 synths are biologically human, super mutants are highly resistant — all read by the
  radiation/tick path rather than scattered conditionals.
- ⬜ **Rule lookup dimensions** — rules are deliberately not race-only: radiation differs by synth generation, and
  lifecycle rules key off provenance. Key the table by `(race, state of being)` using the enums that already exist
  (`RaceEnum` × `SynthTypeEnum | GhoulFeralnessEnum | SuperMutantMutationEnum`), falling back to `(race, none)` and
  then to a human default. Lifecycle rules (reproduction, aging) key off provenance, which is derivable from the
  race/state pair for synths and ghouls but explicit for edge cases. Settle and document that precedence before
  implementation so no rule is expressed twice.
- ⬜ **Age groups per race** — decide what `AgeGroupEnum` means for a dweller who was never a child: synths are
  manufactured at an adult apparent age (track `manufactured_at` instead of a birthday), ghouls may not age
  conventionally, super mutants age differently again. Open questions to settle first: does a synth have
  `child`/`teen` rows at all; does a ghoul count as an elder; how do aging/youth/apprentice ticks skip races that do
  not age.
- ⬜ **Backstory provenance** — per-origin bio template variants so a synth bio reads as manufactured ("made in the
  Institute, got out") and a ghoul bio reads as a pre-War survivor, rather than both reading as born.

**Open questions:** provenance as its own column vs derived from `visual_attributes`; how mixed-race pairs (if
allowed) resolve offspring race; whether sterile races get adoption/apprentice paths so family features stay
meaningful for them.

**Guardrails:** one options-backed identity table keyed by `(race, state of being)` with a race-only fallback and
provenance for lifecycle rules; no per-system race branches; keep `RaceEnum` as the identity anchor so the
race/faction work above is not duplicated.

**Success criteria:** a synth cannot be bred or born and the dossier says why; a ghoul shrugs off radiation while a
gen-3 synth takes it like a human and a gen-1 synth takes none; age progression produces no nonsensical life stages
for races that do not age; unit tests exercise the same `(race, state of being)` → rule lookup the runtime uses,
plus reproduction eligibility and age progression.

## Planned Features (Future)

### Weapon & Outfit Crafting — Timed Queue (Target: TBD)

**Focus**: The two Crafting rooms (`Weapon workshop`, `Outfit workshop`) went from inert to functional with the
instant crafting ship below; the remaining work is the queue that makes them feel like Fallout Shelter's
workshops rather than a shop menu.

- ⬜ **Timed craft queue (FS-authentic)** — replace the instant grant with an order queue: dwellers assigned to
  the workshop speed completion, the tick advances progress, and the finished item is collected from the room.
  Reuses the `Training` session shape (`started_at` / `estimated_completion_at` / `progress` / `status`). Build
  only if the instant loop proves too frictionless in play-testing.

**Reuse:** item catalogs (`weapons.json`, `outfits/*.json`), `junk.json` + `convert_to_junk` scrap output,
`game_config` for costs, the shared item builders, `RoomTypeEnum.CRAFTING`, and the progression red line for
surfacing the craft result.

**Non-goals:** per-item authored recipes (costs derive from rarity for now); crafting `craftable: false` items;
pets.

**Success criteria:** a player with junk can craft a craftable weapon at the Weapon workshop and an outfit at
the Outfit workshop; materials and caps are consumed in one transaction; the result appears in storage
immediately.

### Phase 1: Core Gameplay

- Room management improvements (optimal dweller suggestions)

### Phase 2: Advanced Gameplay

- Combat enhancements (statistics, log/replay)
- Exploration enhancement (events with choices; "journal" is now the near-term Wasteland Journal release — see World Map plan above)

### Phase 3: Endgame

- Pet system, legendary dwellers
- Merchant system, economy
- Achievement system, daily/weekly challenges
- **Dead Dweller Reuse System** — parked; cross-vault encounters are out of scope under the single-vault exploration guardrail.
  - Soft-delete permanently dead dwellers (keep data)
  - ~~Reuse as raiders attacking other vaults~~ — out of scope
  - Transformation chance: ghoul, synth, super mutant
  - ~~Cross-vault encounters with former dwellers~~ — out of scope

### Apprentice System & Pets — design fragments (Issue #470)

Loose fragments from the #470 discussion, recorded so the decisions aren't lost.

- ⬜ **Production/crafting bonus** — scaled by the apprentice's accrued SPECIAL skill, not a flat percentage;
  the more skilled the apprentice, the larger the room efficiency bonus. Remaining follow-up.
- **Pets** — assign to **living quarters (`CAPACITY`)** and **training rooms (`TRAINING`)**; intentionally NOT production/crafting rooms (a pet in a power plant or diner makes no sense). Pets remain a larger feature (new `Pet` model + assignment) tracked under Phase 3.

### Onboarding — Guided Game Mechanics (design fragment, Target: TBD)

User requests for a first-session onboarding that teaches the game mechanics step by step. Written as the
player-facing requests the feature should satisfy; sequence and copy are up to implementation.

- ⬜ **Welcome & goal** — as a new Overseer, I want a short intro explaining my role and the vault goal, so I
  understand what I am doing before my first action.
- ⬜ **Power first** — guide me to build/assign my first power plant and explain why power gates everything else.
- ⬜ **Production chain** — walk me through water and food production, and show me what happens when a resource
  runs out.
- ⬜ **Assigning dwellers** — show me how SPECIAL stats map to rooms and let me try the auto-assign tools with an
  explanation of what they do.
- ⬜ **Vault expansion** — point me at building/elevators/room upgrades and merging at the right moment.
- ⬜ **Population basics** — explain living quarters capacity, breeding, and growth (radio recruitment later).
- ⬜ **Incidents & defense** — introduce incidents, weapons, and the arena when the vault is stable enough to
  survive a demo fight.
- ⬜ **Wasteland** — send my first dweller exploring with an explanation of stimpaks/radaways and recall.
- ⬜ **Progression loop** — objectives, quests, training, and where to find each system (links into the sidebar).
- ⬜ **Soft hooks** — after onboarding, surface the Overseer Briefing attention items instead of the tutorial.

Design notes: step order should follow actual dependency order (power → water/food → population → defense →
exploration); each step needs a skippable/dismissable state so returning players are not forced through it;
completion state should persist per user (localStorage or server-side).

**Delivery vehicle (decided 2026-09-19):** the pre-Overseer's-Office portion is delivered through the **sequenced
starter objectives** (`.omo/plans/quest-objective-progression.md`), not a separate modal tour. Progress persists
server-side via `VaultObjectiveProgressLink`, which resolves the localStorage-vs-server-side blocker for that phase;
later onboarding phases and skippability remain open.

### Celldweller Easter Egg (idea, Target: TBD)

In-game homage to the band Celldweller (fits the Fallout aesthetic — electro/industrial wasteland vibes).
Loose ideas, none committed:

- A legendary dweller named "Klayton" (or a wanderer named after band lore) with unique dialogue lines and
  Celldweller lyric references in their bio.
- A rare radio-station event: "Celldweller — Own Little World" plays as a special broadcast with a happiness
  bonus for the vault.
- A discoverable wasteland location on the world map (e.g. "Cell 23" / "End of an Empire" landmark) with a
  one-time loot drop or unique encounter.
- A crafting recipe or outfit skin referencing the band's visual style (chrome/black, glowing red accents).

Keep it optional, non-breaking, and discoverable — easter eggs should reward curiosity, never gate progress.

### Dweller Violence — one dweller moves against another (idea, Target: TBD)

A dweller deciding another dweller should not survive. Not scheduled; recorded now because the
machinery shipped for exit requests covers most of it and should be reused rather than rebuilt.

Reuse map (all of this already exists — reach for it first):

- **Applying the death**: `death_service.mark_as_dead(...)` in `backend/app/services/family/death_service.py`
  already takes `cause`, `epitaph` and `permanent`. A murder is the ordinary (revivable) path, so pass
  `permanent=False`; the killer is not an exile.
- **New death cause**: add a `DeathCauseEnum` member in `backend/app/core/enums.py`, then a manual
  `ALTER TYPE deathcauseenum ADD VALUE` migration plus the `PG_ENUM_LABELS_SNAPSHOT` update.
  `backend/app/alembic/versions/2026_09_17_0002-e7c8d9a0b1f2_*` (EXILE) is the template — autogenerate
  does not detect enum changes, and an unmigrated member poisons the connection pool.
- **Intent/pending state**: `dweller.exit_requested_at` is the pattern for "this dweller intends something"
  — one nullable column, withdrawn when the cause passes, no cooldown column. A grievance/vendetta would
  mirror it.
- **Eligibility policy**: `exit_request_service.blocking_reason` (grown dwellers only, not away from the
  vault, population floor) and `crud.dweller.count_living_in_vault` are directly reusable guards.
- **Tick phase**: `process_exit_requests` in `backend/app/services/game_tick/dwellers_tick.py` plus the
  `DwellersStats` counters in `tick_results.py` show how to add a per-tick dweller pass.
- **Player-facing event**: `NotificationType` + `notification_service.notify_*` + the
  `notify_owner(sender=...)` fan-out is the delivery pattern. A new type needs its own
  `ALTER TYPE notificationtype` migration + snapshot. Per the progression red line
  (AGENTS.md rule 9) this must surface as a modal/toast, never notification-only.
- **Chat surfacing**: `ACTION_TYPES`, `REQUIRED_ACTION_FIELDS` and `ALLOWED_ACTION_FIELDS` in
  `backend/app/agents/chat_schemas.py`, the `ActionSuggestion` union in `backend/app/schemas/chat.py`,
  the policy branch in `agents/chat_tools.parse_action_suggestion`, and the rule in `agents/chat_prompts.py`.
- **API surface**: `backend/app/api/v1/endpoints/exit_requests.py` is the thin vault-scoped router template.
  `DomainError` subclasses map to HTTP globally — do not add per-endpoint try/except.

Gaps this feature has that exit requests do not:

- **Motive and target selection.** `Relationship.affinity` (existing) is the natural source: cheap, already
  maintained, and pair-scoped. Needs a threshold plus a deterministic target policy.
- **Agency and consequence.** Does the killer get caught? Does the vault react (happiness hit, their own
  exit request, a status change)? Without this it reads as a random death, not a story.
- **Family fallout.** Victims with partners, parents or children leave a lineage behind — the family services
  already model this, so decide whether survivors react.
- **One-shot semantics.** It must not fire every tick; either a resolved flag or the standing-request
  withdrawal pattern above.
- **Architecture constraints that will bite**: queries belong in `crud/` (enforced by
  `app/tests/test_architecture/test_service_layer_guard.py`), enums are defined once in `app/core/enums.py`,
  and new service modules are named `*_service.py`.

### Parked Product Ideas

- Multiplayer/social features (friends, vault visits, leaderboards) are not on the delivery roadmap.
- Cloud saves and multi-device sync require a separate product and operations plan before scheduling.

---

## Technical Debt

### Backend

- [ ] Performance testing: Locust in nightly CI
- [ ] Datetime consistency: Migrate all `datetime.utcnow()` to aware `datetime.now(UTC)`
- [ ] Test-suite consolidation (backend + frontend) — audit redundant examples; prefer parameterized/table-driven cases,
      behavior-contract suites, and shared fixtures while preserving coverage and every currently exercised edge case.
- [ ] Reduce test flakiness — the suite runs on an in-memory SQLite engine with a single `StaticPool` connection, which
      serializes cross-session work and limits concurrency-sensitive tests (e.g. row-lock/`FOR UPDATE` guarantees are
      not exercisable). Consider a per-test transactional Postgres/`pytest-postgresql` harness for race-condition
      coverage and to harden `test_vault` segfaults under garbage collection.
- [ ] Docstring coverage: AI settings / chat services sit at ~32% (ruff `D` rules) vs the 80% repo target — add
      module and public-method docstrings to `app/services/ai_service.py`, `app/services/chat_service.py`,
      `app/crud/ai_settings.py`.
### Frontend

- [ ] Component refactoring: Break down large components (DwellerCard, RoomGrid)
- [ ] Reduce Vitest teardown flakiness — parallel runs intermittently hit `EnvironmentTeardownError`
      ("Cannot load ... after the environment was torn down", e.g. `RoomGrid.test.ts` / `RoomDetailModal.vue`).
      Investigate module-teardown ordering / `sequence` isolation so CI is deterministic.
- [ ] Drop the superseded standalone radio UI — `/vault/:id/radio` (`modules/radio/views/RadioView.vue`, already
      `hideFromNav`) duplicates the in-room radio panel (`RoomDetailModal` → `ProductionStats` radio mode +
      `RadioControls`, driven by `modules/rooms/composables/useRadioRoom.ts`). That route is the only external
      importer of `@/modules/radio`, so deleting it orphans the whole frontend module (view, store,
      `RadioStatsPanel`, `ManualRecruitButton`, routes) for a clean removal; the backend `/radio` API the room
      panel calls stays. Confirm every flow (stats, mode switch, manual recruit) is covered by the in-room panel
      before deleting.
### DevOps

- [ ] Deploy immutable images: build and promote commit-SHA tags; production deployments select an explicit tested tag,
      never `latest`
- [ ] Run database migrations as a dedicated, pre-rollout Kubernetes Job and abort deployment if it fails
- [ ] Add migration safety checks to backend CI (`alembic check` and `alembic current --check-heads` against PostgreSQL)
- [ ] Add deterministic seed data and critical Playwright journeys, including stable visual regression baselines
- [ ] Test the rollback workflow against a known image tag; automate staging while retaining manual production approval

---

## Progress Metrics

### Version Milestones

Full release history lives in `CHANGELOG.md`; release names recap the headline theme.
---



### Sound System — Fallout-Themed Music & SFX (Target: next updates — HIGH PRIORITY)

**User request**: a sound system with music and effects close to the original Fallout atmosphere (1950s radio,
ambient hums, terminal beeps, incident alarms). **The asset blocker is resolved** — a full Fallout-Shelter-style
library (music loops, per-room ambience, interface SFX) is available locally in `/assets/audio/` (git-ignored
source; curated copies land in `frontend/public/audio/`).

- 🔄 **UI & feedback SFX pass** — wired: global button-click `select` (delegated listener in the audio manager),
  room-modal `modalOpen` (close intentionally silent), chat typewriter key per keystroke in the message input
  (`typeKey`, fires on `beforeinput`), and `messageReceive` on dweller replies (WS + REST + audio paths via the
  shared messages watcher), incident alarm loops for the whole chain (spawn hook starts the loop and
  ducks music over 2s; the loop stops and music resumes 5s after the last incident resolves; asset is
  a public-domain excerpt, see the sound manifest). A speaker toggle in the navbar mutes/unmutes
  without leaving the page. Remaining: `cardDrop` on dweller drag-and-drop assignment,
  `upgrade` on room upgrades, `success` on completions.
- ⬜ **Radio station integration** — the radio room already streams a station concept; pipe music through it
  instead of the view-level loop.
- ⬜ **Ambient layers** — per-room ambience loops from `assets/audio/sounds/ambience/` (armory, cafeteria,
  barbershop, ...) layered under the music loop.
- ⬜ **Curated-copy growth** — extend `frontend/public/audio/` from the source library per feature (keep the
  committed set small; the 295MB source library stays git-ignored).

**Reuse:** `GameEvent`/SSE streams as trigger sources, Preferences persistence pattern, radio room UI.
**Blockers:** none hard remaining — remaining work is wiring + curation.
**Deploy:** verified end-to-end — Vite copies `public/` into `dist/`, the frontend image serves it via `serve -s`,
and the git-ignored source library never reaches CI. No pipeline changes needed; revisit cache headers or
object storage only if the curated set grows large.

### Sequenced Starter Objectives & Progress-Relative Quest Gating (P1 — plan ready)

**Plan:** `.omo/plans/quest-objective-progression.md` (recorded 2026-09-19).

**Focus:** the Objective system becomes the source of "what do I do next" from vault start until the Overseer's
Office is built, and quest unlocking follows the real game's dweller-LEVEL + equipment gates with progressive
reveal.

- Add a `starter` objective category (column is `VARCHAR(50)` → no PG enum migration) plus explicit `sequence` and
  `description`, seeded as one ordered arc at vault initiation; the current step is **derived at read time**
  (lowest unfinished sequence) so there is **no completion→unlock write** across background sessions. Pre-Office,
  the objectives view shows only this arc (daily/weekly/achievement tabs hidden).
- The arc teaches the player to **earn** the Overseer's Office's 1000 caps by exploring the wasteland and selling
  loot (a `collect caps` step already counts that income via `deposit_caps`' `RESOURCE_COLLECTED`), then capstones
  on **Build Overseer's Office** — the hand-off to quests. The Office gate stays at population 18 + 1000 caps; no
  income floor or reward tuning is added.
- Unify quest availability into one function used by both the read path and `POST /start`, fixing the current
  "listed as available but rejected at start" mismatch.
- Move the "**all** quests require the Overseer's Office" rule from the frontend into the backend as the single
  source of truth and expose `is_locked`/`lock_reason` to clients.
- Keep the real-game dweller-**LEVEL** gates (Against the Odds 46, A Poorly-Thought-Out Plan 44, A Gathering of
  Ghouls 27, `power_struggle` 20) and enforce them against the dwellers **sent** on the quest (the party must meet
  level/equipment requirements), matching the real game — not a vault-wide population check. Progress-relativeness
  comes from **progressive reveal**: a quest is hidden until the vault has a dweller within ~10 levels of its
  requirement, so a fresh board never shows level-46 quests, then shown locked with its requirement reason until a
  qualifying party exists. Advertised gates are always enforced (seed guard).
- Boosted vaults (seeded with the Office) skip the arc; existing vaults are not back-filled.

**Non-goals (this plan):** economy changes to the D1 soft-lock (guidance only), persisting `quest_objective` step
text, and new quest kinds — all tracked separately. **Blocking decisions:** all resolved 2026-09-19 (plan §9).

---

### Quest & Objective Domain Refactor — requirement policy + `progression/` domain — SHIPPED (#702)

Delivered per `.omo/plans/quest-objective-domain-refactor.md` (plan complete).

- `prerequisite_service.py` → module-level requirement policy in `progression/quests/requirements.py`
  (`vault_missing_requirements` read gate, `party_missing_requirements` start validation, describers; dead
  `can_start_quest` dropped). Behavior-neutral, locked by the existing suites + new regression cases.
- Quest + objective services grouped under `services/progression/`:
  `quests/{service,availability,requirements}`, `objectives/{evaluators,assignment,notifications}`. No
  `quests/rewards.py` (settlement stays in shared `reward_service`) and no `objectives/service.py` (no objective
  lifecycle facade exists). Top-level files remain thin compatibility facades; `objective_evaluators` is not the
  canonical monkeypatch path (tests patch `progression.objectives.evaluators`).
- Availability logic split into `quests/availability.py` (office gate, progressive reveal, read assembly).
- `async_session_maker` retyped as `async_sessionmaker` — the sync `sessionmaker` typing broke `async with`
  across session plumbing and hid `Session.execute` deprecations in `cli/`.
- Verified: 1737 backend tests pass; ruff/ty clean on changed files; architecture guards green.

---

### Quest System Completion & Expansion (P1 correctness, P2 new mechanics)

**P1 — correctness before expansion:** existing quest mechanics and rewards are the immediate priority (see Active
Priorities). Complete the audit and manual progression playtest before adding quest types, chain gates, or interactive
content.

**P2 — richer quest handling after the core loop is proven:** construction-driven quests, properly locked quest
chains, and quiz/puzzle quests. Reuse-first: the quest model already has `chain_id`/`chain_order`,
`previous_quest_id`/`next_quest_id` links, and `QuestRequirement`/`QuestReward` relations; the objectives system and
room construction flow already emit state that quests can key off.

- ⬜ **Authored quest ordering** — `chain_order` is already persisted from quest-chain JSON. Add explicit per-quest
  display/difficulty order, validate authored ordering uniqueness, and sort from those fields; do not infer
  difficulty from duration, UUIDs, or database insertion order.
- ⬜ **Locked quest chains** — chain visibility/lock state in the UI: show the next chain quest as "locked"
  with its unlock requirement instead of hiding it. Blocker: chain unlocking today is purely linear
  (`previous_quest_id`); requirement-based unlocking (vault level, population, resource thresholds) needs a
  decision on whether `QuestRequirement` rows gain a condition type or a new gating model is added.
- ⬜ **Building quests** — quests whose completion condition is a construction action ("build a Water
  Treatment", "upgrade to tier 2"). Reuse the objectives system's condition checking if it can watch room
  events; blocker: room construction currently emits no quest-checkable event, so the objectives/quest
  completion path needs a hook into room create/upgrade.
- ⬜ **Quiz / puzzle quests** — timed quest with a question/choice step instead of auto-resolve. Blocker:
  quests are timer+party based (`duration_minutes`); there is no interactive step model, no question content
  format, and no frontend interaction surface. Needs a small content schema (question, choices, reward
  mapping) and a quest-detail interaction UI.
- ⬜ **Separate handling per quest kind** — type-specific completion flows (auto-resolve vs construction vs
  interactive) behind the existing `quest_type`/`quest_category` fields rather than new tables.

**Blockers (in order):**

1. Chain gating model decision (requirement conditions vs new table) — blocks locked chains.
2. Room construction → quest event hook — blocks building quests.
3. Interactive-step content schema + UI — blocks quiz/puzzle quests; largest of the three.

---

## Roadmap Direction & Blockers

Standing direction for picking work, in order:

1. **Correctness and balance first** — quest rewards/mechanics and objective balance/playtesting outrank new
   progression features, technical polish, and expansion work.
2. **Reuse & integration over new systems** — a feature that composes existing services (event bus, quest
   chains, recycling pipeline, objectives) beats a green-field design at equal value.
3. **Unblock before building** — when a feature is blocked, prefer work that removes the blocker over
   workarounds.
4. **Low-hanging fruit next** — prefer scoped P1/P2 work when it does not displace progression correctness.

Current blocker map (what stalls what):

| Blocker                               | Stalls                                                                          | Unblocking work                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Chain gating model (**resolved 2026-09-19**) | Locked quest chains                                                       | Progress-relative gates reuse existing `DWELLER_COUNT`/`ROOM`/`QUEST_COMPLETED` + chain order + a backend-owned Office gate; no new requirement type or gating table (`.omo/plans/quest-objective-progression.md`) |
| Room construction events              | Building quests                                                                 | Emit quest-checkable events on room create/upgrade                           |
| Interactive quest-step schema + UI    | Quiz/puzzle quests                                                              | Content schema + quest-detail interaction surface (largest quest item)       |
| Trading PoC validation                | Trading Post graduation (weapons/outfits tabs, coverage re-inclusion)           | Playtest the dweller loop, then graduate per the WIP sidebar marker          |
| Bio structured-entry storage decision | Bio extension (action-driven updates)                                           | Decide JSONB vs side-table; template bios are NOT blocked and can ship first |
| Onboarding persistence (**pre-Office resolved 2026-09-19**) | Post-Office onboarding phases                                 | Pre-Office phase persists server-side via objective links; later phases still choose localStorage vs server-side |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

_Last updated: 2026-09-20_ — grey-surface styling policy recorded under Frontend
Design-System Consolidation (quest/objective cards lost their grey background in an earlier pass; a deliberate
"which parts, on what condition, which shade" decision is deferred). Also on 2026-09-19: quest/objective progression
plan recorded (`.omo/plans/quest-objective-progression.md`): sequenced starter objectives drive
pre-Overseer's-Office guidance and quest gates follow the real-game level/equipment model with progressive reveal.
Progression correctness remains P1; the D1 soft-lock stays a separate decision.
The world map remains single-vault exploration; multiplayer is out of scope.
