# Dweller Bio → World Map Uncovering (Rarity-Scaled)

> Status: Proposed design (2026-08-08). Validated against existing systems.
> Predecessor docs: `docs/EXPLORATION_SYSTEM.md`, `docs/features/SOFT_DELETE.md`.

## Goal

Make the world map uncover naturally as the player builds a population — without
requiring paid AI generation, and without flooding the map with hundreds of markers.

## Core Insight (why this is cheap)

The bio→map pipeline **already exists**:

- `map_service.register_bio_places()` upserts a dweller's `origin` + up to 5
  `visited` places as `WastelandLocation` markers whenever a bio is generated.
- `DwellerBio.vue` already linkifies place names in bios; clicking one navigates
  to `/vault/{id}/map?place={locationId}`.

The only gaps are:
1. Bios are `NULL` by default → the map stays empty until the player pays AI tokens.
2. The visited-places cap is flat (5) for every dweller — rarity is ignored.
3. Radio recruits are 100% common → no variety, and no rare-content pipeline.

This design fills those gaps with procedural content + config, not new systems.

## Design

### 1. Default procedural bios (free, no AI)

Every new dweller receives a **template bio** at creation (or lazily on first
chat — pick ONE trigger, see below). Template bios are deterministic strings
like:

> "Born in {origin}. Spent years drifting through {place1} and {place2} before
> the vault opened its doors."

- Origin + visited places are drawn from a curated place-name pool.
- The bio is stored in `Dweller.bio` and fed through the existing
  `register_bio_places()` flow → map markers appear immediately.
- **No AI call, no quota charge.** AI-generated bios (`generate-bio`,
  `extend-bio`) remain a premium, manual, paid upgrade that can enrich the
  same markers.

**Trigger decision:** generate at creation time (simplest, map fills as you
recruit) vs. lazily on first chat. Recommend **creation time** — one code path,
no chat coupling.

### 2. Rarity scales how much a dweller uncovers

Replace the flat 5-place cap in `register_bio_places` with a rarity-driven cap
(config-driven):

| Rarity | Origin | Visited places |
|---|---|---|
| common | 1 | 1–2 |
| rare | 1 | 3–4 |
| legendary | 1 | 5 |

- Rare/legendary dwellers are scarcer, so their higher yield stays balanced.
- Cap total per-vault markers as a backstop (e.g. hard ceiling on
  ORIGIN/VISITED rows) to prevent endless growth; the existing
  single-dweller-VISITED clutter filter in `WorldMap.vue` already reduces noise.

### 3. Radio: small rare chance (optional, recommended)

Keep radio as-is but add a configurable small % chance to roll a **rare**
dweller (e.g. 3–5%). Legendary/unique NEVER come from radio — they stay
quest-exclusive to preserve their value.

### 4. Quests = the premium source of rare/unique dwellers + map places

Quest chains (already modeled via `chain_id` / `previous_quest_id` /
`next_quest_id`) are the primary source of rare/legendary/unique dwellers:

- Chain-end quest rewards grant named (unique) dwellers via the existing
  `grant_dweller` (rarity already supported in reward templates).
- Unique dwellers ship with a **hand-authored bio** referencing the chain's
  locations → completing a chain uncovers its region on the map.
- Quest rewards already support items + dwellers + caps; no reward-system
  changes required — only JSON content.

### 5. Balance guardrails

- AI bio generation stays manual + quota-gated (no free AI for everyone).
- Per-dweller place caps are low (1–5) so a large vault doesn't drown the map.
- **Surface `register_bio_places` silent failures** (known issue, ROADMAP
  v2.26): if bio→map is the core mechanic, log-and-swallow is unacceptable —
  add user-visible surfacing or retry semantics.

## Affected Areas

| Area | Change |
|---|---|
| `backend/app/services/map_service.py` | rarity-scaled visited cap; failure surfacing |
| `backend/app/utils/dwellers.py` | procedural template bio in `create_random_common_dweller` |
| `backend/app/crud/dweller.py` | pass bio through creation path |
| `backend/app/services/radio_service.py` | optional rare roll (config) |
| `backend/app/core/game_config.py` | `bio.visited_by_rarity`, `radio.rare_chance` |
| quest seed JSON | chain-end unique dwellers with bio + locations |
| `frontend` | nothing required (linkify + map already render bio places) |

## Non-Goals

- No new "unique" rarity enum (use existing COMMON/RARE/LEGENDARY + named
  templates).
- No AI-generated default bios.
- No changes to exploration/discovery systems.
