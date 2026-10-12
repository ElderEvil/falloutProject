# Balance Playtest — Slice 1 (verification + baseline)

> Branch `feat/balance-pass`, base `origin/master` @ `1847289c`. This slice **verifies** that the
> incident/resource simulators faithfully represent production, **fixes** the discrepancies with a
> failing test first, and **records baselines**. It performs **no value tuning** (that is slices
> 3a/3b). Nothing here changes production combat or resource formulas except the simulator kernel
> itself.

Reproducibility rule: every command below is copy-pasteable from `backend/` and pins a seed. The
matchup mode and the resource tier/size options are new in this slice; the tables are the output of
those exact commands.

## 1. Failing-test-first proof of the fixes

The kernel `app/services/combat/incident_sim.py` claimed (in its docstring) that
`TEAM_RESPONSE_BONUS`, `TEAM_HAZARD_RESIST` and radiation accumulation were "NOT modeled". Production
`incident_round.process_incident` / `apply_damage` model all three. The new parity tests were added to
`app/tests/test_services/test_incident_sim.py` **before** the kernel change and failed with:

```
TypeError: DefenderProfile.__init__() got an unexpected keyword argument 'reductions_radiation'
```

After the kernel/roster change the same file is green (24 passed). Fixes:

| # | Discrepancy | Production source | Fix |
|---|---|---|---|
| (i) | Team response power bonus | `incident_round.py`: `dweller_power = int(dweller_power * (1 + TEAM_RESPONSE_BONUS * len(active_ids)))` | `resolve_incident` applies the same multiplier for responders holding an active place on the incident's matching `HazardTeam` (`TEAM_RESPONSE_BONUS` imported from `hazard_team_service`). |
| (i) | Team hazard resist | `apply_damage`: `team_share = TEAM_HAZARD_RESIST if active` | Folded into the precomputed `DamageReductions` via `damage_reductions` shape (`_with_team`), so the resolver's multiplicative-complement combination stays the single source of truth. |
| (i) | Outfit resists | `damage_reductions` reads the equipped outfit | `synthetic_defenders` now wears a **catalog-shaped stub** (`_catalog_outfit`) — real `fire_resist`/`radiation_resist`/SPECIAL read from `game_data_store.outfits`, never a bare `Weapon`/`Outfit` constructor (item-factory guard). `snapshot_vault_defenders` already used the real equipped outfit. |
| (ii) | Radiation on irradiating incidents | `apply_damage`: `radiation_damage = min(dweller_damage - 1, dweller_damage // 2)` then `apply_radiation_gain(..., team_share=...)` | Kernel adds RAD via the profile's `reductions_radiation` (+ team share) and clamps health to `max(1, max_health - radiation)`. |
| (vi) | Tier-1-only resource rooms | `room_service.upgrade_room` evaluates the output formula at tier and multiplies by the tier multiplier | `simulate-resources` gained `--room-tier`/`--room-size`; `_make_room` now evaluates `output_formula` at the room tier. |

## 2. Effective configuration

Values actually in force when the baselines were taken (`uv run python -c` over `app.core.game_config`;
`base_production_rate` is a `RESOURCE_`-prefixed setting and was confirmed `0.1`).

```
game_loop.tick_interval              = 60
game_loop.incident_tick_seconds      = 2
incident.spawn_chance_per_hour       = 0.05
incident.min_vault_population        = 5
incident.spread_duration             = 60
incident.max_spread_count            = 0
incident.max_active_incidents        = 5
incident.spawn_cooldown_seconds      = 120
incident.difficulty_fire             = (2, 4)
incident.difficulty_radscorpion      = (3, 6)
incident.difficulty_raider           = (4, 7)
incident.spawn_weights               = FIRE 20, RADROACH 30, MOLE_RAT 25, RADSCORPION 12, RAIDER 10, FERAL_GHOUL 5, DEATHCLAW 2
combat.base_raider_power             = 10
combat.level_bonus_multiplier        = 2
combat.weapon_stat_weights.unarmed   = {str 0.2, per 0.1, end 0.1, cha 0.1, int 0.1, agi 0.1, luk 0.1}
combat.xp_per_difficulty             = 30
health.regen_per_tick                = 5
health.starvation_threshold          = 0.0
health.dehydration_threshold         = 0.0
resource.base_production_rate        = 0.1
resource.tier_multipliers            = {1: 1.0, 2: 1.5, 3: 2.0}
resource.power_consumption_rate      = 0.0083333 (0.5/60 per room-size-tier per second)
resource.food_consumption_per_dweller= 0.006 (0.36/60)
resource.water_consumption_per_dweller=0.006 (0.36/60)
resource.medical_production_rate     = 0.01
leveling.hp_gain_per_level           = 5
TEAM_RESPONSE_BONUS                  = 0.20
TEAM_HAZARD_RESIST                   = 0.20
QUALIFYING_INCIDENTS / TEAM_SIZE     = 3 / 3
TEAM_OUTFIT_NAMES                    = fire: Firefighter suit, radiation: Hazmat suit
features.race_mechanics / faction    = True / False
```

