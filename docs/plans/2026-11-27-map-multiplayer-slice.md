# Map & multiplayer slice — Combat Zone + Vault Raids, playable end to end

Status: **Slice 1 backend implemented and approved at Gate 1 (Codex, round 3). Slice 2 UI next.**
Owner: maintainer. Related: `docs/WORLD_MAP_PLAN.md` (Phase B, parked),
`docs/features/WORLD_MAP.md`, `docs/features/COMBAT_SURFACE_MATRIX.md`,
`docs/features/WASTELAND_COMBAT_EXPANSION.md`, `docs/backend/GAME_MECHANICS.md`,
`docs/backend/SERVICE_LAYER.md`, `AGENTS.md`.

## Goal

Two multiplayer surfaces become **actually playable** in the CRT/Fallout UI, not just reachable:

1. **The Combat Zone** — cross-vault 1v1 asynchronous bouts: travel, queue, live spectating, stance
   commands, escrow/pot settlement, and a result the player can see and understand.
2. **Vault Raids** — the shipped cross-vault async exhibition duel, made playable: reachable from
   the map, visible to the defender, replayed as combat (not a text log), with a bounded history.

Observable end state: a player can open the map, find the Combat Zone or a discovered player vault,
send/challenge, watch the fight resolve with readable feedback, and find the result in the bell,
a toast/modal and a history list — on desktop and phone, without leaving the Fallout fiction.

## Decision D1 — binding scope for "async vault raid"

