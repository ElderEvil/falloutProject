# Map place identity — material loot and XP by destination

Status: **P0–P2 implemented and verified; per-place overrides and discovery identity deferred.**
Owner: maintainer. Related: `docs/features/LOCATION_KINDS_AUDIT.md`,
`docs/features/WASTELAND_COMBAT_EXPANSION.md` (next pass, line 125), `#1254` (ranked exploration
backlog), `#1193` (site alerts — precursor, not this plan),
`backend/app/data/places/place_groups.json`.

First playable milestone is **P0–P2**. Overrides wait for the playtest, and discovery identity is
deferred.

## Goal

Every clearable map place should earn its archetype, so the player picks a destination **for a
reason** — a specific material or levelling — because the alternative is choosing the nearest
reachable pin.

Observable end state: a player who needs Adhesive can name the place that gives it, and a player
levelling a dweller can name a different one. Today both picks pay the same loot and no XP.

## Why this is small

The identity machinery already exists; it is nearly empty.

| Layer | Today | Evidence |
| --- | --- | --- |
| Archetype catalog | 19 groups, 15 clearable, each with `risk / clearable / reclear_hours / loot_table / base_difficulty` | `backend/app/data/places/place_groups.json` |
| Loot tables | **three** tables (`low`/`medium`/`high`) shared by all 15 clearable groups | `backend/app/data/places/place_loot.json` |
| Table content | caps range + a flat `{type, rarity}` list; every entry is awarded | `place_loot.json`; `dispatch_resolution.py` |
| Reaction | `min(5, base_difficulty + tier)`, tier = `clear_count` capped at 3 | `services/exploration/dispatch_resolution.py` |
| Cooldown | **every** clearable group: `reclear_hours: 168` | `place_groups.json` |

A dispatch clear also awards **0 XP**: `rewards_calculator.calculate_exploration_xp` counts only
`total_distance`, `enemies_encountered` and non-site events, none of which a dispatch increments
(verified: those counters are written only in `event_service.py` and `expedition.py`).

Identity is **per archetype, not per place**: `worldlocation` has no loot/difficulty/XP override
column. Ungrouped emergent places already resolve to the generic `wasteland_site` archetype when
`features.emergent_sites` is on (`utils/place_groups.effective_place_group`), so the gap is that
they are *generic*, not that they are inert.

## Decisions

- **D1 — Identity is a category filter, not item names.** Junk carries `junk_type` (Circuitry,
  Leather, Adhesive, Cloth, Science, Steel, Valuables) and crafting already consumes `junk_types`;
  weapons carry `weapon_type`. Loot entries gain optional `junk_types` / `weapon_types`.
- **D2 — Each themed table dedicates its signature slot.** The **first entry** of a themed table is
  filtered to one material and always rolls, so "gas stations roll Adhesive" is a promise rather
  than a probability. Proportional haul loss can still drop it when a party loses members, so the
  map preview calls it a **guaranteed roll**, never a guaranteed drop. Remaining entries are
  incidental and may overlap neighbours; the preview labels the two differently.
- **D3 — XP is one nullable integer, `Exploration.location_xp`.** It stores **base XP per survivor**
  for this clear, tier-scaled, *before* survival, luck and pet bonuses. Settlement adds those
  bonuses and scales by recall progress through the existing path. A single int replaces the
  earlier JSONB idea because XP is the only planned field.
- **D4 — The snapshot is written at resolution and paid at settlement.**
  `resolve_dispatch_arrival` runs under the vault/site claim lock and knows whether the point was
  held; `coordinator.finalize_return` pays it and owns the commit. `NULL` means the run cleared
  nothing (wipe, retreat, salvage, non-dispatchable point), so settlement pays nothing. This also
  prevents a dispatch-then-recall XP farm.
- **D5 — Timeout resolves like arrival; it is not an XP exception.** The tick routes both a spatial
  arrival (`arrived=True`) and an elapsed timer (`resolve_dispatch_arrival(id)`) into the same clear
  resolution, so either path may clear the point and snapshot XP. The anti-farm property comes from
  the reclear cooldown and `clear_count`, not from arrival semantics. Whether a spatial run that
  times out *before reaching its target* should abort instead of resolving is a pre-existing
  behaviour question that also affects loot, not an XP rule; it stays out of this change.