## 3. Incident baselines

Commands (from `backend/`, `seed=20261012`, 100 runs each; roster is 18 synthetic defenders —
`starting_dwellers 20 → starting_adults 18` — each aged level 5, SPECIAL 4, unarmed weapon average
damage 10; each run samples 1..6 responders, mirroring production's "whoever is in the room"
response):

```bash
uv run fo-cli simulate-incidents --matchup FIRE:2 --hazard-team fire     --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup FIRE:3 --hazard-team fire     --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire     --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:3 --hazard-team radiation --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4 --hazard-team radiation --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:5 --hazard-team radiation --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:6 --hazard-team radiation --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:4 --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:6 --runs 100 --seed 20261012
```

The FIRE and RADSCORPION rows assume a trained team of 3 active members (the vault's first 3
defenders) auto-equipped with the matching catalog outfit (Firefighter suit `fire_resist 0.5`;
Hazmat suit `radiation_resist 1.0`). RAIDER trains no team (`hazard_team_for` is `None`), so team
places change nothing for it.

| Matchup | Type | Diff | Resolved | Ticks p5 / mean / p95 | Damage p5 / mean / p95 | RAD mean (max) | Deaths (runs) |
|---|---|---|---|---|---|---|---|
| FIRE:2  | FIRE | 2 | 100/100 | 1 / 1.5 / 3 | 0 / 2.5 / 6 | 0 (0) | 0 (0) |
| FIRE:3  | FIRE | 3 | 100/100 | 1 / 1.8 / 4 | 1 / 4.7 / 12 | 0 (0) | 0 (0) |
| FIRE:4  | FIRE | 4 | 100/100 | 1 / 2.3 / 5 | 2 / 7.9 / 20 | 0 (0) | 0 (0) |
| RADSCORPION:3 | RADSCORPION | 3 | 83/100 | 3 / 10.1 / 30 | 12 / 38.6 / 72 | 12.4 (36) | 17 (17) |
| RADSCORPION:4 | RADSCORPION | 4 | 79/100 | 5 / 13.7 / 30 | 30 / 70.4 / 144 | 27.6 (72) | 47 (34) |
| RADSCORPION:5 | RADSCORPION | 5 | 62/100 | 8 / 18.2 / 30 | 64 / 101.6 / 180 | 38.9 (72) | 61 (44) |
| RADSCORPION:6 | RADSCORPION | 6 | 50/100 | 11 / 21.9 / 30 | 72 / 142.6 / 216 | 55.6 (108) | 92 (51) |
| RAIDER:4 | RAIDER | 4 | 79/100 | 6 / 14.4 / 30 | 48 / 80.2 / 144 | 0 (0) | 55 (38) |
| RAIDER:6 | RAIDER | 6 | 49/100 | 13 / 23.2 / 30 | 72 / 162.4 / 240 | 0 (0) | 94 (51) |

Reading: FIRE containment is trivially won (100%) even at its top difficulty; it deals almost no
damage. RADSCORPION is the lethal one — at difficulty 4 it already loses 21% of fights and kills in
34% of runs, and by difficulty 6 it is a coin flip. RAIDER sits between; its `p95 = 30 ticks` is the
no-defender timeout (30 sub-ticks at `incident_tick_seconds=2`), i.e. the fights that end in a loss.

