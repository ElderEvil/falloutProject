# Expedition Sites — Resolved Rules and Implementation Spec

Status: **decisions resolved; implementation in progress.**

Context: the expedition-sites feature is on three stacked PRs — backend
(#786), frontend (#787), scenario CLI (#788). This document records the
gaps found in review, the decisions taken, and the rules implementation
must follow. Analysis only previously; the "Resolved model" below is the
authoritative spec.

Related: `docs/features/INTERACTIVE_EXPEDITION_SITES.md` (design doc). Its
§10 ("freeze the event clock") and §8 ("rooms yield nothing on revisit")
were not implemented; the rules here supersede them where they differ.

## Decisions

| #   | Decision | Chosen |
| --- | -------- | ------ |
| D1  | Clock during open runs | **A** — pause random events only; clock keeps running |
| D2  | Retreat-farming rule | **B** — any terminal run locks the site 7 days |
| D3  | XP on combat re-attempts | **A** — credited once, on room clear |
| D4  | Same-site concurrency per vault | **B** — one open run per vault/site (exclusive) |
| D5  | Room payout permanence | **B** — reset window, aligned to the 7-day lock |

Micro-decision (unanimous-simple rule): **every terminal status
(`CLEARED`, `RETREATED`, `DIED`) starts the cooldown**, including an
expiry-driven auto-retreat.

### CodeRabbit findings (PR #786) — all captured here

| Finding | Maps to |
| ------- | ------- |
| `expedition.py:406` — retreat/re-entry farms room loot; extend anti-farm to `RETREATED`/`DIED` | Gap 2 / D2-B (their suggested fix **is** the chosen rule) |
| `expedition.py:475` — block expedition actions after the exploration leaves `ACTIVE` | Gap 1 |
| `docs/…:125` — "someoneImprovised" typo | fixed in `INTERACTIVE_EXPEDITION_SITES.md` |

No findings on #787 or #788.

---

## Resolved model

The five decisions collapse into one mechanism. This section is the spec;
the gap sections below keep the problem analysis and note what changed.

1. **One site cooldown.** Any terminal run blocks the site for that vault
   for 7 days; after 7 days the site fully resets — rooms *and* finale.
   D5-B's "reset window" is this same clock, so there is no separate
   room-refresh rule. Implement as a single `finished_at` timestamp on the
   run, set on every terminal transition; rename the current `cleared_at`
   field while the feature is still unmerged. The cooldown query covers all
   terminal statuses.
2. **One open run per vault/site.** Enforced by a partial unique index on
   `(vault_id, site_id)` where `status IN ('ENTERED','IN_ROOM')`. The index is
   a backstop, not the whole claim rule: entry must re-check cooldown and
   create its run under the same vault/site serialization used by terminal
   transitions. Otherwise an entry that checked before a prior run finished
   can insert just after that run becomes terminal. This shared claim also
   protects finale payout; no separate finale-only claim is needed.
3. **Defeat does not advance.** On combat defeat (survivor), stay in the
   room and offer push-on / retreat. Stop the enemy pack at the first defeat.
   XP is credited once on room clear, tracked run-locally in
   `expedition_run.flags` — no vault-wide room ledger.
4. **Clock = events paused, time running (D1-A).** While a run is open the
   tick skips *event generation* but the wall clock keeps ticking. On clock
   expiry with an open run: auto-retreat it, then start the return leg. A
   recall with an open run force-retreats first.
5. **Locking.** `resolve_node`, `retreat_run`, entry, and the return
   transitions lock the exploration row and re-check `ACTIVE` under that
   lock. Define one acquisition order for exploration, vault/site claim,
   and run locks before implementation; use it on every path.

### Deleted by these choices (do not implement)

- vault/site/room payout **ledger** (D2-B makes the cooldown the reset)
- separate finale-only **claim** lock (the shared vault/site claim protects
  cooldown, entry, and terminal payout)
- per-enemy **durable progress** (D3-A is run-local)
- full **clock freeze** with `paused_seconds` (D1-A needs no time math)

---

## Gap 1 — An open site could outlive its exploration

### Problem

Two lifecycles shared one row and only touched at entry. The tick had no
expedition awareness (random events fired mid-site, clock drained, dweller
could start the return leg mid-room). `resolve_node` never checked
`is_active()`, so a run could be resolved after return rewards were settled
— writing into a completed exploration. The UI only reconnected on active
explorations, so a run left open past completion was reachable by API but
not UI, and blocked future entry. A random death mid-site left the run open
until the next resolve. On finalize the dweller went IDLE while the run
dangled.

### Rule

1. Lock the exploration row; re-check `ACTIVE` **under the lock**. Include
   the shared vault/site claim and run in a consistent lock order wherever
   those resources are needed.
2. Skip event generation while a run is open (wall clock keeps running).
3. Clock expiry with an open run: auto-retreat it, then start the return leg.
4. Recall with an open run: force-retreat first.
5. Show remaining exploration time before entry; warn that expiry forces a
   retreat.
6. Defensive UI: a run open on a non-active exploration renders a
   recovery/close state, never a resolvable room.

### Tick risk

`dwellers_tick.process_explorations` loads a vault's explorations in bulk and
processes them in one session; `recover_session` rolls back and expires
instances on failure. Lock and re-read per exploration at its decision
point; do not hold locks across the vault sweep. Needs a focused
PostgreSQL concurrency test.

### Transaction boundaries

`crud.expedition_run.create_run` currently commits inside the CRUD call,
which would release the entry locks before the site event is recorded.
`apply_exploration_damage` also calls `mark_as_dead` with its default
`commit=True`, which can release resolve locks before the run is marked
`DIED`. Move these commits to the operation boundary when implementing the
shared claim and lifecycle transitions; keep death notifications consistent
with the resulting transaction. A lock-order rule alone cannot provide
atomicity across an inner commit.

---

## Gap 2 — Retreat allowed repeat room rewards

### Problem

The 7-day lock only saw `CLEARED` runs, so enter → grab room 1 → retreat →
re-enter re-paid the room. Multiple dwellers could enter before anyone
cleared, and concurrent runs could both reach the finale.

### Rule (superseded by the resolved model)

- Any terminal run (`CLEARED`, `RETREATED`, `DIED`) blocks the site for the
  vault for 7 days; the site fully resets after the window.
- One open run per vault/site, backed by the partial unique index. Serialize
  cooldown check plus entry against terminal transitions at that vault/site
  key; the index alone does not close a finish-versus-entry race.
- No per-room ledger or separate finale-only claim is required; see
  "Deleted by these choices".

---

## Gap 3 — Losing a fight still advances

### Problem

The PR promised "take rolled damage, offered push on / retreat." The code
advanced the cursor on any non-fatal outcome, so a dweller could lose every
fight — including the Mart boss — and still open the prize cage.

### Rule

- On combat defeat (survivor): stop the remaining enemies, stay in the
  room, show the defeat outcome, and offer **Push on** (retry the fight) vs
  **Retreat**. If combat came from a choice failure, keep that failed branch
  for the retry; do not reroll the original choice.
- Expose a `defeated` signal in the view so the modal renders a retry
  choice, not progress.
- Credit a successful room's enemy count to `enemies_encountered` once on
  clear (run-local `credited_rooms` in `expedition_run.flags`), rather than
  incrementing it on every attempted fight. Per-enemy victories are
  insufficient: a partial pack then retry would leak XP. Exploration XP
  also counts log entries, so repeated failed site attempts must not earn
  additional event XP merely by appending another site event. Persist flag
  changes explicitly; in-place mutation of the JSONB dict is not tracked
  automatically.

---

## Gap 4 — Reward promise and UI recovery (no decisions needed)

1. `roll_gear` returns the first item when every rarity-floor attempt
   misses, so "rare-or-better" is not guaranteed. Select the guaranteed
   item from catalog entries at or above the floor, and reject site content
   whose reward pool has no eligible item.
2. Resolve/retreat errors are stored on the Pinia store but only rendered
   in the picker; a failed room action looks like a no-op. Render
   `store.error` in the room pane and clear it on the next action.
3. The shared Pinia `room` is not keyed to the open exploration; navigating
   between explorers can show a stale room. Guard on `room.exploration_id`.

---

## Cross-cutting notes

- Gaps 1–3 reshape `resolve_node` / `retreat_run` and the run lifecycle.
  Implement as one coherent backend change, not three passes.
- These fixes make the manual picker safe. Discovery prompts are a separate
  gameplay step: decide whether a time-limited offer is a run state or a
  separate one-use opportunity before adding it, and inherit the same
  cooldown and claim rules.
- Nothing here changes the random-event economy or currencies.

## Sequence

Backend (Gap 4.1 + Gaps 1–3 with the model) → frontend (Gap 4.2/4.3 + the
Gap 1 time/recovery UI) → a real browser playthrough through return **and**
reward collection. Do not treat the feature as player-facing before Gaps
1–3 land.