- **D6 — Inert archetypes stay inert.** `settlement`, `city`, `landmark`, `region` remain
  non-clearable except where a bound collectible gives them a one-time **Search**.
- **D7 — XP-per-hour is the levelling lever, not raw XP.** Cooldown stays tied to risk, so XP is
  tuned to keep a clear ordering per hour (below). Equal raw XP with different cooldowns is the
  trap to avoid: 60 XP / 72 h and 110 XP / 120 h are nearly the same reward.
- **D8 — Discovery identity is deferred.** Assigning a discovered place a themed `group_key` would
  make it clearable **with `emergent_sites` off**, because `effective_place_group` resolves an
  explicit key before checking the flag. A later phase must add a separate `inferred_group_key`
  honoured only while the flag is on, and must cover both registration paths: bio/AI places and
  random discoveries (today both reach `crud.world_location.get_or_create_location`).

## Player loop (target)

1. Open a known place. The preview states:
   - **Signature material** (guaranteed) and incidental salvage,
   - **Base XP per survivor** — tier raises it; survival, luck and pets add on top at settlement,
   - when it re-clears.
2. Dispatch a party; tier and difficulty behave exactly as today.
3. On return, the reward summary shows caps + items + the XP actually granted per survivor.
4. The player re-chooses the next destination by yield, not by distance.

## Data changes

### 1. `place_loot.json` — themed tables with a signature slot

`low/medium/high` stay (fallback, and `wasteland_site` still uses `low`). Signature entry first:

| Table | Signature (guaranteed) | Incidental | Other |
| --- | --- | --- | --- |
| `automotive` | Adhesive | Steel, Leather | common outfit |
| `household` | Cloth | Valuables, Leather | common outfit, rare Cloth/Valuables |
| `tech` | Circuitry | Science | rare Circuitry, common outfit |
| `medical` | Science | Cloth | rare Science, rare outfit |
| `military` | rare Gun/Heavy weapon | rare Steel | rare outfit, legendary Gun/Heavy |

Every junk type is reachable, and each signature has exactly one dedicated source, so the material
goal maps to a destination.

### 2. `place_groups.json` — theme, XP and cadence

| `group_key` | loot table | `xp_reward` | `reclear_hours` | XP/h | Role |
| --- | --- | ---: | ---: | ---: | --- |
| `gas_station` | automotive | 20 | 48 | 0.42 | Adhesive |
| `supermarket` | household | 25 | 48 | 0.52 | Cloth |
| `entertainment` | household | 30 | 48 | 0.62 | Cloth |
| `ruin` | household | 45 | 72 | 0.62 | Cloth |
| `metro` | household | 55 | 72 | 0.76 | Cloth |
| `vertical_refuge` | household | 70 | 96 | 0.73 | Cloth |
| `factory` | tech | 60 | 72 | 0.83 | Circuitry |
| `power` | tech | 65 | 72 | 0.90 | Circuitry |
| `vault_tec` | tech | 85 | 96 | 0.89 | Circuitry |
| `observation_facility` | tech | 75 | 96 | 0.78 | Circuitry |
| `research` | medical | 150 | 120 | 1.25 | Science / XP |
| `military` | military | 165 | 120 | 1.38 | Weapons / XP |
| `brotherhood_outpost` | military | 200 | 168 | 1.19 | Weapons / XP |
| `exclusion_zone` | military | 220 | 168 | 1.31 | Weapons / XP |
| `wasteland_site` | `low` | 15 | 168 | 0.09 | Generic fallback |

`xp_reward` is required and `>= 0` on every clearable group and forbidden on inert ones — the same
rule `loot_table` already follows. `base_difficulty` stays on the existing risk bands so combat is
unchanged. Numbers are playtest starting points.

### 3. `place_overrides.json` — per-place deltas (after the playtest)

Keyed by `normalized_name`, mirroring `data/collectibles/bobbleheads.json`:
`{ "super duper mart": { "loot_table": "household", "xp_reward": 40 } }`.
Resolution order **override → group → default**, in one loader so dispatch, reads and settlement
cannot disagree.