## 4. Resource baselines

Commands (from `backend/`, `base_production_rate 0.100`; 60-minute run, starting 50/100 capped at 100):

| Scenario | Command | Workers | Rooms | Pop | Net power/min | Net food/min | Net water/min |
|---|---|---|---|---|---|---|---|
| starter  | `uv run fo-cli simulate-resources --population 10 --workers-per-room 1 --worker-special 1 --duration-minutes 60 --base-production-rate 0.1` | 1×SPECIAL 1 | tier 1, size 3 | 10 | +163.5 | +164.4 | +164.4 |
| growing  | `uv run fo-cli simulate-resources --population 20 --workers-per-room 2 --worker-special 3 --duration-minutes 60 --base-production-rate 0.1` | 2×SPECIAL 3 | tier 1, size 3 | 20 | +1003.5 | +1000.8 | +1000.8 |
| developed| `uv run fo-cli simulate-resources --population 30 --workers-per-room 3 --worker-special 6 --room-tier 3 --room-size 9 --duration-minutes 60 --base-production-rate 0.1` | 3×SPECIAL 6 | tier 3, size 9 | 30 | +26743.5 | +26773.2 | +26773.2 |

All three scenarios reach the 100 cap inside the first tick (nets are positive and large), so
forecasts read `0.3 min` (starter) or `<0.1 min` (growing/developed). Consumption is dwarfed by
production at these staffing levels; the numbers are only meaningful as a delta, not as an
absolute. The developed row shows tier+size scaling (`(2·S·(L+4)−2)` at `L=tier`, × tier
multiplier): a tier-3, size-9 room is ~160× the tier-1 size-3 net.

## 5. Approximation list (verified, not yet faithful)

Each item was checked against production and is **not** a value-tuning change.

1. **Passive regen is simulator-only.** `HEALTH_REGEN_PER_TICK` (`5`) is read nowhere in production —
   a repo-wide search finds its only use in `simulate_incidents` (`_regen_defenders`). The simulator
   heals every living defender 5 HP per 60 s tick, **including while an incident is active**, which
   production never does (only Stimpaks/medical actions heal). Baselines therefore overstate
   survival; set `--heal-per-tick 0` to approximate production. Documented, not changed, because the
   config field's "safe and fed" semantics have no implementation to mirror.
2. **Responder selection.** Production fights with the healthy adults in the incident's room plus
   the auto-dispatched hazard team (`incident_round.process_incident` + `dispatch_to_incident`). The
   simulator samples `1..defenders_per_incident` random defenders from the whole roster; room
   topology and the dispatcher are not modeled.
3. **Spread / duration.** At the shipped `max_spread_count = 0` the kernel matches production: an
   unopposed incident fails at `duration = spread_duration = 60 s` (30 sub-ticks), and a defended
   fight continues until it is won or all defenders die (`process_incident` has no duration timeout
   while defenders live). When `max_spread_count > 0` the simulator extends the effective duration
   instead of spawning in an adjacent room — the documented extended-escalation approximation.
4. **Team place earning / auto-dispatch / auto-equip are not simulated.** A defender is configured
   with the active team places and outfit it is assumed to already hold; the 3-incident qualification
   (`QUALIFYING_INCIDENTS`), bench promotion, and post-round outfit swap are production-only.
5. **Outfit SPECIAL bonuses.** The synthetic team outfit stub carries the catalog's resists, and its
   SPECIAL is read by `combat_power` — but non-team synthetic defenders wear no outfit/pet, and race
   is the human baseline (`race_mechanics` on, `faction_mechanics` off).
6. **Resource sim scope.** It drives `ResourceManager`'s private per-tick helpers, so it does **not**
   run `process_vault_resources` (no storage, warnings, or events); medical production (Medbay /
   Science Lab → Storage) is ignored; workers are bare `Dweller()`s (human, no outfit/pet, no
   `production_pct`, no apprentice junior multiplier); `population` is flat (child 0.7× consumption is
   not modeled); power consumption counts only the three production rooms, not other rooms; there is
   no offline catch-up (`max_offline_catchup`). Per-tick clamping and the power-outage gate
   (`current_power <= 0` skips non-STRENGTH rooms) **are** modeled.
