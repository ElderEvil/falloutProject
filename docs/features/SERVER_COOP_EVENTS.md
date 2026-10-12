# Server Co-op Events — Design Contract

> Status: **proposed, not implemented.** Feature-flagged off by default. This is the project's first
> multiplayer element; like `RESOURCE_ECONOMY_BALANCE.md`, the numbers are a playtest baseline, not a
> specification.

## Goal

Give players a visible sense that other vaults exist, without adversarial systems, realtime sockets, or
new infrastructure. A recurring **server-wide cooperative event** that every vault contributes to, with
a **personal threshold** and a **server-wide threshold**. Contribution comes from ordinary play.

## Why this shape

- **Cheapest real multiplayer signal.** No PvP, so nothing to grief and no balance arms race.
- **Reuses what exists.** The periodic-actor pattern (`refresh_weekly_objectives`), `event_bus` for
  contribution, `sse_manager` for live progress, the notification/toast/modal stack, and
  `FeatureConfig` for shipping dark.
- **Async only.** No websockets, no matchmaking, no live opponents.

## Current state (what we build on)

- **Objectives are per-vault.** `Objective` (template) + `VaultObjective` (instance) are refreshed by
  `refresh_daily_objectives` / `refresh_weekly_objectives` Dramatiq actors on a `periodiq` cron. There
  is **no global/cross-vault entity** — `GameState` is unique per `vault_id`, and `world_location` is
  per-vault too.
- **Redis is available** (used for refresh tokens) — usable for hot counters, but Postgres stays the
  durable source of truth.
- **`event_bus.emit(GameEvent.*, vault_id, data)`** already carries the game events we need
  (`QUEST_COMPLETED`, `OBJECTIVE_COMPLETED`, `ITEM_SCRAPPED`, `DWELLER_TRAINED`, …).
- **`sse_manager`** broadcasts to a vault or a user topic; the frontend already consumes SSE.
- **Feature flags** live in `game_config.FeatureConfig` and surface through `/system/features`.

Naming note: "vault events" (`VaultEventConfig`) already exist and are **per-vault** random rewards — a
different concept. This feature is deliberately named *server* co-op events to avoid the collision.

## Contract — entities

Add the first global game entity, plus per-vault participation:

- **`WorldEvent`** (global; at most one `ACTIVE`): `id`, `kind`, `status`, `goal`, `progress`,
  `started_at`, `ends_at`, `reward_tiers` (JSONB), `metadata` (JSONB).
- **`WorldEventParticipation`** (unique per `vault_id` + `world_event_id`): `contribution`,
  `personal_goal`, `reward_claimed_at`.

New enum `WorldEventStatus` (`SCHEDULED` / `ACTIVE` / `COMPLETED` / `FAILED`). New feature flag
`FeatureConfig.world_events` (default `False`), surfaced via `/system/features`.

No other existing column or table changes; `world_location` and vault state are untouched.

## Contract — lifecycle

A single new periodic actor, following the objectives pattern exactly:

- `refresh_world_events` on a `periodiq` cron (propose hourly): start the next scheduled event when no
  `ACTIVE` one exists and its window opens; close an `ACTIVE` one whose `ends_at` has passed.
- On **start**: create the `WorldEvent`, broadcast SSE, emit `WORLD_EVENT_STARTED`.
- On **completion**: settle rewards, mark `COMPLETED`, emit `WORLD_EVENT_COMPLETED`.
- One active event at a time; a rolling schedule (e.g. weekly) with a small kind rotation.

## Contract — contribution

Contribution is **mapped from existing `GameEvent`s**, not a new gameplay loop. A small handler
subscribes and adds a weighted amount:

| Source event | Proposed weight |
|---|---:|
| `QUEST_COMPLETED` | 25 |
| `OBJECTIVE_COMPLETED` | 10 |
| `ITEM_SCRAPPED` | 3 |
| `DWELLER_TRAINED` | 2 |
| incident resolved | difficulty × 5 (needs an event or a direct hook) |

Weights live in `game_config` (env-overridable), not inline, so the simulator and production share one
source of truth.

**Anti-abuse / fairness:**

- Per-vault, per-tick contribution cap, so one vault cannot dominate a server goal.
- Aggregation is an atomic increment on the durable row; a Redis counter fronts reads and is flushed
  periodically. Server-authoritative, as all simulation already is.
- Contributions are idempotent per source event (guard against double-counting on retry).

## Contract — rewards and surfacing

- **Personal threshold** per vault (reuse `reward_service`); **server threshold** for every participant.
- **Live progress** in the UI via SSE (a progress bar + recent contributors).
- **Progression red line:** start, milestones and completion surface as toast/modal **and** bell, never
  bell-only. New `NotificationType`s map as **always-on** categories in `notification_preferences`.
- **Leaderboard is opt-in to appear.** Default view is aggregate progress; showing a vault name is a
  player choice.

## Phasing

| Phase | Deliverable | Gate |
|---|---|---|
| 0 | This document | — |
| 1 | `WorldEvent` + lifecycle actor + read-only UI progress, one kind (e.g. "scrap N junk server-wide") | flag off |
| 2 | Contribution wiring from `GameEvent`s + personal/server reward settlement | flag off |
| 3 | Live SSE progress, milestones, recent-contributors / opt-in leaderboard | flag off |
| 4 | Rotation of kinds + schedule, balance pass | flag off |

Enablement is a per-deployment flag flip for playtest, then a balance pass before any default — the
same path the resource rate took.

## Guardrails

- **Feature flag** `FeatureConfig.world_events`, default `False`.
- **No new infrastructure**: Postgres + Redis + the existing `periodiq` cron and `dramatiq` actor
  pattern. No websockets, no matchmaking.
- **No cross-vault leakage** beyond aggregate progress and an opt-in leaderboard; a vault's contents,
  dwellers, and resources are never exposed.
- **Layering**: endpoint → service → CRUD; new logic in `services/`; the periodic actor is a thin
  wrapper, as the objectives actors are.
- **Enums in one place**: `WorldEventStatus` and the new `NotificationType`s live in
  `app/core/enums.py`; the PG enum migration is hand-written and `PG_ENUM_LABELS_SNAPSHOT` updated in
  the same commit.
- **Does not touch incident pacing, the resource economy, or the combat tuning** from the last pass.
- **One active event**, and settlement must be idempotent (a restarted worker cannot double-pay).

## Open questions (decide before Phase 1 code)

1. **Visibility.** Do players ever see another vault's name, or only aggregate progress + an opt-in
   leaderboard? (Proposed: opt-in only.)
2. **Can the server fail?** Is the world threshold always reachable (tiers: bronze/silver/gold), or a
   true pass/fail that can be lost? (Proposed: tiers — a losing shared goal is demoralizing.)
3. **Catch-up.** How do new/low-activity vaults contribute meaningfully against whales? Per-vault
   normalized targets, or flat personal goals independent of server total? (Proposed: flat personal
   goal; server total is the shared stretch.)
4. **Curation.** Which `GameEvent`s feed which event kind, and should a kind bias contributions (e.g. a
   "construction drive" weights `ROOM_BUILT`)? (Proposed: yes, one weighted theme per kind.)
5. **Always-on or opt-in?** Does the event exist for every vault, or only vaults that opt in?
   (Proposed: every vault sees it; participation is passive via normal play.)
6. **Reward shape.** Caps, loot crates, or a cosmetic/seasonal badge — and does the project have a
   cosmetic surface to hang a badge on yet?