## Code changes

| File | Change |
| --- | --- |
| `models/exploration.py` | nullable `location_xp` int on `Exploration` |
| `alembic/baseline_versions/` | one additive `ADD COLUMN`, no backfill (`NULL` is correct) |
| `utils/place_loot.py` | validate `junk_types` / `weapon_types` against the enums; reject a filter on the wrong item type |
| `services/exploration/loot_calculator.py` | optional category filter applied before the rarity bucket; empty filtered pool raises |
| `utils/place_groups.py` | require `xp_reward >= 0` on clearable groups; forbid it on inert ones |
| `services/exploration/dispatch_resolution.py` | pass entry filters to `roll_item`; snapshot `location_xp` on a held clear |
| `services/exploration/rewards_calculator.py` | additive `location_xp` term before bonuses |
| `schemas/wasteland_location.py` | (P2) `PlaceGroupRead` gains `xp_reward`, plus a signature-material label |
| `services/map/reads.py` | (P2) project the new fields |
| `frontend/.../MarkerDetailModal.vue` | (P2) signature material, incidental salvage, base XP per survivor |

## Phases

- **P0 — Loot identity.** Filters, themed tables, signature slots, per-archetype assignment.
- **P1 — XP yield.** `location_xp` snapshot + additive settlement term; fixes the zero-XP clear.
- **P2 — Map preview.** Signature/incidental labels derived from the live table, base XP per
  survivor for the marker's current tier, re-clear countdown; types regenerated. The return summary
  labels its figure **Total party XP**.
- **P3 — Per-place overrides**, only for places the playtest shows players target.
- **P4 — Discovery identity (deferred).** Needs `inferred_group_key` gated by `emergent_sites`, and
  both registration paths covered. Not part of this slice.

## Tests

- Every declared table entry resolves to a real catalog item in CI, so a valid category that
  matches an empty pool fails before play, not mid-resolution.
- A themed table's signature entry yields the signature material on every clear; incidental entries
  stay within their declared families.
- An unknown `junk_types` / `weapon_types` value fails catalog validation at import; a filter on the
  wrong item type fails too.
- The haul rolls **before** combat damage is staged, so a bad entry cannot persist damage without its
  loot when the tick swallows the error.
- A held clear snapshots `location_xp`; a wipe, retreat, salvage or non-dispatchable point leaves it
  `NULL`, and a held clear with a zero reward stores `0` so `NULL` keeps its meaning. **Both** the
  arrival path and the elapsed-timer path snapshot it (D5).
- Settlement pays `location_xp` once, adds survival/luck/pet bonuses to it, and scales by recall
  progress; settling the same run twice cannot pay twice.
- **Late settlement failure** after XP is staged: the run stays `RETURNING`, `dweller.experience`
  and `dweller.level` are restored, no level-up is emitted, and the retry delivers it exactly once.
- Map projection: `xp_per_survivor` scales with the reported tier, and the preview derives its
  signature/incidental split from the live loot table.
- Existing behaviour untouched: an entry without filters still rolls across the whole catalog, and
  `base_difficulty` still follows the risk bands.

## Playtest protocol

Give the tester **two reachable pins with different roles** — one material farm (Gas Station,
48 h, 20 XP) and one levelling destination (Military Site, 120 h, 165 XP) — and watch whether the
material goal and the levelling goal lead to different picks. Record, per clear: chosen place, why,
XP gained, material gained, travel time, and whether the place was reachable in time.

Success: after three clears the tester can name (a) one place they go for a material and (b) one
they are saving for levelling, and chose them by yield. Failure symptoms: they pick the nearest
pin; or they cannot tell which material a place guarantees.

## Non-goals

- No food/water/power yield from locations.
- No salvage-site or site-depletion system (`#1254`), no site-state redesign (`#1193`).
- Do not merge `ExpeditionSite` into `WorldLocation` (`LOCATION_KINDS_AUDIT.md`).
- No per-location enemy tables; dispatch combat stays archetype difficulty + tier.
- No new currency, no crafting changes, no feature flag.