7. **Known pre-existing quirks (out of scope, documented only).** Garden / Water-purification /
   Nuka-Cola rooms have no `output_formula` and are not representable by `simulate-resources`;
   `link_home_origin` lacks a rollback. Not touched in this slice.

## 6. Not yet verified by manual playtesting

- Whether the RADSCORPION lethality seen here (50% loss at difficulty 6 with a level-5, SPECIAL-4,
  unarmed roster) is intended, or an artifact of the untrained baseline roster. A real vault fights
  with equipped weapons and higher SPECIAL, which `--avg-special`/`--avg-weapon-damage` can model.
- Whether FIRE being a guaranteed, near-harmless win at all shipped difficulties is intended.
- Team-worthiness of the current `TEAM_RESPONSE_BONUS`/`TEAM_HAZARD_RESIST` values under a live vault
  with earned teams (the kernel models their effect; no player run has).
- Resource survival under real consumption (non-production room power draw, children, offline
  catch-up), which the flat simulator does not exercise.

---

# Balance Playtest — Slice 2 (repeatable response-team playtest)

> Branch `feat/balance-pass`. Appended after Slice 1; Slice 1 stays authoritative for the simulator
> fixes and baselines. Slice 2 turns the response-team loop into a **repeatable playtest**: a second
> person starts an isolated dev deployment with the environment overrides below, runs the protocol
> verbatim, and fills in the observation tables. Evidence that can run headless is recorded here as
> **SIM**; everything that needs a human in the browser (Game Control panel clicks, toast visibility)
> is **MANUAL-NEEDED** and happens during the protocol run. This slice performs **no value tuning**
> (that is still slice 3).

## 1. Acceptance criteria this protocol proves

| # | Line | How it is proven |
|---|---|---|
| A | Matching **active** teams are measurably better than the same defenders without them | SIM seeded matchups (table below) + manual FIRE/RADSCORPION rows for conditions C/D vs A/B |
| B | Benched and mismatched teams get **no** matching bonus | SIM negative controls + manual bench/mismatch rows |
| C | Qualification works through real play: 3 distinct incidents → active place | Manual qualification loop (3 distinct FIRE, then 3 distinct RADSCORPION) |
| D | The place auto-equips matching gear and surfaces as bell + toast | Manual loop round 3 checks; SIM/API-level test `test_qualification_loop_through_real_rounds_places_equips_and_notifies` |
| E | Repeat rounds of one incident never double-count participation | Existing test `test_participation_is_recorded_once_per_incident` (SIM) + manual 4th-incident roster check |
| F | Player can tell the team is helping from the UI alone | Manual "comprehensibility" column per condition |

## 2. Isolated deployment and environment overrides

Playtests run on a **throwaway instance**; the accelerated knobs below must never ride a shared or
production deployment.

Confinement (all mandatory):

- `ENVIRONMENT=local` (the default) — the settings model only allows `local`/`staging`/`production`;
  production-mode guardrails must never see the playtest knobs.
- A **separate** `compose`/`.env` copy for the playtest (own Postgres + Redis), never the shared or
  long-lived vault data.
- Do not reuse a vault you care about: the protocol spawns and kills incidents and equips outfits on
  purpose.

Verified environment-loading caveat (`app/core/game_config.py`, pydantic-settings 2.15):

- The top-level `GameConfig` declares `env_file=".env"`, but each nested config (`IncidentConfig`,
  `GameLoopConfig`, …) is built by `default_factory` from **OS environment only**. A key such as
  `INCIDENT_DIFFICULTY_FIRE` placed in `backend/.env` is read by the top-level source and then
  dropped as `extra="ignore"` — it never reaches `IncidentConfig`.
- Reproduced directly: `.env` with `INCIDENT_VAL=9` → nested value stays `5`; `export INCIDENT_VAL=9`
  → nested value becomes `9`.
- Consequence: **native `uv run` needs `export` lines**; a **Docker** deployment gets the same keys
  through `compose` `env_file:`/`environment:`, which arrive as real OS env in the container, so the
  overrides work there without extra steps.