**Binding for this slice:** "Vault Raids" is the feature the repo already names and ships (#1476,
#1570): a cross-vault **exhibition duel** resolved from frozen snapshots. This slice makes that
surface fully playable. It does **not** add loot, dweller injury, or attacks on a live vault.

**Parked:** the looting/attrition raid described in `docs/WORLD_MAP_PLAN.md` Phase B (`RaidTarget`,
`raid` exploration subtype, rewards/losses, consent + protection). This slice keeps that contract
untouched and does not quietly ship any part of it.

**Required doc change in Slice 4:** record the exhibition map entry in the **active** part of
`docs/WORLD_MAP_PLAN.md` (outside the "Deferred multiplayer phases (parked)" section) and align
`docs/features/WORLD_MAP.md`. Describe the Combat Zone's **caps escrow** as its own mechanic, not as
raid loot.

## Decisions

- **D2 — Revive, don't rewrite:** port `feat/combat-zone-m1` onto a fresh branch, then adapt it.
  The engine, lifecycle and tests are the spec; a rewrite only if port cost proves higher.
- **D3 — One presentation and attack kernel (REUSE-B):** Combat Zone and Vault Raids reuse
  `ArenaRing`, `CombatDamageNumbers`, `useCombatPlayback`, `BattleLog`, `ArenaFighter` and the
  `attack_service` kernel. No second animation engine and no second damage formula. Vault Raids keeps
  its pure deterministic resolver; the shared kernel is for live Combat Zone rounds.
- **D4 — Transport:** polling on the existing cadence (lobby 3–5 s, match 2 s, event `after_sequence`),
  not new WebSocket/SSE channels. Notifications use the existing `NotificationService`.
- **D5 — Flags:** `combat_zone.enabled` default **`False`**; enable in dev and after playtest only.
  `pvp_duels` stays as-is (already on in production). Expose `combat_zone` in `/system/features` and
  the frontend flag store. No per-vault toggle: the global switch is the only gate (LOC review
  removed selective suspension).
- **D6 — Ownership:** `modules/combat-zone` for the real-time tick system; extend `modules/pvp` for
  raids. Do not create a third multiplayer module.
- **D7 — Settlement:** caps pot and result are one transaction; result notifications are staged in
  the same transaction and delivered after commit (existing PvP pattern).
- **D8 — No new currency/ranking:** no ELO, leaderboard, loot table, or new caps sink.
- **D9 — Shared Arena kernel:** `attack_service.resolve_attacks` gains one optional
  `damage_multiplier=1.0`; Combat Zone passes `outgoing_stance × incoming_stance`. Fighter power and
  the 5%/s cap stay intact; the skill queue is empty. `ArenaFighter` is the canonical nested fighter.
  Keep `CombatZoneEvent` and its cursor separate. Active skills are deferred until a playtest asks
  for a second input.

## Non-goals

- Looting a vault, dweller injury/death, or any live-vault query/combat authority.
- Live shared-world simulation, vault visits, trading, friends graph, leaderboards/ELO.
- New currencies, loot tables, or a second combat math engine.
- Public spectating of finished results (participants only; live spectating stays authorized).

## Current state (verified)

| Area | State | Evidence |
| --- | --- | --- |
| Combat Zone backend | Complete but **unmerged** branch, 42 files, +4,605/−114, based on `3b5ae333` (2026-10-19); 14 conflicts with HEAD | `git diff --stat 3b5ae333..feat/combat-zone-m1`; `git merge-tree` |
| Combat Zone UI | Vue module with panel + match cards, terminal framing ("Interchange 77", the Umpire), queued board, stances, journal; no `ArenaRing`/playback | `frontend/src/modules/combat-zone/*` on branch |
| Combat Zone transport | 2 s Dramatiq actor, chain lease + advisory lock, polling; **no bell/SSE**; text-only events; final HP not frozen | `combat_zone_tasks.py`, `combat_zone_engine.py` on branch |
| Vault Raids backend | In HEAD, flag on in production | `backend/app/services/pvp_duel_service.py`; `deployment/k3s/backend-deployment.yaml` sets `FEATURE_PVP_DUELS=true` |
| Vault Raids UI | Board/post/accept/text journal; no defender notification, no map entry, no history, no playback | `frontend/src/modules/pvp/views/VaultRaidsView.vue` |
| Vault Raids extras | Two small laptop branches: durable history (384 lines), map challenge (250 lines) | `remotes/laptop/feat/pvp-raid-history` (`25aceb5f`), `remotes/laptop/feat/pvp-targeted-challenges` (`b28330bb`) |
| Map | SVG/atlas; marker types without Combat Zone; player vaults already on the shared atlas | `frontend/src/modules/map/models/markerTypeMeta.ts`, `stores/map.ts`, `backend/app/services/map/reads.py` |
| Combat presentation | `ArenaRing` + `useCombatPlayback` + `CombatAction`/`CombatImpact` already exist | `frontend/src/modules/rooms/components/ArenaRing.vue`, `frontend/src/modules/combat/composables/useCombatPlayback.ts`, `backend/app/schemas/combat.py` |
| Alembic head at review | `c3f5a7d9e1b2` | `cd backend && uv run --no-sync alembic heads` |

## Transaction ownership (name one owner per operation)

| Operation | Owner | Lock order | Staged writes | Commit / delivery |
| --- | --- | --- | --- | --- |
| Combat Zone send | `CombatZoneService.send_party` | party row → dweller row → vault row (last, matching tick order) | caps deduction, party row (`TRAVELING`, escrow, origin room), dweller (`FIGHTING`, room cleared) | one commit; then wake tick; no notification |
| Combat Zone recall | `CombatZoneService.recall_party` | party row → vault row | escrow refund from recorded `escrow_caps`, party (`RETURNING`/`RETREAT`), dweller restore only on final return | one commit per command |
| Combat Zone tick | `CombatZoneTickEngine.process` | advisory lock → match row → party rows → dweller rows → vault rows (payout) | travel/arrival, pairing, one micro-round via `resolve_attacks`, fractional carry per fighter, turn advance, match finish (frozen HP), journal, notification rows (`commit=False`) | one engine commit per tick; deliver after commit |
| Duel post | `PvpDuelService.post` | challenger vault lock → lazy expiry → snapshot/insert | duel row only | one commit; no notification |
| Duel accept | `PvpDuelService.accept` | duel row (`FOR UPDATE`) → vaults → snapshots | defender snapshot, outcome, journal, participant notifications (`commit=False`) | one commit; deliver after; discard on rollback |

Rules:

- **Carry is match state:** persist fractional damage carry per match and fighter in the same
  transaction as HP, turn advancement and journal events. A turn whose whole-damage total is zero
  still advances the attacker and writes the carrying state; never drop the tick.
- **Concurrent first send (no party row yet):** an absent row cannot be locked. `send_party` inserts
  the `combat_zone_party` row first (unique `vault_id`) inside a savepoint; a unique conflict rolls
  back that savepoint and raises `ResourceConflictException` **before** any fee debit or dweller
  change. After the insert, lock party → dweller → vault, matching the tick order. Never lock an
  absent row, and never debit the fee before the row exists.
- **Ordinary rejection rollback:** an ineligible dweller, active incident, insufficient caps, or a
  disabled switch leaves caps unchanged, the dweller unchanged, and no party row. Test each.
- Draw refunds come from the **recorded** `escrow_caps`, never from config at settlement time.
- `credit_vault` returns the **actual credited amount** (the 999,999 caps ceiling can truncate);
  the player-facing result reports what was credited, not what was promised.
- Cover failures during notification **staging** (before commit) as well as commit: a late DB
  failure must roll back, reload affected rows, and assert **zero external delivery**.
- PostgreSQL concurrency tests with independent sessions and **zero skips**: concurrent first send
  (one success, one controlled rejection, one fee debit, one `FIGHTING` dweller), concurrent
  settlement, concurrent accept.

## Combat Zone wire contract

Use the existing `CombatAction`/`CombatImpact` schemas as the payload shape (no second event model).

| Field | Rule |
| --- | --- |
| `sequence` | Monotonic per match, unique `(match_id, sequence)`; clients poll `after_sequence`. Never filter by `round_seq` — a finish event can share the final hit's round. |
| `kind` | `system`, `hit`, `finish` |
| `actor_id` | Stable side/fighter id (`a:<party_id>`, `b:<party_id>`, or `challenger:<dweller_id>`) |
| `action` | `CombatAction` produced by `resolve_attacks` (`actor_body`/`effect` from `weapon_skill`, empty skill queue), with `targets: [CombatImpact]` carrying `damage`, `health_before`, `health_after` |
| `message` | Human journal line, retained for accessibility and legacy rendering |
| `cursor` | `{ sequence, round_seq, status }` returned with first load and terminal load |

- **Fighter DTO:** `CombatZoneMatchPartyRead` nests `fighter: ArenaFighter` as the canonical shape
  and keeps `stance`, `vault_id`, `vault_number`, `is_winner` on the wrapper. Reuse
  `participant_from_dweller`/`fighter_view` for live rows; reconstruct finished fighters from frozen
  match fields (level, power, age group, race, HP) and suppress `active_skill`/pet metadata (stances
  are the only Combat Zone input).

- **Authoritative HP:** the match party `health`/`max_health` at `cursor.sequence` is authoritative;
  event `health_before`/`health_after` are presentation only. On reconnect, read the cursor: if
  `cursor.sequence > last_sequence`, request events after `last_sequence` and apply them; if the
  cursor is behind the client or the gap exceeds the playback budget, hard-resync from the snapshot,
  clear the queue and skip to live.
- **First load:** full event list + cursor. **Reconnect:** `after_sequence`. **Terminal:** final
  events + frozen result; never read live dweller rows.
- Freeze finished fields on the match so a returned/redeployed dweller cannot rewrite history:
  names, levels, power, max HP, final HP, portrait `age_group`/`race`, vault numbers.
- Endpoint scoping: **active** matches may be spectated by any authenticated user; **finished**
  detail, journal and history are participant-only.

## Vault Raids replay projection

- `PvpDuelRead` keeps its summary shape; add a participant-only `replay` projection:
  stable fighters (`challenger:<dweller_id>`, `defender:<dweller_id>`), frozen name/level/power,
  portrait `age_group`/`race`, per-member `hp_before`/`hp_after`, and `CombatAction` events.
- **Integer HP model (no visibly standing corpse, no false knockout):**
  - Keep the resolver's **fractional side HP authoritative** and never round the pool to decide
    lethality. A 10.2 pool minus 10 damage is still alive.
  - Display rule: if the side's authoritative remaining is `<= 0`, display **every** member at `0`;
    otherwise display each member at `max(1, ceil(member_remaining))` when its remaining is positive,
    and `0` only for an overkilled member. `ArenaFighter.health` stays an integer display value.
  - Member remaining is the member's **fractional** initial pool (`power_i * hp_per_power`, which sums
    to the side pool) minus the integer damage shares that targeted it; internal overkill is allowed.
    Do **not** use `split_proportional` for this allocation: it rounds the total before splitting and
    would zero a 10.2-HP one-fighter side after 10 damage. Round only when producing display HP.
  - Round-limit wins keep both sides above 0 and use the remaining pool; the resolver outcome does
    not change.
  - Tests: unequal-power parties, overkill, round-limit win, and the 10.2-vs-10 display case.
