# World Map Delivery Plan

This document owns implementation sequencing, delivery status, verification, and future-phase contracts for
the World Map. Feature behavior belongs in [World Map — Multiplayer-First](features/WORLD_MAP.md) and
[The Wasteland Journal](features/WASTELAND_JOURNAL.md).

## Current status

**Phase A — The Wasteland Journal:** implemented locally; pending commit/release.

The release provides a per-explorer journey record, discovery-to-map links, event-authoritative map routes,
and viewer-independent temporary vault signals. It also consolidates exploration progress calculation, removes
two obsolete exploration components, and fixes quest party-member rendering.

## Phase A delivery checklist

- [x] Persist discovery `location_id` and unscaled map coordinates on JSON event records; no migration.
- [x] Project ordered `discovery_routes` from `Exploration.events`, rather than from a de-duplicated
  `WastelandLocation.exploration_id`.
- [x] Keep historic events that have no route metadata compatible; they produce no trail segment.
- [x] Add journal loot presentation and cumulative health-change trail. Automatic Stimpak use records its
  healing delta.
- [x] Link discovery events to `/vault/:id/map?place=<location_id>`.
- [x] Use a fixed global neighbor-signal seed, with regression coverage.
- [x] Consolidate exploration progress logic; delete `ExplorationConfigModal.vue` and `DwellerDropZone.vue`.
- [x] Populate quest party members for quest cards.

### Verification recorded for the current working tree

| Check | Result |
|---|---|
| Backend focused exploration/map/place tests | 59 passed |
| Backend `ruff check` | clean |
| Frontend focused map/journal tests | 37 passed |
| Frontend typecheck and lint | clean |
| Diff whitespace check | clean |

## Phase B — async raiding

1. Introduce a stable `RaidTarget` keyed by target vault number plus snapshot version. The snapshot contains
   only raid-relevant rooms, defenses, and eligible dwellers; never query a live vault while resolving combat.
2. Give every real vault a marker derived from `normalize_place_name(f"Vault {number:03}")`. The global
   roster remains only for NPC signals. A real marker replaces its matching NPC signal without moving.
3. Add a `raid` exploration subtype with an idempotency key and explicit state machine:
   `created → travelling → resolving → resolved|expired`. Apply rewards and losses in one transaction and
   persist a durable result event for attacker and defender.
4. Authorize target discovery server-side. The client may display a signal but cannot select arbitrary vault
   IDs, request an old snapshot, or infer private dweller details from the map response.

## Phase C — fallen-dweller encounters

1. Add `FallenDwellerRegistry` as an immutable, minimal encounter projection: public combat stats,
   deterministic encounter seed, transformation flags, source-vault pseudonym, and lifecycle state. Do not
   expose a dead dweller's full biography or source-vault identity.
2. Claim/resolution must be idempotent and use row-level ownership or a lease so concurrent explorers cannot
   consume the same encounter twice.
3. Seed encounter placement from registry ID/name, not death time or viewing vault, and retain a tombstone or
   audit result for replay and support.

## Phase D — social world registry

1. Introduce `WorldLocation` (normalized-name authority and canonical coordinates) plus
   `VaultLocationState` (discovered/unlocked/first-seen metadata). Backfill per-vault rows by normalized name
   and compare coordinates before merging; retain conflicts for review rather than silently moving markers.
2. Vault visits require an explicit friends/permission graph and versioned, read-only vault snapshots. Map and
   leaderboard responses use privacy-safe aggregate data, pagination, and rate limits.
3. Add observability before global queries: registry conflict count, route projection failures, raid resolution
   retries, and per-vault map payload size. Migrate only once cross-vault queries, not speculation, justify it.

## Deferred outside the map plan

- Exploration events with player choices.
- Persisted radiation deltas and an absolute radiation trend.