Compose fragment (playtest service only):

```yaml
services:
  fastapi:
    environment:
      ENVIRONMENT: local
      INCIDENT_MAX_ACTIVE_INCIDENTS: "1"
      INCIDENT_MAX_SPREAD_COUNT: "0"
      INCIDENT_SPAWN_CHANCE_PER_HOUR: "1.0"
      INCIDENT_SPAWN_COOLDOWN_SECONDS: "120"
      INCIDENT_DIFFICULTY_FIRE: "[4,4]"
      INCIDENT_DIFFICULTY_RADSCORPION: "[4,4]"
      GAME_LOOP_INCIDENT_TICK_SECONDS: "2"
```

Native runner (from `backend/`, must be exported, not `.env`):

```bash
export ENVIRONMENT=local
export INCIDENT_MAX_ACTIVE_INCIDENTS=1
export INCIDENT_MAX_SPREAD_COUNT=0
export INCIDENT_SPAWN_CHANCE_PER_HOUR=1.0
export INCIDENT_SPAWN_COOLDOWN_SECONDS=120
export INCIDENT_DIFFICULTY_FIRE='[4,4]'
export INCIDENT_DIFFICULTY_RADSCORPION='[4,4]'
export GAME_LOOP_INCIDENT_TICK_SECONDS=2
```

Every Incident/GameLoop knob used, and why:

| Env knob | Value here | Default (shipped) | Why |
|---|---|---|---|
| `INCIDENT_MAX_ACTIVE_INCIDENTS` | 1 | 5 | One fight at a time so the qualification loop can never stack incidents; the spawn endpoint returns 409 while one is active |
| `INCIDENT_MAX_SPREAD_COUNT` | 0 | 0 | Spread disabled — a fight resolves on its own instead of jumping rooms |
| `INCIDENT_SPAWN_CHANCE_PER_HOUR` | 1.0 | 0.05 | Guarantees roughly one automatic incident per hour (safety net); the round cadence still comes from manual spawn (see §3) |
| `INCIDENT_SPAWN_COOLDOWN_SECONDS` | 120 | 120 | Unchanged; listed for completeness |
| `INCIDENT_DIFFICULTY_FIRE` | `[4,4]` | `(2,4)` | Pins every FIRE spawn to difficulty 4 (spawn endpoint rolls `randint(*range)`), so manual rows line up with the SIM table |
| `INCIDENT_DIFFICULTY_RADSCORPION` | `[4,4]` | `(3,6)` | Same for RADSCORPION_ATTACK |
| `GAME_LOOP_INCIDENT_TICK_SECONDS` | 2 | 2 | Combat round cadence; unchanged (listed for completeness) |

Do **not** widen caps or add endpoint parameters on this branch — if a knob is truly missing, record
it in §6 as a playtest gap and leave it for a later slice.

## 3. Playtest settings (effective values)

`uv run python -c "from app.core.game_config import game_config; print(game_config.incident.model_dump())"`
with the exports above must report the pinned values. Effective configuration for this slice:

```
incident.max_active_incidents       = 1
incident.max_spread_count           = 0
incident.spawn_chance_per_hour      = 1.0
incident.spawn_cooldown_seconds     = 120
incident.difficulty_fire            = (4, 4)
incident.difficulty_radscorpion     = (3, 6) → (4, 4) with the export
game_loop.incident_tick_seconds     = 2
game_loop.tick_interval             = 60
QUALIFYING_INCIDENTS / TEAM_SIZE    = 3 / 3
TEAM_RESPONSE_BONUS / TEAM_HAZARD_RESIST = 0.20 / 0.20
TEAM_OUTFIT_NAMES                   = fire: Firefighter suit, radiation: Hazmat suit
```

Cadence note (verified): incident spawning rolls `spawn_chance = chance_per_hour * seconds_passed/3600`
against a cap of 2 hours of chance, evaluated on the 2 s incident tick. So `1.0/hr` still averages
**one automatic spawn per ~hour of wall-clock** — it cannot pace a 10–15 min playtest. The protocol
uses the manual spawn controls for round cadence; normal pacing is deliberately unchanged, and a
better debug cadence than `1.0/hr` (e.g. a debug-only cooldown override) is a future-slice
recommendation, not a change here.

