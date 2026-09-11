# World Map Delivery Plan

This document owns implementation sequencing, delivery status, verification, and future-phase contracts for
the World Map. Feature behavior belongs in [World Map — Multiplayer-First](features/WORLD_MAP.md) and
[The Wasteland Journal](features/WASTELAND_JOURNAL.md).

## Current status

**Phase A — The Wasteland Journal:** **shipped in v2.46.0.**

The release provides a per-explorer journey record, discovery-to-map links, event-authoritative map routes,
and viewer-independent temporary vault signals. It also consolidates exploration progress calculation, removes
two obsolete exploration components, and fixes quest party-member rendering.

**Discovery unlock fix (v2.46.1 follow-up):** released in v2.46.1. `register_discovery` now links the
exploring dweller to the DISCOVERY marker with `is_unlocked=True`, so discovered locations unlock immediately
instead of staying locked (previously only bio-linked places could unlock, via chat). A backfill script
(`uv run fo-cli backfill backfill-unlock-discoveries`) repairs pre-fix rows. Deploy the v2.46.1 worker image to activate the
runtime fix.

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
- [x] Unlock DISCOVERY markers by linking the exploring dweller (`is_unlocked=True`); backfill pre-fix rows.

### Verification recorded for v2.46.0

| Check | Result |
|---|---|
| Backend focused exploration/map/place tests | 59 passed |
| Backend `ruff check` | clean |
| Frontend focused map/journal tests | 37 passed |
| Frontend typecheck and lint | clean |
| Diff whitespace check | clean |

### Verification recorded for the discovery-unlock follow-up

| Check | Result |
|---|---|
| Backend discovery/map/CRUD/backfill tests | 40 passed |
| Backend `ruff check` | clean |
| Backfill idempotency (re-run reports 0 changes) | verified |

## Shared Places Registry — active plan of record (former Phase D, promoted)

**Decision:** the map moves to a shared world with a canonical **places registry**. This promotes the former
Phase D sketch (`WorldLocation` + `VaultLocationState`) from *"deferred until cross-vault queries justify it"* to
the active foundation. Cross-vault **state** features — raiding, visits, leaderboards, fallen-dweller
encounters — remain deferred (see below). The registry exists so geography is globally consistent and lore is
authored once; it does not introduce live shared simulation.

### Target model

| Table | Scope | Contents |
|---|---|---|
| `WorldLocation` | global canonical | `normalized_name` (unique merge key), `kind` (`PLACE` / `VAULT`), `vault_number` (partial-unique; real-vault link), `coord_x/y`, canonical `description`, `source` (`seed` / `emergent`) |
| `VaultLocationState` | per-vault fog | `vault_id`, `location_id`, `type` (unchanged `LocationTypeEnum`), `exploration_id`, per-vault `description`, first-seen |
| `DwellerLocation` | per-dweller relation | unchanged semantics; FK repointed to `WorldLocation` |

- **Coordinates live in the registry**, derived from `schematic_coords(name)` plus a **registry-level** collision
  nudge (one global occupied set, first-insert-wins) instead of today's per-vault nudge. Names remain coordinate
  authority; a curated seed may override coordinates on first insert only.
- `type` (ORIGIN / VISITED / DISCOVERY / HOME_VAULT) is **per-vault** and moves unchanged onto
  `VaultLocationState` — a place is one player's origin and another's discovery. The `locationtype` PG enum is
  reused, so no `DROP VALUE` problem; only `placekind` is new.
- API/wire shape is unchanged (the service layer owns it); no compatibility view.

### Phases

| Phase | Scope | Gate |
|---|---|---|
| **0** | Docs + decisions (this change) | — |
| **1** | Registry schema + one transactional migration (dedupe by name, backfill state, repoint FK, drop old table, `placekind` + enum snapshot) | Row-count parity old vs new; PG integration migration test |
| **2** | Rewire services/CRUD onto registry + state (`register_bio_places`, `get_vault_map`, `ensure_home_marker`) | Existing `test_map_service` / `test_map` / `test_discovery_events` pass **unmodified** |
| **3** | Seed JSON + idempotent loader; NPC vault rows; delete hardcoded `_KNOWN_*` lists and runtime `seeded_vault_specs` path | Golden test: seeded roster matches old `seeded_vault_specs()` output |
| **4** | Race mechanics: newborn race (bug), breeding eligibility, distribution, dossier visibility | Breeding tests preserved; new eligibility covered |
| **5** | Map presentation: registry lore on markers, region/tag filtering, fog UX | Frontend contract verified (no `types:generate` diff) |
| **6** | *Deferred:* raids, visits, fallen dwellers, leaderboards | Revisit with product direction |

Phases 1–3 (registry) and phase 4 (race) are independent; either order works. The race newborn fix is a live bug
and may ship first.

### Migration strategy (phase 1)