- Legacy journals (no `action`/fighter data) render text-only with a "legacy record" note; outcomes
  are unchanged. **Pre-deploy snapshot:** a challenge posted before this deploy and accepted after it
  may carry a snapshot without replay fields; `replay` returns `null` for that duel and the UI falls
  back to the text journal. Test post-before-deploy → accept-after-deploy.
- Displayed HP is the stored resolution, never a live dweller read.
- Playback controls: explicit **Replay** loads the full event list into the shared queue;
  play/pause and **Skip to result**. No step-by-step control in the first pass.

## Slices and gates

| Slice | Deliverable | Gate |
| --- | --- | --- |
| 0 | This plan | **Codex `APPROVE`** |
| 1 | Combat Zone backend revived + notifications + event payloads + migrations + tests | Codex reviews diff + executable evidence |
| 2 | Combat Zone UI/UX + map entry + live spectating + visual QA | Codex reviews diff + screenshots |
| 3 | Vault Raids playable: map challenge, defender notice, replay, history | Codex reviews diff + evidence |
| 4 | Docs, flags, size report, PR (no merge) | Codex final review |

No slice starts before the previous gate is approved. A gate is executable only when its commands
and evidence are attached.

Gate 1 (Slice 1 backend) was approved by Codex after three re-reviews. The evidence lives in
`backend/app/tests/test_db/test_combat_zone_concurrency.py`: PostgreSQL send/settlement races, a
forced send-vs-recall interleaving, repeatable-read snapshot tests for detail and incremental events,
a payout-trigger rollback, and a second-notification rollback that proves the first delivery was
queued before the transaction failed.