## 4. Controlled variables

Everything except the defender **condition** is fixed across a comparison:

- **Defenders under test**: the same dwellers throughout; record level, SPECIALs, equipped weapon and
  outfit once on the vault roster sheet.
- **Defender count per fight**: kept identical by (a) the SIM runs sharing one seed (the responder
  sample is identical across conditions, count included) and (b) manual rounds placing every test
  defender in the same room while keeping exactly **one occupied room** — the spawn endpoint picks a
  random occupied room (room is not selectable per call), so one occupied room pins it.
- **Difficulty**: confirmed from each spawn response (`difficulty` must read `4`).
- **Incident type / objective**: FIRE (contain) and RADSCORPION_ATTACK (combat + radiation) only.

## 5. SIM evidence (headless — already run, reproducible)

New simulator control gap found while building this protocol and **fixed test-first**: the Slice 1
roster always glued a team place to its matching outfit, so the four defender conditions could not be
isolated. `synthetic_defenders()` grew `outfit_count` (independent of `team_size`) and the CLI grew
`--team-size` and `--outfit-count`; tests `test_synthetic_outfit_count_decouples_gear_from_team_places`,
`test_four_defender_conditions_isolate_team_place_from_matching_gear`,
`test_benched_team_and_mismatched_team_earn_no_matching_bonus` and
`test_matchup_cli_accepts_team_size_and_outfit_count` were written first (they failed with
`TypeError: synthetic_defenders() got an unexpected keyword argument 'outfit_count'`).

Commands (from `backend/`, seed `20261012`, 200 runs each; roster 18 synthetic defenders —
`--starting-dwellers 20` → 18 adults — level 5, SPECIAL 4, unarmed damage 10):

```bash
uv run fo-cli simulate-incidents --matchup FIRE:4                            --runs 200 --seed 20261012   # 1 ordinary, no gear
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire --team-size 0 --outfit-count 3 --runs 200 --seed 20261012   # 2 ordinary + matching gear
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire --team-size 3 --outfit-count 0 --runs 200 --seed 20261012   # 3 active place, no gear
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire                         --runs 200 --seed 20261012   # 4 active place + matching gear
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire --team-size 0           --runs 200 --seed 20261012   # bench: team exists, nobody active
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4                              --runs 200 --seed 20261012   # plain
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4 --hazard-team fire --team-size 3 --outfit-count 3 --runs 200 --seed 20261012   # mismatched active fire team
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4 --hazard-team radiation --team-size 3 --outfit-count 0 --runs 200 --seed 20261012  # radiation team, no hazmat
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4 --hazard-team radiation               --runs 200 --seed 20261012  # radiation team + hazmat
```

| Condition | Matchup | Resolved | Ticks mean | Damage mean (p5/p95) | RAD mean | Deaths (runs) |
|---|---|---|---|---|---|---|
| 1 ordinary / no gear | FIRE:4 | 200/200 | 2.4 | 9.6 (4/20) | 0 | 0 (0) |
| 2 ordinary / matching gear | FIRE:4 | 200/200 | 2.4 | 8.5 (3/20) | 0 | 0 (0) |
| 3 active place / no gear | FIRE:4 | 200/200 | 2.2 | 8.2 (3/20) | 0 | 0 (0) |
| 4 active place + matching gear | FIRE:4 | 200/200 | 2.2 | 7.8 (3/20) | 0 | 0 (0) |
| bench (team set, 0 active) | FIRE:4 | 200/200 | 2.4 | 9.6 (4/20) | 0 | 0 (0) |
| 1 ordinary / no gear | RADSCORPION:4 | 162/200 | 14.2 | 81.8 (48/144) | 35.6 | 102 (70) |
| mismatched (active fire team) | RADSCORPION:4 | 162/200 | 14.2 | 81.8 (48/144) | 35.6 | 102 (70) |
| 3 radiation team / no hazmat | RADSCORPION:4 | 162/200 | 13.4 | 71.3 (30/144) | 28.3 | 76 (57) |
| 4 radiation team + hazmat | RADSCORPION:4 | 162/200 | 13.4 | 71.3 (30/144) | 27.6 | 76 (57) |

