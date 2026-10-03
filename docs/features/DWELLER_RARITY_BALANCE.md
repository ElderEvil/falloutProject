# Dweller Rarity Balance — Decisions

> **Status:** Agreed direction, not yet implemented. Covers procedural dwellers and curated
> templates alike. Related: `DWELLER_TEMPLATES.md` (template system),
> `BIO_MAP_UNCOVERING.md` (bio → map flow), `BALANCE_FINDINGS.md` (simulator evidence).
> Canon reference: Fallout Shelter wiki / Fallout Wiki (rare ~level 6–7, legendary 19–43,
> 12/28/40 SPECIAL, lunchbox gear).

## Decision 1 — visited places capped by rarity, templates included

Well-traveled backstories are a rarity signal. Origin is identity and always registers;
*visited* history is what rarity gates:

| Rarity | Origin | Visited cap | Total |
|---|---|---|---|
| Common | always | 0 | origin only |
| Rare | always | 1 | 2 |
| Legendary | always | 2 | 3 |

Mechanically this is a `visited_by_rarity` config change (`{"common": 0, "rare": 1,
"legendary": 2}` — env `BIO_`, no code). Deliberately stricter than today
(`{1, 2, 3}`): a common vault-born dweller knowing distant ruins is flavor noise,
while a legendary wasteland hero knowing two places is character.

**Templates obey the same law.** Curated bios (e.g. Abraham Washington's four visited
places) are currently exempt via `cap_bio_places=False`. Exemption ends: authorial
intent does not outrank the discovery economy. Template authors pick the *best*
N places for the cap instead of listing every mention. (Bio text may still name-drop
freely — only map registration is capped.)

**Balance consequence:** bio registration feeds shared map markers, so this cap is a
**map-reveal-rate knob**. Tightening it makes exploration — not recruitment — the
map-filling engine. Intended, but verify in playtest that the early map does not go
quiet: commons still seed origins, rangs/rares still arrive.

## Decision 2 — starting levels closer to canon

| Rarity | Start level | Gear (canon) |
|---|---|---|
| Common | 1 | none |
| Rare | 6–10 | rare outfit, no weapon |
| Legendary | 19+ | legendary outfit and/or weapon |

Compressed where our content curve demands it, but canon-shaped: rares arrive
experienced, legendaries arrive veteran. SPECIAL spreads stay as today (procedural
rolls / fixed template values); level is about power-now, not stat budget.

## Decision 3 — flat HP gain stands (the canon loophole stays closed)

Canon ties HP growth to Endurance *at level-up*, which creates the degenerate
optimal strategy: hold dwellers at level 1 until Endurance is maxed, then level.
Punishing normal play to reward wiki-reading is a perverse incentive, and it
specifically gimped the flagship fantasy (a level-40 box legendary with mid
Endurance ends up squishier than a home-grown common).

Our `leveling.hp_gain_per_level` is flat per level by design: delaying level-ups
gains nothing, so the loophole is closed structurally rather than by policy.
No change needed; this note records *why* it must stay flat. Any future proposal
to reintroduce Endurance-scaled growth must also solve the hold-at-1 problem
(e.g. retroactive recompute) or it reopens the trap.

Under flat gain, starting level carries no HP penalty — a level-25 legendary is
simply closer to cap, not weaker. The remaining tuning question is
**power-now vs. pacing** (does a geared level-20 arrival trivialize the early
game?), which is playtest feel, not spreadsheet math.

## Out of scope

- SPECIAL budgets per rarity (unchanged).
- Breeding/legendary-baby odds (unchanged; the flat-gain formula already makes
  home-grown dwellers competitive without extra rules).
- Map-reveal pacing targets — to be observed after Decision 1 lands, not
  specified here.