## Slice 1 — Combat Zone backend revival

### 1.1 Dependency checklist (port in this order)

1. `backend/app/core/combat_zone.py` — POI constants + stable location id.
2. `backend/app/core/combat_zone_dispatch.py` — wake binding (`register_combat_zone_wake`,
   `request_combat_zone_tick`).
3. `backend/app/core/enums.py` — `CombatZoneStance`, `CombatZonePartyStatus`,
   `CombatZoneMatchStatus` (keep enum ownership here).
4. `backend/app/core/game_config.py` — `CombatZoneConfig`; **`enabled=False`**.
5. `backend/app/models/combat_zone.py`, `models/__init__.py`. Include fractional carry per fighter
   on the match.
6. `backend/app/crud/combat_zone.py`.
7. `backend/app/schemas/combat_zone.py`, `schemas/wasteland_location.py`
   (`CombatZoneMarkerRead`, `VaultMapResponse.combat_zone`). `CombatZoneMatchPartyRead` nests
   `fighter: ArenaFighter`.
8. `backend/app/services/combat/attack_service.py` — add optional `damage_multiplier=1.0`, applied
   to raw damage before the per-second cap; defaults keep Arena/site output identical.
9. `backend/app/services/combat/arena_participants.py` — reuse `participant_from_dweller` and
   `fighter_view` from the engine/service; add a frozen-fighter helper only if needed.
10. `backend/app/core/chained_tick_actor.py` — extract the narrow Redis lease + `task_session`
    wrapper shared by `arena_tasks.py` and `combat_zone_tasks.py`; each actor keeps registration,
    scheduling, watchdog and stop conditions.
11. `backend/app/services/combat/combat_zone_engine.py`, `combat_zone_service.py`.
12. `backend/app/services/map/reads.py` — `combat_zone` marker projection.
13. `backend/app/api/combat_zone_tasks.py`; import it from `app/api/tasks.py` (worker binding), and
    bind the wake at the web composition root if the web process is expected to wake the actor
    (otherwise document the watchdog fallback).
14. `backend/app/api/v1/endpoints/combat_zone.py`, `api/v1/api.py`.
15. Migrations in `backend/app/alembic/baseline_versions/` (see 1.4).
16. Tests.

### 1.2 Flags and switch-off behavior

- **One source of truth:** `game_config.combat_zone.enabled` drives the actor, the endpoint guard,
  the map marker's `enabled`, and `/system/features`.
- **Switch-off drain (executable, not one pass):** the actor must **not** early-return on global
  disable. It enters drain mode when disabled:
  - **Global disable:** no new sends. Each tick refunds `TRAVELING`/`QUEUED` escrow, returns those
    dwellers, and finishes `IN_MATCH` as draw/refund. The chain lease keeps running until **every**
    party is `HOME` and every match is terminal, then the actor exits. The periodiq watchdog
    re-seeds it — including after a worker restart — and resumes the drain.
  - While disabled, a live `IN_MATCH` bout is finished as draw/refund; new sends are blocked and
    the map marker is dark.
  - Tests: global disable with one party in each state; worker restart mid-drain.
- **Reads vs commands:** the flag gates **commands** (send, stance, challenge), not every read. Lobby/history/party and finished match detail stay readable while the flag is off, so
  a drain/refund notification can open its result. Split dependencies into
  `require_combat_zone_commands` and `require_combat_zone_reads`; participant scoping still applies
  to finished detail/history. Test: global flag off → open a drained result from the bell, history
  renders, while send/stance/challenge are rejected.
- Add `combat_zone` to `FeaturesResponse` and `frontend/src/core/stores/featureFlags.ts`.

### 1.3 Session premise (corrected)

At reviewed HEAD, `backend/app/db/session.py::task_session()` explicitly returns SQLModel's
`AsyncSession`, which does provide `.exec()`. Keep the repo rule anyway: CRUD uses
`session.execute(...)`; services stay query-free. Add a regression test that runs the **worker
entry point** and one that drives the CRUD with a **raw SQLAlchemy** `AsyncSession`, so the code is
portable regardless of which session class the actor is given.

### 1.4 Migration contract

- Re-parent onto **`c3f5a7d9e1b2`** (verify at port time with `uv run --no-sync alembic heads`).
- Place the rewritten revision in `backend/app/alembic/baseline_versions/`, with a new revision id
  and `down_revision = "c3f5a7d9e1b2"`.