Reading (these are the SIM take-aways the manual rows must reproduce):

- FIRE is always contained; the signal is damage. Isolating the effect: the matching **gear alone**
  takes mean damage 9.6 → 8.5, the matching **place alone** 9.6 → 8.2, and the trained team
  (**place + gear**) 9.6 → 7.8 (~19% less) with the fastest ticks. The **bench** control is
  byte-identical to the ordinary row — an inactive roster earns nothing.
- RADSCORPION is the lethal one. A **mismatched** active team (fire places, fire suits) is
  byte-identical to the ordinary row (81.8 damage, 35.6 RAD, 102 deaths): the fire tag and fire suit
  contribute nothing to a radiation hazard. The **radiation** team cuts damage 81.8 → 71.3 and
  deaths 102 → 76 (~25%) whether or not hazmat is worn; hazmat only shaves burst radiation
  (per-run min 0 vs 5), because long fights still saturate near max health.

Existing/added API- and service-level evidence that qualification + notifications survive the real
round path (`uv run pytest`, all green):

- `test_contamination_team.py::test_qualification_loop_through_real_rounds_places_equips_and_notifies`
  — three distinct FIRE incidents through `process_incident` → active place + Firefighter suit
  equipped + exactly one `HAZARD_TEAM_JOINED` bell per responder (new in this slice).
- `test_contamination_team.py::test_participation_is_recorded_once_per_incident` — many rounds of one
  incident credit a defender once (no double-count).
- `test_contamination_team.py::test_join_emits_hazard_team_joined_notification` /
  `test_bench_join_emits_bench_notification` / `test_promotion_emits_notification_without_new_qualifier`
  — the bell entry carries the join meta for active, bench and promotion.

## 6. Manual browser protocol (MANUAL-NEEDED parts)

Pre-requisites on the isolated deploy (§2): a superuser account, a fresh vault with ≥ 6 occupied-room
dwellers to test, ≥ 3 spare **Firefighter suits** and ≥ 3 spare **Hazmat suits** in storage, and a
single occupied room that holds all test defenders (pins the random room pick, §4).

Notation: **SPAWN-TYPE** = Game Control panel → TEST INCIDENTS → *Fire* / *Radscorpion* (superuser
only), or `curl -X POST -H "Authorization: Bearer $TOKEN" /api/v1/game/vaults/{vault_id}/incidents/spawn?incident_type=fire|radscorpion_attack`.
**ROSTER** = `GET /api/v1/contamination-team/vault/{vault_id}/roster`. Every **SPAWN-TYPE** response
must report `"difficulty": 4`.

### Qualification loops (run first — they build conditions 3 and 4)

1. **Fire team (3 distinct incidents).** Make sure no dweller holds a fire place yet (`/roster` shows
   `active: []`). Spawn **FIRE**; let the fight contain (watch the room). Repeat for a **second** and
   **third** distinct FIRE incident. After the third containment:
   - **Membership (Criterion C):** `/roster` fire `active` now lists the qualifying dwellers.
   - **Gear (Criterion D):** each newly-user member wears the Firefighter suit (auto-equip closed at
     the round commit when a spare exists).
   - **Surfacing (Criterion D, MANUAL-NEEDED):** the bell gains one “Hazard team —
     *name* earned a place on the vault’s fire team” entry **and** a toast pops for it. Record which
     round produced it. `set_place` manual moves emit **no** toast — do not use them to check
     surfacing.
2. **Radiation team (3 distinct incidents).** Same loop with **RADSCORPION_ATTACK**. Spares of the
   Hazmat suit are consumed the same way.
3. **No-double-count (Criterion E).** Spawn a 4th FIRE incident with the (already active) member on
   duty, let it resolve, then `/roster` again: still **one** `active` fire row per member — no second
   place, no duplicate slot.

### Four defender conditions — FIRE then RADSCORPION

Target crew and gear per condition (same dwellers where possible; write their level/SPECIAL/weapon on
the observation sheet):