One transactional Alembic revision: create `placekind` + both tables; backfill `WorldLocation` by iterating the
current rows ordered by `created_at, id`, deduping on `normalized_name`, assigning `schematic_coords` +
registry-level nudge; backfill `VaultLocationState` (carrying `type`, `exploration_id`, description, first-seen);
repoint `DwellerLocation` via a normalized-name join; drop `wastelandlocation`; add `placekind` to
`PG_ENUM_LABELS_SNAPSHOT` in the same commit. Coordinate divergences from the old per-vault nudge are **logged as a
migration report** rather than retained in a review table (documented deviation from the earlier Phase D.1
wording). Zero data loss is proven by a PostgreSQL integration test.

### Seed strategy (phase 3)

One `backend/app/data/places/seed_places.json` = the union of curated sources (the bio-place regex lists, template
origin/visited places, the procedural place pool). Combinatorial discovery names and AI free-form names are **not**
seeded — they register emergently. Upsert by `normalized_name` (`DO NOTHING` for name/coords; seed-owned
description/tags only), run idempotently on startup plus a `fo-cli seed-places` escape hatch, so seed edits never
need a migration.

### Risks

- **FK swap on `DwellerLocation`** — single-transaction revision + per-vault 1:1 name mapping + count assertions +
  PG integration test.
- **Marker shifts** from dropping per-vault nudge — cosmetic (≤3 grid units); divergences logged; changelog note.
- **Discovery semantics** — discovery routes already project from `Exploration.events` (Phase A), so they survive
  the table swap; keep `type` / `exploration_id` / `is_unlocked` semantics byte-identical and let the unmodified
  discovery/map suites prove it.

### Open decisions (settle before the noted phase)

1. **Breeding rule shape** — per-race `can_breed` boolean vs partner-compatibility matrix. *(before phase 4)*
2. **Newborn race** — deterministic inheritance vs inheritance + mutation chance. *(before phase 4)*
3. **Race effects** (ghoul radiation immunity, etc.) — phase 4 or the separate parked roadmap item. *(before phase 4)*
4. **Seed scope** — confirm excluding combinatorial discovery names (emergent). *(before phase 3)*
5. **Ordering** — registry-first (1→2→3) vs race bug (4a) first. *(now)*

## Deferred multiplayer phases (parked)

Raiding and the social/multiplayer **state** layers remain deferred. The registry they would depend on (formerly
Phase D.1) is now the **active plan of record** above. Everything below is retained for when that state work is
revisited; nothing in this section is being implemented now.

### Phase B — async raiding

1. Introduce a stable `RaidTarget` keyed by target vault number plus snapshot version. The snapshot contains
   only raid-relevant rooms, defenses, and eligible dwellers; never query a live vault while resolving combat.
2. Give every real vault a marker derived from `normalize_place_name(f"Vault {number:03}")`. The global
   roster remains only for NPC signals. A real marker replaces its matching NPC signal without moving.
3. Add a `raid` exploration subtype with an idempotency key and explicit state machine:
   `created → travelling → resolving → resolved|expired`. Apply rewards and losses in one transaction and
   persist a durable result event for attacker and defender.
4. Authorize target discovery server-side. The client may display a signal but cannot select arbitrary vault
   IDs, request an old snapshot, or infer private dweller details from the map response.

### Phase C — fallen-dweller encounters

1. Add `FallenDwellerRegistry` as an immutable, minimal encounter projection: public combat stats,
   deterministic encounter seed, transformation flags, source-vault pseudonym, and lifecycle state. Do not
   expose a dead dweller's full biography or source-vault identity.
2. Claim/resolution must be idempotent and use row-level ownership or a lease so concurrent explorers cannot
   consume the same encounter twice.
3. Seed encounter placement from registry ID/name, not death time or viewing vault, and retain a tombstone or
   audit result for replay and support.

### Phase D — social world registry

1. **Promoted** — `WorldLocation` (normalized-name authority and canonical coordinates) plus
   `VaultLocationState` (discovered/unlocked/first-seen metadata) are now the active plan of record above. The
   coordinate-conflict policy there supersedes the earlier "retain conflicts for review" wording: canonical
   coordinates are recomputed from the name (the authority) and divergences are logged.
2. Vault visits require an explicit friends/permission graph and versioned, read-only vault snapshots. Map and
   leaderboard responses use privacy-safe aggregate data, pagination, and rate limits.
3. Add observability before global queries: registry conflict count, route projection failures, raid resolution
   retries, and per-vault map payload size. The registry above ships on the shared-places goal; cross-vault
   *state* queries still wait until they, not speculation, justify their own work.

## Deferred outside the map plan

- Exploration events with player choices — now planned in phases, see the roadmap's World Map focus list.
- Absolute radiation trend — deltas are persisted (`radiation_gain` on event records); charting them in the
  journal is the remaining step (see roadmap).