- Explicit PostgreSQL enum DDL for the three enums via `op.execute()` / `postgresql.ENUM`
  (`checkfirst=True`), with a matching downgrade drop. Update `PG_ENUM_LABELS_SNAPSHOT` in
  `backend/app/tests/test_db/test_enum_drift.py` in the **same commit** and run that test.
- Aware timestamps: use `UTCDateTime`/`DateTime(timezone=True)` and `app.utils.time.utcnow()`; add
  the new columns to the UTC inventory/test (`docs/backend/UTC_MIGRATION.md`,
  `test_utc_migration_contract.py`).
- Nullable pre-settlement HP (`party_a_health`, `party_b_health`, max HP) so live and finished
  states are distinguishable.
- Idempotent Interchange 77 seed keyed by `normalized_name` (`ON CONFLICT DO NOTHING`), with
  downgrade deleting only the system row.
- Prove: single head, upgrade from the prior head, downgrade/re-upgrade, and `alembic check` on a
  scratch PostgreSQL database.

### 1.5 Playback payload and result fidelity

- **Shared kernel:** `_resolve_round` calls `resolve_attacks` with an empty skill queue and
  `damage_multiplier = outgoing_stance × incoming_stance`; persist the returned fractional carry per
  match/fighter with HP, turn advance and journal rows in one transaction. A zero-whole-damage turn
  still advances the attacker and writes carry state.
- **Wire:** build `CombatAction` from the resolver result; `CombatZoneMatchPartyRead` nests
  `fighter: ArenaFighter` (live rows via `fighter_view`, finished rows from frozen fields, skills
  suppressed).
- Add `sequence` (unique per match) and `action` JSON to `combat_zone_event`; fill from
  `_resolve_round` / `_finish_match`. Never poll by `round_seq`.
- Store frozen final HP, level, power and portrait fields (`age_group`, `race`) on the match at
  finish; never read a live dweller for a finished result.
- Keep the 25% return floor separate from the stored final combat HP.
- `resolve_attacks` defaults must leave Arena and wasteland-site output byte-identical; add a
  regression test on their existing fixtures.

### 1.6 Notifications and history

- On finish, stage one `COMBAT_VICTORY` / `COMBAT_DEFEAT` per participant user
  (`meta_data={"combat_zone_match_id": ...}`), `commit=False`; deliver after commit; discard on
  rollback.
- Add `GET /combat-zone/matches` for the viewer's vault: **bounded recent list** (default 20, max
  50), stable order `(finished_at DESC, id DESC)`, no journal payload. Explicitly no cursor paging
  in this slice.
- History/detail scoping: participants only; live matches remain spectatable by authenticated users.

### 1.7 Tests

Port the branch's 17 service + 5 API tests, then add:

- Notification staging/rollback; zero delivery on late DB failure.
- Ordinary rejection rollback: ineligible dweller, active incident, insufficient caps, or disabled
  switch leaves caps, dweller and party row unchanged.
- Concurrent first send (`test_db/test_combat_zone_send_concurrency.py`: one success, one 409, one
  fee debit, one `FIGHTING` dweller), concurrent settlement
  (`test_db/test_combat_zone_settlement_concurrency.py`) and concurrent accept
  (`test_db/test_pvp_duel_accept_concurrency.py`) on PostgreSQL with independent sessions and
  **zero skips**.
- Switch-off drain: global disable with each party state; worker restart mid-drain.
- Draw refund from recorded escrow; caps-ceiling actual credited amount.
- Frozen final HP survives return floor and party reuse.
- `sequence` monotonic; finish shares the final round; `after_sequence` reconnect; first/terminal.
- Participant scoping for finished detail/journal/history; live spectating allowed.
- Kernel parity: Arena and wasteland-site fixtures unchanged with `damage_multiplier=1.0`.
- Balance: representative low-, mid- and high-power matchups resolve within the 120 s limit; record
  whether different stances saturate the 5%/s cap; assert a turn with zero whole damage still
  advances.
- Carry: fractional carry persists across worker restart and rolls back with its HP/journal row.
- Shared tick wrapper: Arena's existing reschedule path still passes; Combat Zone keeps ticking
  through drain and stops when cleanup completes.
- Worker entry point + raw SQLAlchemy session.
- Migration up/down/re-upgrade + enum drift snapshot + UTC contract.

## Slice 2 — Combat Zone UI/UX

### 2.1 Scope cuts (first pass)

- **One** entry banner, not a second vault banner: reuse the existing multiplayer banner host and
  add the Combat Zone action beside the raid action.
- No custom countdown component; reuse `formatRemaining`/`useNow`.
- No bespoke Vault Boy treatment; reuse the existing feedback system only if an existing event fits.
- No replay stepping in the live panel (Slice 3 owns replay).