| Cond | Membership | Matching hazard gear | Manual setup |
|---|---|---|---|
| A ordinary / ordinary-gear | none | no | an ordinary dweller, ordinary outfit |
| B ordinary / matching-gear | none | yes | same dweller, equip one spare matching suit from storage (UI inventory) |
| C qualified-active / ordinary-gear | active (from loop 1/2) | no | active member, replace the matching suit with an ordinary outfit (UI; the suit returns to storage) |
| D qualified-active / matching-gear | active (from loop 1/2) | yes | active member still wearing the auto-equipped matching suit |

For each row: **SPAWN-TYPE** → watch the fight → record outcome; repeat per condition. Do the same
for RADSCORPION_ATTACK (note: the member in rows C/D must hold the *radiation* team place and the
Hazmat suit for the radiation rows).

### Negative controls

- **Bench:** `PUT /api/v1/contamination-team/vault/{vault}/fire/{dweller_id}` with `{"active": false}`
  on one active member, then spawn the matching hazard. The benched dweller is ordinary in every way
  that matters (no place, no forced auto-equip). Expect row values ≈ condition A, **not** C/D.
  Re-activate afterwards with `{"active": true}`. (No toast should fire on either move — only bio
  entries.)
- **Mismatched team:** with a fire member in a fire suit, spawn **RADSCORPION_ATTACK**. The fire tag
  must add nothing — expect row values ≈ condition B with the fire suit (which also has no radiation
  resist), far from the radiation-team rows.

## 7. Observation tables (fill in — one sheet per incident type)

Copy this block per run. Columns that the SIM already predicts for `seed 20261012`, level-5/SPECIAL-4
unarmed defenders are in square brackets and should be treated as the expectation, not the answer.

| Condition (fire team ⇄ radiation team) | Difficulty from spawn | Resolution (observed sec / ticks) | Outcome contained/victory/lost | HP lost (sum) | RAD gained (sum) | Deaths | Stimpaks used | Participation/qualification observed | active/bench status after | Does the UI make the team benefit legible? |
|---|---|---|---|---|---|---|---|---|---|---|
| A ordinary / ordinary-gear | 4 | … | … | … [→ SIM] | … [0 FIRE] | … | … | none | none | … |
| B ordinary / matching-gear | 4 | … | … | … | … | … | … | none | none | … |
| C qualified-active / ordinary-gear | 4 | … | … | … | … | … | … | 3rd incident → active | active | … |
| D qualified-active / matching-gear | 4 | … | … | … | … | … | … | 3rd incident → active | active | … |
| bench control | 4 | … | … | ≈ A | ≈ A | ≈ A | … | none | bench | … |
| mismatched control | 4 | … | … | ≈ B (fire suit, no rad resist) | ≈ B | ≈ B | … | none | active (wrong team) | … |

Repeat the sheet for RADSCORPION_ATTACK on the radiation team (rows C/D use the radiation place +
Hazmat suit).

## 8. Gaps, caveats, and what remains unverified

- **MANUAL-NEEDED, cannot be proven headless:** Game Control panel clicks, the bell-popup entry and
  the browser toast for `hazard_team_joined`, and in-battle wall-clock resolution feel. All of these
  are exercised only in §6.
- **SIM gaps documented, not built:** conditions 2 (gear without a place) and 3 (place without gear)
  needed an `outfit_count` knob — added (§5). What the CLI still cannot express and the protocol does
  not need: room-level selection per spawn (pinned by the single-occupied-room rule, §4) and
  per-spawn difficulty selection (pinned by the difficulty env tuples, §2).
- **Difficulty pin caveat (verified):** the tuples only reach the game when exported as OS env (or
  supplied by compose `env_file`); `backend/.env` alone is silently ignored for nested incident keys
  (§2).
- **Unverified in production:** `1.0/hr` spawn cadence with a 120 s cooldown is ~one auto-incident per
  hour, not a playtest pace; protocol cadence comes from manual spawn. A debug-only cooldown or spawn
  force is a future-slice recommendation (no change in this pass).
- Anything the simulator does not model (room topology, auto-dispatch, bench promotion, outfit auto-
  equip) is intentionally exercised by the manual loop instead — see Slice 1 §5 items 2 and 4.