### 2.2 Entry points

- Map: add `combat_zone` marker type (`mdi:sword-cross`), legend row, and the Interchange 77 marker
  from the `combat_zone` map field; clicking opens the panel. Dark when the global flag is off.
- Vault page: a single Combat Zone action in the existing multiplayer banner/card, flag-gated.
- Do not add a production sidebar item in this slice.

### 2.3 Panel and match UX (Fallout fiction)

- Keep the branch's fiction: **Interchange 77**, **the Umpire**, emergency-band broadcast frame,
  purse, regulation bout.
- Overview: signal status, contender picker (mature, idle/working, not dead), entry fee vs caps,
  ETA, queue state, active match, house rules.
- Board: queued contenders (vault number, level, coarse power, stance, queued time), direct
  challenge, live matches.
- Match: reuse `ArenaRing` + `useCombatPlayback` + `BattleLog` through a small Combat Zone adapter
  (1v1 dweller layout, `skillEnabled=false`), with `CombatDamageNumbers`, HP bars, round/next-attacker
  strip, stance buttons and the "frequency" journal. No new animation components.
- Result: Victory/Defeat/Draw terminal card with credited pot and frozen final HP; toast + bell +
  result modal when the panel is closed.
- Reduced motion: static HP updates, no shake; respect `prefers-reduced-motion`.

### 2.4 Transport and lifecycle

- Lobby poll 3–5 s while open; match poll every 2 s with `after_sequence`; stop on close, route
  leave, hidden tab, unmount. Follow `frontend/AGENTS.md` event-delivery ownership.
- Reconcile on missed windows; never replay history on entry; skip to live state if the backlog
  exceeds the playback budget.

### 2.5 Notification consumer (single owner)

`frontend/src/modules/vault/components/shell/NotificationBell.vue` +
`frontend/src/modules/vault/utils/notificationRouting.ts` own result toasts and deep links.

- Add `combat_zone_match_id` routing; define draw copy.
- Reuse the `duel_id` route for both exhibition participants.
- Bell **plus** toast/modal when the panel is closed; deduplicate across notification delivery,
  reconnect and polling.
- **Result-only mode:** a `combat_zone_match_id` deep link must render the frozen match/history even
  when the global flag is off (drain/refund case). Do not gate the result view on the map marker or
  `enabled`; gate only the commands.
- Test obsolete responses after a vault switch, and opening a drained result with the flag off.

### 2.6 Tests and QA

Store/api; panel interactions; playback adapter; polling lifecycle; map marker/legend/list; banner
gating; notification routing/dedup; reduced motion. Manual browser QA at desktop + phone with
screenshots (panel, live bout, result).

## Slice 3 — Vault Raids playable

### 3.1 Pinned reuse

- `remotes/laptop/feat/pvp-raid-history` (`25aceb5f`) — history schema/service/CRUD/API/store/view.
- `remotes/laptop/feat/pvp-targeted-challenges` (`b28330bb`) — map challenge modal/route.
- Cherry-pick or port; re-run their tests against current HEAD.

### 3.2 Server-side target eligibility

The shared atlas lists live player-vault slots globally, while `PvpDuelService.post` currently
checks only target existence and self-targeting. `vault_slot_crud.list_markers` filters deleted
vaults but does **not** identify scenario/test vaults.

Define one predicate, `is_challengeable_target`, shared by the map projection and the POST path:

- target vault has a `VaultSlot` row (shared atlas placement),
- `Vault.is_deleted == False`,
- `Vault.user_id IS NOT NULL`,
- `Vault.scenario_key IS NULL` (scenario/test vault representation),
- `Vault.incidents_disabled == False` (playground representation),
- target id != caller vault id.

Expose `challengeable: bool` on `PlayerVaultMarkerRead` computed from this predicate; the UI reads
the flag instead of recomputing. `PvpDuelService.post` revalidates the same predicate on every
direct POST. The map response stays identity-only (owner username, number, coordinates; no
resources). Tests: a **slotted scenario vault** is rejected by a direct POST; an **unslotted vault**
is rejected; self-targeting is rejected; an eligible slotted vault succeeds.

### 3.3 Board states and defender visibility

- States: **incoming targeted**, **public open**, **outgoing (mine)**.
- The defender sees a pending targeted challenge in the existing banner and board before
  acceptance; accepting remains voluntary.
- Defender receives the result notification on accept; stage it in the accept transaction and
  deep-link to `?duel=<id>`.

### 3.4 Replay and history

- Participant-only replay projection (see "Vault Raids replay projection"): stable fighter ids,
  frozen presentation, per-member HP, `CombatAction` events.
- `RaidPlayback` maps frozen snapshots to `ArenaRing` fighters (1–3 per side) and replays the
  journal; explicit Replay, play/pause, Skip to result. No client combat math.
- History: bounded recent list (limit 20, max 50), stable `(created_at DESC, id DESC)`, no cursor
  paging in this slice; the laptop branch's `limit`-only endpoint is acceptable once ordering is
  pinned.
- Legacy journals render text-only; outcomes preserved.

### 3.5 Tests

- Defender notification staged/rolled back; targeted access denied; self-challenge rejected.
- Eligibility enforced on direct POSTs; map identity-only; slotted scenario and unslotted vaults
  rejected.
- History ordering/bounded list and participant scoping.
- Resolver per-member HP and additive fields; playback order/reconciliation; legacy records;
  pre-deploy snapshot accepted post-deploy; duplicate names; 3-fighter parties on phone width.
- Display rule: a one-fighter 10.2-HP side that takes 10 damage displays **1 HP** and the bout
  continues; terminal frame zeros every member of a defeated side; unequal power and round-limit wins.
- Combat Zone reads remain available with the global flag off: open a drained result from the bell,
  render history, and verify send/stance/challenge are rejected.
- Map challenge route/modal gated by `pvpDuels`, but a result deep link works with `combat_zone`
  disabled.

## Slice 4 — Ship

- Flags: Combat Zone dark by default; dev/test enabled via env; production enable only after a
  two-vault playtest. Vault Raids keep the current production flag.
- `pnpm run types:generate` after every API change (Gate 1 and Gate 3).
- Docs: update `docs/ROADMAP.md`, add the active exhibition section to `docs/WORLD_MAP_PLAN.md`,
  align `docs/features/WORLD_MAP.md`, add `docs/features/COMBAT_ZONE.md`, link from
  `WASTELAND_COMBAT_EXPANSION.md`; record new invariants in `GAME_MECHANICS.md`.
- Size report and budget (below); PR body states what is reused/replaced.
- Open the PR, run CI, hand over for review. **Do not merge** without maintainer approval.

## Size budget (per slice)

Baseline at review: **81,679 backend** and **83,125 frontend** handwritten production lines. The
donor branch measured **3,801** gross application/test additions against its base.

| Slice | Production (handwritten) | Tests | Migrations | Generated |
| --- | ---: | ---: | ---: | ---: |
| 1 Combat Zone backend | ~1,920 | ~1,200 | ~230 | API schemas only |
| 2 Combat Zone UI | ~1,200 | ~600 | 0 | frontend types |
| 3 Vault Raids | ~500 | ~300 | 0 | frontend types |
| Total | **~3,620** | **~2,100** | **~230** | regenerated |

LOC review cuts removed ~330 implementation lines. The Gate 1 evidence then added the PostgreSQL
race, snapshot and rollback tests back, landing Slice 1 at ~1,920 production / ~1,200 tests / 230
migration lines — within Codex's test target and ~120 lines over its production estimate. Kernel reuse
still accounts for the bulk of the reduction from the 4,605-line donor. The separate
`CombatZoneEvent` and cursor stay because the matrix records that unified journal storage is out of
scope. Generated OpenAPI types (+701) are excluded from the handwritten counts.

Justification and cuts:

- The separate tick system is required: the vault tick is too slow for a 2 s bout; it reuses the
  Arena actor/lease wrapper rather than duplicating it.
- The dedicated `modules/combat-zone` owns a distinct real-time domain; Vault Raids extend
  `modules/pvp` instead of adding a second module.
- The shared kernel removes the donor's inline `_damage`, its party DTO and the duplicated tick
  lease; the slice adds ~200 net production lines instead of a second combat engine.
- The shared playback kernel replaces the branch's text-only journal and bespoke match cards; no
  existing feature is deleted, so the PR says "nothing further to remove".
- Flag owner: maintainer. Review date: first two-vault playtest, recorded in the PR.
- Two-vault playtest criterion: both players can (a) find the entry, (b) explain what each stance
  does, (c) locate the result in the bell/toast/modal and history, and (d) see a stance change alter
  the fight without every round saturating the 5%/s cap.

## Executable gates

### Gate 0 — plan

Codex reads this file and replies `APPROVE` or numbered `CHANGES`. Evidence: the reply is quoted in
the PR/handoff.

### Gate 1 — backend

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run ty check --output-format concise 2>&1 | grep -E 'combat_zone|pvp_duel'   # expect empty
uv run pytest app/tests/test_services/test_combat_zone_service.py \
             app/tests/test_api/test_combat_zone.py \
             app/tests/test_services/test_arena_service.py \
             app/tests/test_services/test_combat_presentation.py \
             app/tests/test_services/test_pvp_*.py \
             app/tests/test_api/test_pvp_duel.py \
             app/tests/test_db/test_pvp_duel_accept_concurrency.py \
             app/tests/test_db/test_combat_zone_concurrency.py \
             app/tests/test_db/test_enum_drift.py \
             app/tests/test_db/test_utc_migration_contract.py -q
# PostgreSQL race tests must execute, not skip:
uv run pytest app/tests/test_db/test_pvp_duel_accept_concurrency.py \
             app/tests/test_db/test_combat_zone_concurrency.py \
             -m integration -q -rs
uv run pytest app/tests -q
uv run --no-sync alembic heads        # exactly one head
uv run --no-sync alembic upgrade head
uv run --no-sync alembic downgrade -1
uv run --no-sync alembic upgrade head
uv run prek run --from-ref <base-ref> --to-ref HEAD
```

Scratch PostgreSQL: upgrade from the prior head, `alembic check`, downgrade/re-upgrade. Then start
the backend and run `cd frontend && pnpm run types:generate`; commit the intended generated diff.

### Gate 2 — frontend

```bash
cd frontend
pnpm run lint
pnpm run format:check
pnpm run typecheck
node scripts/check-boundaries.mjs
node scripts/check-hardcoded-colors.mjs
node scripts/check-raw-controls.mjs
pnpm run test:run
pnpm run build
node scripts/check-bundle-budget.mjs
```

Browser QA: desktop + phone, Combat Zone panel, live bout, result, map marker/legend; screenshots
attached; check module-boundary imports and that polling stops on close.

### Gate 3 — Vault Raids

After `pnpm run types:generate`, **re-run the full backend suite** (`uv run pytest app/tests -q`),
the Gate 1 targeted + PostgreSQL race tests, and every Gate 2 command. Then run the targeted
eligibility tests, replay/legacy tests, and browser QA of the map challenge → board → replay →
history path. Attach the generated diff and zero-skip race output.

### Gate 4 — handoff

Final implementation evidence before handoff, in this order:

```bash
cd backend && uv run pytest app/tests -q          # full backend suite, final tree
cd ../frontend && pnpm run test:run                # full frontend suite, final tree
```

Then update docs, run `python3 scripts/size-report.py <base-ref>`, and open the PR with the
evidence. No merge.

### Push and merge rules

- Codex approval advances the **review gate only**.
- A push requires explicit user authorization, the installed `scripts/pre-push` guard, and a
  verified explicit feature-branch destination:
  `git push -u origin HEAD:refs/heads/<branch>`.
- A merge requires maintainer approval for that specific PR; the agent does not merge.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| 14 conflicts / stale branch (Oct 19) | Port backend first; adapt to `app.core.tick_chain`, `run_async`, current service patterns; rebuild the service on the branch as spec if conflicts exceed the rewrite |
| Two tick loops / double settlement | One actor, chain lease + advisory lock; shared tick wrapper; concurrency tests |
| Shared-kernel balance shift | Donor `power/10` min-1 becomes `power/5` with a 5%/s cap and carry; test low/mid/high power and stance saturation before enabling |
| Arena/site regression | `damage_multiplier=1.0` must leave existing fixtures byte-identical; parity tests in Gate 1 |
| Playback divergence from polling | `sequence` cursor, snapshot reconciliation, skip on backlog |
| Escrow/caps ceiling mismatch | Draw refunds from recorded escrow; report actual credited amount |
| Docs say raids deferred | Binding D1 is exhibition only; update `WORLD_MAP_PLAN.md`; no loot/loss code |
| Target spam / consent | Eligibility from atlas, voluntary accept, no stakes, identity-only map |
| Production `pvp_duels` already on | Test new defender notification/map entry against the live flag |

## Closed decisions (no open questions)

| Question | Decision |
| --- | --- |
| Raid semantics | Exhibition duels only; Phase B looting raids stay parked (D1). |
| Port vs rebuild | Port `feat/combat-zone-m1`; rebuild only if conflicts exceed the port (D2). |
| Live transport | Polling on the existing cadence; no new SSE/WebSocket channel (D4). |
| Notification family | Reuse `COMBAT_VICTORY`/`COMBAT_DEFEAT` with `meta_data` ids (1.6). |
| Enablement | Global flag only, default off; no per-vault toggle (LOC review; 1.2). |
| History shape | Bounded recent list, stable order, no cursor paging in this slice (1.6/3.4). |
| Playback | One shared kernel; Replay + play/pause + Skip to result; no stepping (D3). |
| Combat engine | Shared Arena kernel: `resolve_attacks` + optional stance multiplier; skills deferred (D9). |
| Fighter shape | `ArenaFighter` nested inside `CombatZoneMatchPartyRead` (D9). |
| Journal storage | `CombatZoneEvent` stays separate; shared `CombatAction` only (D9). |
