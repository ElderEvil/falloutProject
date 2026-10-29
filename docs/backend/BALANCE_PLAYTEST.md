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
34% of runs, and by difficulty 6 it is a coin flip. RAIDER sits between; its longest tails are
last-defender-standing fights (a lone responder absorbing the full split for 20+ sub-ticks), which
resolve as losses when the room empties.

## 3b. Incident difficulty pass (#1221)

Config: `combat.incident_containment_progress_divisor` 20 → **50**; new
`combat.incident_threat_health_multipliers` = **2.0** for raider, feral ghoul and mole rat
(absent for fire and Deathclaw). `incident_threat_damage_divisor` and `base_raider_power`
are unchanged, and the multiplier is applied only to progress denominators — damage to
dwellers still uses the raw threat power, so incoming DPS does not rise.

Commands (from `backend/`, seed `20261012`, 100 runs each):

```bash
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:4 --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:5 --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:7 --runs 100 --seed 20261012
uv run fo-cli simulate-incidents --matchup DEATHCLAW_ATTACK:10 --runs 100 --seed 20261012
```

Before (issue #1221 baseline, same roster and seed):

| Matchup | Resolved | Mean ticks (~s) | Mean damage | Deaths (runs) |
|---|---:|---:|---:|---:|
| FIRE:4 | 100/100 | 7.5 (~15s) | 12.5 | 0 (0%) |
| RAIDER:4 | 79/100 | 21 (~42s) | 48 | 21 (21%) |
| RAIDER:5 | 62/100 | 31 (~62s) | 78 | 38 (38%) |
| RAIDER:7 | 49/100 | 42 (~84s) | 144 | 51 (51%) |
| DEATHCLAW:10 | 0/100 | 61 (~122s) | 247 | 100 (100%) |

After:

| Matchup | Resolved | Mean ticks (~s) | Mean damage | Deaths (runs) |
|---|---:|---:|---:|---:|
| FIRE:4 | 83/100 | 21.0 (~42s) | 27.1 | 17 (17%) |
| RAIDER:4 | 79/100 | 28.8 (~58s) | 79.0 | 38 (38%) |
| RAIDER:5 | 62/100 | 38.9 (~78s) | 118.1 | 51 (51%) |
| RAIDER:7 | 38/100 | 54.5 (~109s) | 215.5 | 100 (100%) |
| DEATHCLAW:10 | 0/100 | 61.0 (~122s) | 247.1 | 100 (100%) |

Reading: fire is no longer a guaranteed win and now runs about 42 seconds. Mid-tier fights
are 13–30% longer; the top raid loses another 11 win-rate points. Deathclaw is unchanged.
Damage rises because fights last longer and more runs end in deaths, not because threat DPS
or `base_raider_power` changed.

**Responder-relative containment floor.** A global divisor cannot serve both a fresh and a
mature vault. `incident_containment_min_rounds` (10) floors effective containment threat at
``responder_power × tick_seconds × min_rounds / divisor``, capping containment at 10% per
round. It only binds for strong crews: vault 666's dispatched responders (~280–360 power
with the team bonus) would otherwise contain a difficulty-3 fire in ~3 rounds (~6s) at
divisor 50; the floor makes it 10–11 rounds (~20–22s). Weak crews keep the raw threat, so
the level-5 simulator rows above are unchanged. Combat objectives are not floored; raider
and feral-ghoul fights in that vault already run 13–33s.

Observed on vault 666 (68 dwellers, average level 15.8, max 49): fires resolved in
1.6–5.5s at the old divisor, raiders in 13–29s, feral ghouls in 27–33s. Those incident
ticks ran in the long-lived Dramatiq worker, which does not hot-reload; restart it after a
config change.

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
   survival; set `--heal-per-tick 0` to approximate production. The unconditional/mid-combat aspect
   is documented, not changed, because the config field's "safe and fed" semantics have no
   implementation to mirror — but since the 2026-10-12 correction the heal respects the radiation
   ceiling (`max(1, max_health - radiation)`), like the combat kernel, instead of healing through it.
2. **Responder selection.** Production fights with the healthy adults in the incident's room plus
   the auto-dispatched hazard team (`incident_round.process_incident` + `dispatch_to_incident`). The
   simulator samples `1..defenders_per_incident` random defenders from the whole roster; room
   topology and the dispatcher are not modeled.
3. **Spread / duration.** At the shipped `max_spread_count = 0` the kernel matches production: an
   unopposed incident fails on the first no-defender round (`no_defender_outcome` resolves the loss
   immediately once spreading is disabled), and a defended fight continues until it is won or all
   defenders die (`process_incident` has no duration timeout while defenders live). When
   `max_spread_count > 0` the simulator extends the effective duration instead of spawning in an
   adjacent room — the documented extended-escalation approximation. (Corrected 2026-10-12: the
   kernel previously burned sub-ticks to the full duration after a wipe, inflating failed-fight
   tails; the §3 tables were regenerated with the fail-fast kernel.)
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

---

# Balance Playtest — Slice 3a (combat tuning)

> Branch `feat/balance-pass`, appended after Slice 2. Slices 1–2 stay authoritative for the simulator
> fixes and baselines; this is the first slice that **changes shipped combat values**. Scope is
> incident combat only: no spawn-cadence change, no resource change (that is Slice 3b), no frontend,
> no schema/API, no new endpoint parameter. Every number below is a seeded distribution (200 runs per
> comparison) from `fo-cli simulate-incidents --matchup …`. The "prepared" rows are the response-team
> condition from Slice 2 (matching active team + matching catalog outfit).

## 1. What changed (two knobs, one formula reuse)

The Slice 1 baselines exposed two opposite failures: FIRE (a CONTAIN hazard) was won in 1–2 sub-ticks
(2–4 s) at every difficulty, so gear and team places had almost nothing to act on; and an ordinary
DEFEAT incident's per-tick damage was high enough that a lone or two-person response died before it
could finish a routine encounter.

Both levers live in `CombatConfig` and the simulator keeps calling the same pure helpers
(`incident_math`, `damage_reductions`) — no simulator-only formula:

| Knob (`CombatConfig`) | Slice-1 value | Slice-3a value | Effect |
|---|---|---|---|
| `incident_threat_damage_divisor` | 10 | **18** | Dwellers take `threat_power / divisor` damage per second. Raising it softens *every* incident's damage without touching the win race (progress vs. difficulty), so preparation survives longer. |
| `incident_containment_progress_divisor` | 5 | **20** | Containment fills at `power / threat * seconds / divisor`. Raising it makes a fire take more rounds, so the fight is long enough to see and react to. |

`incident_math.containment_damage` now returns `damage_to_dwellers(...) / 2` instead of a separate
`threat / 20`, so the single threat-damage knob governs both the combat and containment channels and
the old hard-coded constants are gone. **Unchanged on purpose:** `base_raider_power` (10), the DEFEAT
win race (`power/5` → `damage//5` per second) and its `difficulty * 2` kill threshold, the 30-sub-tick
escalation deadline, `TEAM_RESPONSE_BONUS` / `TEAM_HAZARD_RESIST` (0.20 / 0.20), the difficulty
ranges, the spawn weights, and the shared damage-reduction resolver.

## 2. Rationale (evidence → value)

- **`incident_threat_damage_divisor = 18`.** At 18 a lone level-5 / SPECIAL-4 / unarmed defender
  (70 HP) finishes a difficulty-3 hazard with 60 damage taken and no death; at the Slice-1 value of 10
  it took 72 damage and died at the deadline. 16 still killed the lone defender (73 damage); 18 is the
  first round value with margin. Above 18 the routine tail stops improving while the high-difficulty
  ladder softens faster (RAIDER:7 resolves 46% at 18 vs. 65% at 24), so 18 is the knee.
- **`incident_containment_progress_divisor = 20`.** This puts FIRE at ~4 (difficulty 2) to ~7.4
  (difficulty 4) mean sub-ticks for a trained crew — long enough for rounds to land — while FIRE stays
  the one incident that never kills. 15 already gave FIRE:4 ~5.6 ticks; 20 keeps the easiest fire at a
  full 4 ticks. Neither value targets a fixed % change in damage or duration; both are set from the
  outcome distributions in §3.

## 3. Before / after distributions

Commands (from `backend/`, `seed=20261012`, 200 runs each; roster 18 synthetic defenders — level 5,
SPECIAL 4, unarmed average damage 10 — responding 1..6 to mirror "whoever is in the room"). The
divisor keys are read from **OS environment**, so for the BEFORE rows they must be `export`ed, not put
in `backend/.env` (Slice 2 §2):

```bash
# BEFORE (pre-Slice-3a pacing) — run the whole list below with these set, then
# unset them and run the same list again for AFTER (the shipped defaults).
export COMBAT_INCIDENT_THREAT_DAMAGE_DIVISOR=10
export COMBAT_INCIDENT_CONTAINMENT_PROGRESS_DIVISOR=5
# ... run list ...
# AFTER — unset and re-run the same list:
unset COMBAT_INCIDENT_THREAT_DAMAGE_DIVISOR COMBAT_INCIDENT_CONTAINMENT_PROGRESS_DIVISOR
# ... run list again ...

uv run fo-cli simulate-incidents --matchup FIRE:2 --hazard-team fire --team-size 3 --outfit-count 3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup FIRE:3 --hazard-team fire --team-size 3 --outfit-count 3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup FIRE:4 --hazard-team fire --team-size 3 --outfit-count 3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup FIRE:4                                    --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADROACH_INFESTATION:1 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADROACH_INFESTATION:2 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADROACH_INFESTATION:3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup MOLE_RAT_ATTACK:2 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup MOLE_RAT_ATTACK:3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup MOLE_RAT_ATTACK:5 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:3 --hazard-team radiation --team-size 3 --outfit-count 3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4 --hazard-team radiation --team-size 3 --outfit-count 3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:6 --hazard-team radiation --team-size 3 --outfit-count 3 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:4 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RADSCORPION_ATTACK:6 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:4 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:5 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup RAIDER_ATTACK:7 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup FERAL_GHOUL_ATTACK:5 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup FERAL_GHOUL_ATTACK:6 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup FERAL_GHOUL_ATTACK:8 --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup DEATHCLAW_ATTACK:8  --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup DEATHCLAW_ATTACK:9  --runs 200 --seed 20261012
uv run fo-cli simulate-incidents --matchup DEATHCLAW_ATTACK:10 --runs 200 --seed 20261012
```

Each row shows **BEFORE → AFTER**: resolved runs, duration distribution (ticks p5/mean/p95), damage
distribution (p5/mean/p95) and deaths summed over all runs with `(runs that had ≥1 death)`.

Correction (2026-10-12): the tick columns were regenerated with the fail-fast kernel (see §5) —
previously failed fights burned idle sub-ticks to the 30-tick duration after a wipe, so every loss
tail sat at exactly 30. Resolution, damage, and deaths are unaffected (nothing accrues after death);
the new tails are real last-defender-standing durations.

### FIRE (CONTAIN) and routine infestations

| Matchup | Resolved | Ticks p5/mean/p95 | Damage p5/mean/p95 | Deaths (runs) | Resolved | Ticks p5/mean/p95 | Damage p5/mean/p95 | Deaths (runs) |
|---|---|---|---|---|---|---|---|---|
| FIRE:2 prepared | 200/200 | 1/1.4/3 | 1/2.5/6 | 0 (0) | 200/200 | 2/4.0/9 | 0/3.3/9 | 0 (0) |
| FIRE:3 prepared | 200/200 | 1/1.8/4 | 2/4.6/12 | 0 (0) | 200/200 | 2/5.6/13 | 0/4.8/13 | 0 (0) |
| FIRE:4 prepared | 200/200 | 1/2.2/5 | 3/7.8/20 | 0 (0) | 200/200 | 3/7.4/18 | 3/12.4/36 | 0 (0) |
| FIRE:4 plain | 200/200 | 1/2.4/5 | 4/9.6/20 | 0 (0) | 200/200 | 3/7.8/18 | 6/15.7/36 | 0 (0) |
| RADROACH:1 | 200/200 | 1/1.5/3 | 2/3.1/6 | 0 (0) | 200/200 | 1/1.5/3 | 1/1.5/3 | 0 (0) |
| RADROACH:2 | 200/200 | 2/4.1/9 | 8/16.5/36 | 0 (0) | 200/200 | 2/4.1/9 | 4/8.3/18 | 0 (0) |
| RADROACH:3 | 162/200 | 4/7.4/13 | 24/43.1/72 | 38 (38) | 200/200 | 4/8.7/20 | 12/26.1/60 | 0 (0) |
| MOLE_RAT:2 | 200/200 | 2/4.1/9 | 8/16.5/36 | 0 (0) | 200/200 | 2/4.1/9 | 4/8.3/18 | 0 (0) |
| MOLE_RAT:3 | 162/200 | 4/7.4/13 | 24/43.1/72 | 38 (38) | 200/200 | 4/8.7/20 | 12/26.1/60 | 0 (0) |
| MOLE_RAT:5 | 130/200 | 8/12.5/18 | 70/121.8/180 | 140 (108) | 130/200 | 9/16.3/30 | 45/79.5/145 | 102 (70) |

### RADSCORPION (irradiating)

| Matchup | Resolved | Ticks p5/mean/p95 | Damage p5/mean/p95 | Deaths (runs) | Resolved | Ticks p5/mean/p95 | Damage p5/mean/p95 | Deaths (runs) |
|---|---|---|---|---|---|---|---|---|
| RADSCORPION:3 prepared | 168/200 | 3/7.2/13 | 12/38.3/72 | 32 (32) | 200/200 | 3/8.3/20 | 6/22.2/60 | 0 (0) |
| RADSCORPION:4 prepared | 162/200 | 5/9.7/18 | 30/71.3/144 | 76 (57) | 162/200 | 5/11.5/19 | 15/40.9/72 | 38 (38) |
| RADSCORPION:6 prepared | 95/200 | 7/14.0/21 | 72/151.5/240 | 210 (108) | 130/200 | 11/18.1/31 | 48/95.9/156 | 102 (70) |
| RADSCORPION:4 plain | 162/200 | 6/10.4/18 | 48/81.8/144 | 102 (70) | 162/200 | 6/12.1/19 | 24/47.7/72 | 38 (38) |
| RADSCORPION:6 plain | 92/200 | 7/14.5/20 | 72/167.5/240 | 216 (108) | 130/200 | 13/18.9/26 | 72/111.2/156 | 102 (70) |

### Intrusions (no team trains them)

| Matchup | Resolved | Ticks p5/mean/p95 | Damage p5/mean/p95 | Deaths (runs) | Resolved | Ticks p5/mean/p95 | Damage p5/mean/p95 | Deaths (runs) |
|---|---|---|---|---|---|---|---|---|
| RAIDER:4 | 162/200 | 6/10.4/18 | 48/81.8/144 | 102 (70) | 162/200 | 6/12.1/19 | 24/47.7/72 | 38 (38) |
| RAIDER:5 | 130/200 | 8/12.5/18 | 70/121.8/180 | 140 (108) | 130/200 | 9/16.3/30 | 45/79.5/145 | 102 (70) |
| RAIDER:7 | 65/200 | 6/15.5/22 | 70/207.6/308 | 324 (135) | 92/200 | 11/21.9/32 | 70/149.7/217 | 216 (108) |
| FERAL_GHOUL:5 | 130/200 | 8/12.5/18 | 70/121.8/180 | 140 (108) | 130/200 | 9/16.3/30 | 45/79.5/145 | 102 (70) |
| FERAL_GHOUL:6 | 92/200 | 7/14.5/20 | 72/167.5/240 | 216 (108) | 130/200 | 13/18.9/26 | 72/111.2/156 | 102 (70) |
| FERAL_GHOUL:8 | 28/200 | 6/15.6/23 | 80/236.3/368 | 509 (172) | 92/200 | 10/23.4/35 | 72/182.8/280 | 324 (135) |
| DEATHCLAW:8 | 28/200 | 6/15.6/23 | 80/236.3/368 | 509 (172) | 92/200 | 10/23.4/35 | 72/182.8/280 | 324 (135) |
| DEATHCLAW:9 | 0/200 | 5/14.5/25 | 72/243.7/432 | 677 (200) | 65/200 | 8/23.0/35 | 70/223.4/350 | 509 (172) |
| DEATHCLAW:10 | 0/200 | 5/13.3/23 | 80/245.4/440 | 677 (200) | 0/200 | 8/23.3/40 | 77/245.1/429 | 677 (200) |

Reading:

- **FIRE is no longer a 2-tick formality.** Duration goes 1.4–2.4 → 4.0–7.8 mean ticks (roughly 8–16 s
  of wall clock at `incident_tick_seconds=2`) at every difficulty, and damage becomes a visible
  gradient (FIRE:4 prepared 7.8 → 12.4 mean) instead of a rounding error. Prepared vs. plain still
  separates (FIRE:4, 12.4 vs. 15.7 damage; the matching team place + suit are worth ~21%).
- **Routine is safe.** Every difficulty-3-or-lower matchup now resolves 100% with **zero** deaths
  (RADROACH:3 and MOLE_RAT:3 flip 162/200 with 38 deaths → 200/200 with 0; RADSCORPION:3 prepared
  168/200 with 32 deaths → 200/200 with 0). The routine death tail is gone.
- **Hard stays hard.** RAIDER:7 still resolves 46% with 216 deaths; FERAL_GHOUL:8 / DEATHCLAW:8 46%
  with 324 deaths; DEATHCLAW:9 32% with 509; DEATHCLAW:10 0% with 677. The reduced damage trims the
  death toll, but the 30-sub-tick deadline keeps the top of the ladder a loss for anything but a
  full-size squad.

## 4. Provisional goals — verdict

| # | Goal | Evidence | Met |
|---|---|---|---|
| 1 | Routine incidents reliably handled by prepared crews | FIRE 2/3/4 200/200; RADROACH 1–3 and MOLE_RAT 2–3 200/200; RADSCORPION:3 prepared 200/200 — all with 0 deaths | yes |
| 2 | Gear + matching active teams visibly improve outcomes | FIRE:4 prepared 12.4 vs. plain 15.7 damage and 7.4 vs. 7.8 ticks; RADSCORPION:4 prepared 40.9 vs. 47.7 damage, 11.5 vs. 12.1 ticks; RADSCORPION:6 95.9 vs. 111.2 — already modelled, not retuned | yes |
| 3 | Hard encounters remain costly | RAIDER:7 46% / 216 deaths; DEATHCLAW:8 46% / 324; DEATHCLAW:9 32% / 509; DEATHCLAW:10 0% / 677 | yes |
| 4 | Ordinary prepared defenders not routinely killed | 0 deaths across every difficulty-3-and-below matchup; RADSCORPION:4 deaths 76 → 38, RAIDER:4 102 → 38 (the residual 19% is the lone-responder tail — see §5) | yes (with a lone-responder tail) |
| 5 | Fights last long enough to notice / respond | FIRE duration 1.4–2.4 → 4.0–7.8 mean ticks; every DEFEAT fight keeps its multi-round duration (5–40 ticks across the ladder) | yes |

## 5. Regression tests (failing-test-first)

Written before the value change and shown failing against the Slice-1 divisors
(`COMBAT_…_DIVISOR=10` / `=5`), then green on the shipped defaults
(`uv run pytest app/tests/test_services/test_incident_sim.py`):

- `test_lone_routine_defender_survives_a_difficulty_three_hazard` — under 10/5 the lone defender
  resolved as a loss with 1 death; now resolves with 0.
- `test_fire_containment_takes_several_rounds_for_a_prepared_crew` — under 10/5 the trained crew
  contained a difficulty-4 fire in 1 tick; now it needs ≥ 4.
- `test_top_difficulty_intruder_still_overwhelms_a_lone_defender` — guard that the top of the ladder
  is still a loss (unchanged intent, pins "hard stays costly").
- `test_no_defenders_fails_on_first_round_without_spread` — unopposed incidents fail on the first
  no-defender round (production parity), not after burning the duration; the spread-enabled variant
  keeps the extended window.
- `test_regen_respects_radiation_ceiling` — simulator healing clamps to the radiation ceiling instead
  of restoring through it.
- `test_incident_math_reads_configured_pacing_divisors` — both pacing divisors are the single tuning
  surface; the pure helpers read `game_config` (so production and the simulator cannot drift).
- `test_containment_damage_is_half_of_combat_damage` — pins the formula reuse that removed the
  hard-coded containment divisor.
- `test_live_round_engine_matches_offline_kernel_fire_pacing` — a live `process_incident` loop and the
  offline `resolve_incident` kernel land on the same round count for a difficulty-2 fire from one
  vault snapshot (live/offline consistency on the retuned path).

Existing golden/parity tests were re-pinned to the new divisors (`test_golden_fire_ticks_to_win`,
`test_team_response_bonus_shortens_containment`, `test_team_hazard_resist_reduces_damage`,
`test_radscorpion_accumulates_radiation`, `test_radiation_accumulates_per_tick_until_victory`,
`test_radiation_ceiling_clamps_health`). The kernel-vs-`incident_math` parity tests needed no change —
they compare the kernel against the same helpers.

## 6. Caveats, out of scope, and future

- **The residual difficulty-4 deaths are lone responders.** The matchup sampler draws 1..6 responders
  to mirror "whoever is in the affected room"; a lone defender cannot beat a difficulty-4 incident
  because suppression progress accumulates slower than incoming damage kills it — defended fights
  have no duration timeout, they end in victory or a wipe. That is the intended "bring a crew"
  boundary — a fixed 3-defender check resolves with 0 deaths. The 19% death-run figure at
  difficulty 4 is essentially the 1-responder fraction.
- **The top end softened.** Reducing damage lets 5–6 defender responses survive what used to kill them,
  so DEATHCLAW:8 rose 14% → 46% and DEATHCLAW:9 0% → 32% resolve. DEATHCLAW remains the deadliest
  family (324–677 deaths; difficulty 10 still 0%), so this is within "still costly", but it is a real
  shift and is recorded rather than mitigated.
- **Passive regen is still simulator-only** (Slice 1 §5.1). The multi-hour `run()` path heals every
  60 s; the `--matchup` path used here does **not**, so these tables are already regen-free and need
  no `--heal-per-tick 0` adjustment.
- **Spawn pacing is unchanged** (`spawn_chance_per_hour=0.05`, `spawn_cooldown_seconds=120`). The
  Slice 2 recommendation for a debug-only incident cadence still stands; it is not a balance value and
  is not changed here.
- **Out of scope by design:** resource production (Slice 3b), room caps, presets #839, Survival #838,
  AI dispatch, spread mechanics, SSE, and the manual-only surfaces in Slice 2 §6.

---

# Balance Playtest — Slice 3b (resource production tuning)

> Branch `feat/balance-pass`, appended after Slice 3a. Slices 1–3a stay authoritative. This is the
> first slice that **changes shipped resource production**. Scope is exactly one knob —
> `ResourceConfig.base_production_rate` (env `RESOURCE_BASE_PRODUCTION_RATE`): no consumption change,
> no medical change, no tier/capacity/formula change, no frontend, no schema/API. The goal
> (docs/features/RESOURCE_ECONOMY_BALANCE.md): power/food/water must be a **visible staffing decision**
> on the 60-second tick — a fully staffed starter is safe, and moving or losing a production worker
> has an immediate, recoverable cost.

## 1. What changed and why the four candidates are insufficient

The four 25/50/75%-cut candidates (0.075 / 0.050 / 0.025) plus the unchanged 0.100 were measured
against the actual seeded vault (rooms/catalog values, §2). **None of them changes the qualitative
economy**: at every candidate a single SPECIAL-1 worker out-produces the vault's consumption by an
order of magnitude, so staffing stays a non-decision and storage caps in seconds. The only value in
the repo's own baseline contract (`docs/features/RESOURCE_ECONOMY_BALANCE.md`, "First Adjustment")
that puts production and consumption on the same scale is **0.0003**. That offending-outside-the-band
value is the applied change:

| Knob (`ResourceConfig`) | Slice-1/3a value | Slice-3b value | Effect |
|---|---|---|---|
| `base_production_rate` | 0.1 | **0.0003** | Per-SPECIAL-per-second yield drops ~333× so that a room's output meets, not buries, its consumption. |

History (for the record): 0.0003 was the rate shipped by PR #431's resource-economy work, then bumped
through 0.01 to 0.1 the same day (v2.39.x "livelier resource economy"). This slice reverses that
decision deliberately: the measured outcome at 0.1–0.025 is that staffing never matters (§3), which is
the exact problem the balance pass exists to fix.

## 2. Measurement scenarios (actual room/catalog values)

All numbers use the live `ResourceManager` formulas via `fo-cli simulate-resources` (per-tick
production/consumption with clamping and the power-outage gate). Scenarios:

- **starter** — the seeded standard vault: three tier-1 size-3 production rooms (Power Generator /
  Diner / Water Treatment; catalog output `(2*S*(L+4))-2 = 28`, tier multiplier `1.0`), nine
  dwellers, **two matching SPECIAL-5 workers per room** (the seeded `special_boost` →
  `boosted_stat_value = 5`).
- **growing** — ~20 dwellers with ordinary staffing: two workers per room at the relevant
  SPECIAL **3** (top of the common roll band 1–3), same tier-1 size-3 rooms.
- **developed** — upgraded tier-3 size-9 rooms (`output = 124`, tier multiplier 2.0), **three
  workers per room at SPECIAL 8** (trained/legendary tier 6–10), 30 dwellers.

Consumption uses the simulator's three production rooms (matching the baseline contract); the seeded
standard vault's full room set draws more power (see §7). Reduced staffing rows drop a room's workers
to 1, then 0, to show the staffing decision at each rate.

## 3. Candidate measurements (0.100 / 0.075 / 0.050 / 0.025, then the chosen 0.0003)

> **Superseded 2026-10-12 by §10** — the 0.0003 default this table supports failed live play because it
> models consumption from the three production rooms only. Kept for the record; §10 is the authority.

Commands (from `backend/`; `--base-production-rate` overrides the shipped default for every row, so
the same command reproduces the table again after this slice):

```bash
for R in 0.100 0.075 0.050 0.025; do
  uv run fo-cli simulate-resources --population 9  --workers-per-room 2 --worker-special 5 --room-tier 1 --room-size 3 --base-production-rate $R
  uv run fo-cli simulate-resources --population 20 --workers-per-room 2 --worker-special 3 --room-tier 1 --room-size 3 --base-production-rate $R
  uv run fo-cli simulate-resources --population 30 --workers-per-room 3 --worker-special 8 --room-tier 3 --room-size 9 --base-production-rate $R
done
uv run fo-cli simulate-resources --population 9  --workers-per-room 2 --worker-special 5 --room-tier 1 --room-size 3               # chosen default
uv run fo-cli simulate-resources --population 20 --workers-per-room 2 --worker-special 3 --room-tier 1 --room-size 3
uv run fo-cli simulate-resources --population 30 --workers-per-room 3 --worker-special 8 --room-tier 3 --room-size 9
```

### Starter (9 dwellers, 2×SPECIAL-5, tier-1 size-3; storage caps 100, start 50)

| Rate | Uncap. prod/min (P/F/W) | Consumption/min (P/F/W) | Net income/min (P/F/W) | Time to cap 50→100 |
|---|---|---|---|---|
| 0.100 | 1680 / 1680 / 1680 | 4.5 / 3.24 / 3.24 | +1675.5 / +1676.8 / +1676.8 | <0.1 min |
| 0.075 | 1260 / 1260 / 1260 | 4.5 / 3.24 / 3.24 | +1255.5 / +1256.8 / +1256.8 | <0.1 min |
| 0.050 | 840 / 840 / 840 | 4.5 / 3.24 / 3.24 | +835.5 / +836.8 / +836.8 | <0.1 min |
| 0.025 | 420 / 420 / 420 | 4.5 / 3.24 / 3.24 | +415.5 / +416.8 / +416.8 | 0.1 min |
| **0.0003** | 5.0 / 5.0 / 5.0 | 4.5 / 3.24 / 3.24 | **+0.5 / +1.8 / +1.8** | **92.6 / 27.8 / 27.8 min** |

### Growing (20 dwellers, 2×SPECIAL-3, tier-1 size-3)

| Rate | Uncap. prod/min (P/F/W) | Consumption/min (P/F/W) | Net income/min (P/F/W) | Time to cap 50→100 |
|---|---|---|---|---|
| 0.100 | 1008 / 1008 / 1008 | 4.5 / 7.2 / 7.2 | +1003.5 / +1000.8 / +1000.8 | <0.1 min |
| 0.075 | 756 / 756 / 756 | 4.5 / 7.2 / 7.2 | +751.5 / +748.8 / +748.8 | <0.1 min |
| 0.050 | 504 / 504 / 504 | 4.5 / 7.2 / 7.2 | +499.5 / +496.8 / +496.8 | 0.1 min |
| 0.025 | 252 / 252 / 252 | 4.5 / 7.2 / 7.2 | +247.5 / +244.8 / +244.8 | 0.2 min |
| **0.0003** | 3.0 / 3.0 / 3.0 | 4.5 / 7.2 / 7.2 | **−1.5 / −4.2 / −4.2** | **depletes — needs more/stronger staffing** |

### Developed (30 dwellers, 3×SPECIAL-8, tier-3 size-9)

| Rate | Uncap. prod/min (P/F/W) | Consumption/min (P/F/W) | Net income/min (P/F/W) | Time to cap 50→100 |
|---|---|---|---|---|
| 0.100 | 35712 / 35712 / 35712 | 40.5 / 10.8 / 10.8 | +35671.5 / +35701.2 / +35701.2 | <0.1 min |
| 0.075 | 26784 / 26784 / 26784 | 40.5 / 10.8 / 10.8 | +26743.5 / +26773.2 / +26773.2 | <0.1 min |
| 0.050 | 17856 / 17856 / 17856 | 40.5 / 10.8 / 10.8 | +17815.5 / +17845.2 / +17845.2 | <0.1 min |
| 0.025 | 8928 / 8928 / 8928 | 40.5 / 10.8 / 10.8 | +8887.5 / +8917.2 / +8917.2 | ~0.01 min |
| **0.0003** | 107.1 / 107.1 / 107.1 | 40.5 / 10.8 / 10.8 | **+66.6 / +96.3 / +96.3** | <1 min |

Reading: at the four candidate rates every scenario is net-positive by 1–4 orders of magnitude and
caps storage in well under a tick; the numbers only scale with the rate. Upgrades and stronger workers
"matter" only multiplicatively — they are never *needed*. At 0.0003 the starter is borderline-positive
(exactly the contract), the ordinary next-step vault (growing, same tier) is **net-negative** so the
player must staff smarter or upgrade, and a developed vault is decisively positive again.

## 4. Reduced staffing — does assigning workers matter?

| Scenario | Rate | 1 worker/room net/min (P/F/W) | Verdict |
|---|---|---|---|
| starter | 0.025 | +205.5 / +206.8 / +206.8 | a single weak worker still buries consumption — no cost to shedding workers |
| starter | **0.0003** | **−2.0 / −0.7 / −0.7** | removing a worker is an immediate, recoverable cost |
| growing | **0.0003** | −3.0 / −5.7 / −5.7 | under-staffed growth runs down |
| developed | **0.0003** | −4.8 / +24.9 / +24.9 | a *power* room under-staffed at tier 3 costs power (correct direction) |

Unstaffed (0 workers) is rate-independent — production is zero so every rate depletes identically:

| Scenario | Depletion net/min (P/F/W) | Time from 50 (P/F/W) |
|---|---|---|
| starter | −4.5 / −3.24 / −3.24 | 11.1 / 15.4 / 15.4 min |
| growing | −4.5 / −7.2 / −7.2 | 11.1 / 6.9 / 6.9 min |
| developed | −40.5 / −10.8 / −10.8 | 1.2 / 4.6 / 4.6 min |

## 5. Offline catch-up comparison (single 3600 s window vs 60×60 s per-tick)

Production is always evaluated once per `process_vault_tick` with a `seconds_passed` window that, after
a return, is capped at `max_offline_catchup = 3600`. The simulator's `simulate` path steps 60 ticks of
60 s instead. The two differ in exactly two ways, both documented (same formulas):

1. **Integer rounding across the window** — visible only at the slow rate. At 0.0003 the starter's
   power surplus is `+0.54`/tick, which rounds to `+1` *per persisted tick*, so the stepped path
   accumulates to the cap while a single 3600 s window writes the raw `+32.4`. Measured: start 50/50/50
   → single-step `82/100/100` vs per-tick `100/100/100` (power divergence −18). At 0.1–0.025 both cap
   at 100 and the raw surplus dwarfs the window, so the divergence is invisible.
2. **The power-outage gate is evaluated once, at the window's start power** (`_calculate_production`),
   not per tick. With `power = 0` at the start, a single 3600 s window blocks Diner/Water for the whole
   hour and food/water floor at 0, while stepped ticks produce power on tick 1 and unblock them from
   tick 2. Measured at 0.0003: start 0/50/50 → single-step `32/0/0` vs per-tick `60/100/100`
   (divergence −28 power, −100 food, −100 water). Identical shape at 0.1 and 0.025 — rate-independent.

The live game always single-steps, so both divergences are real player-visible behavior: **offline
catch-up under-persists power** at the tuned rate and **can gate food/water to zero on a power-out
return** until a live tick recovers them. Neither is new, and neither is changed by this slice.

## 6. Choice + rationale

**Apply `0.0003`** — outside the 25/50/75% band by design, and the *justified neighbor* this slice
may select: it is the exact "First Adjustment" of `docs/features/RESOURCE_ECONOMY_BALANCE.md`, whose
baseline contract this slice's success criteria restate, and it is the only value measured here where
production and consumption share an order of magnitude. Verification against the contract (per tick,
after persistence rounding), reproduced by `test_starter_vault_meets_resource_economy_baseline_contract`:

| Staffing | Contract | Measured @ 0.0003 |
|---|---|---|
| Two SPECIAL-5 workers/room | power +1, food/water +2 | +1 (+0.54), +2 (+1.80), +2 (+1.80) |
| One worker/room | power −2, food/water −1 | −2 (−1.98), −1 (−0.72), −1 (−0.72) |
| No workers | power ≈ −4, food/water ≈ −3 | −4 (−4.50), −3 (−3.24), −3 (−3.24) |

Rationale chain: the four candidate rates keep a single SPECIAL-1 worker ≥12× (0.025) to ≥46× (0.100)
above a dweller's consumption, so they cannot produce a staffing decision; 0.0003 makes the *first*
worker in a small room the margin between surplus and deficit (specialty rooms at 0.0003 are still
strongly positive, keeping upgrades and training valuable, §3/§4). If live play finds 0.0003 too slow
for the mid-game, the fix belongs to the consumption/capacity side (see §7), not a return to 0.1.

## 7. Goal verdicts

| # | Goal (docs/features/RESOURCE_ECONOMY_BALANCE.md) | Evidence @ 0.0003 | Met |
|---|---|---|---|
| 1 | Healthy starter staffing is safe when fully staffed | starter 2×SPECIAL-5 is +1/+2/+2 per tick and reaches mid-storage slower (27.8–92.6 min) instead of instantly | yes |
| 2 | Removing/losing production workers has an immediate, recoverable cost | 1 worker → −2/−1/−1 per tick; 0 workers → depletion in 11–15 min | yes |
| 3 | Continued growth needs staffing or upgrades to hold | growing vault (SPECIAL-3, tier-1) is net-negative (−1.5/−4.2/−4.2 per min) | yes |
| 4 | Stronger staffing / upgrades still matter | developed tier-3 (3×SPECIAL-8) is +66.6/+96.3/+96.3 per min; ~21× the starter's net | yes |
| — | The four candidates (0.025–0.100) meet all of the above | no — every staffing level ≥1 worker is trivially positive at any of them | no |

The underlying imbalance the four candidates expose: production scales as `output × ΣSPECIAL × rate ×
seconds` with output 28–124 and SPECIAL 5–10, while consumption is a flat `0.36/min` per dweller (and
`0.5/60` per room-tier-size of power). A per-worker yield of `output × SPECIAL × rate × 60` at 0.1 is
467–2067× a dweller's draw, so no cut in that band changes the decision structure — only a rate that
drops the sustainable band *into* the staffing range can. Applying 0.0003 (the spec's documented
value) is the in-scope lever for that; anything further (e.g. consenting consumption with output) is a
different system and out of scope here.

## 8. Regression tests (failing-test-first)

Written before the value change and shown failing against `base_production_rate = 0.1`, then green on
the shipped default (`uv run pytest app/tests/test_services/test_resource_manager.py
app/tests/test_services/test_race_mechanics.py app/tests/test_scripts/test_simulate_resource_economy.py`):

- `test_base_production_rate_default_matches_resource_economy_baseline` — pins the default to 0.0003
  (failed at 0.1).
- `test_starter_vault_meets_resource_economy_baseline_contract` — the two-worker and one-worker rows
  of the §6 contract land on the documented per-tick integers (failed at 0.1: +1675/+836 instead of
  +1/−2).
- `test_offline_single_step_window_diverges_from_per_tick_rounding` — pins the §5 rounding divergence
  so a future offline-pacing change is deliberate.
- `test_live_tick_matches_offline_kernel_production_at_default_rate` — the live
  `process_vault_resources` DB path and the offline kernel apply the same configured rate (live/offline
  consistency on the tuned path).
- `test_race_mechanics` production assertions were re-pinned from a hard-coded `0.1` to
  `game_config.resource.base_production_rate` (the flag-off reverts-to-raw behavior is unchanged).

## 9. Caveats, out of scope, and future pacing

- **Consumption and medical production are unchanged**, per the spec guardrail (one system per pass);
  the only schema/API-visible change is the shipped default of one env-scoped config field, so no
  migration, endpoint or frontend work is needed.
- **The simulator's power consumption counts only the three production rooms.** The seeded standard
  vault's full room set draws ~14 power/min (door, elevators, living/storage/radio) vs the 4.5/min the
  contract and this table model — live power pressure is *stronger* than shown, so power is the
  resource most likely to need the §5.1 offline attention.
- **Offline single-step under-persists at slow rates** (§5): the live path always evaluates one
  window, so the rounding and gate divergences are player-real. Fixing offline stepping is a
  dedicated pacing change, recorded here, not bundled.
- **Child/junior workers** (Slice 1 §5.6) and full-vault room power draw are still not modeled by the
  simulator; the contract deliberately targets the three-room starter.
- **Recommendation (not implemented):** stay within the spec's `0.00025–0.00035` tuning band after one
  live starter playtest (§2 of the spec's plan); if 0.0003 proves too slow for mid-game vaults, rework
  the consumption/capacity side (raise per-dweller draw and/or shrink the output base) rather than
  returning toward 0.1, which the measurements show erases the staffing decision entirely.
- **Out of scope by design:** combat (Slice 3a owns `incident_threat_damage_divisor = 18` /
  `containment_progress_divisor = 20` — untouched here), spawn cadence, room caps, tier multipliers,
  medical production, frontend.

---

## 10. Correction (2026-10-12): shipped default moves to 0.0012, boosted seeds gain a size-6 generator

> **Supersession notice:** the §3 tables, the §6 verification contract, and the §9 recommendation
> were measured against a simulator that counts only the three production rooms' consumption. Live
> play (vault `31c2dbd3`) proved that model wrong and 0.0003 dark. Those sections stay for the
> record; this section is the current source of truth.

### Why 0.0003 failed live

The simulator and the baseline contract modeled consumption from three tier-1 size-3 production
rooms only: `4.5` power/min. A real seeded standard vault's room set is much larger — six-unit vault
door, four elevators, living room, storage room, radio studio — for a **14 power/min all-room draw**,
and a boosted vault's full set draws **~51.5/min** (103 room-units at `0.5/min` each). At 0.0003 a
fully staffed standard starter produced `5.04` power/min against that real draw, ≈ **−9/min**, so the
vault went dark inside a few ticks; live vault `31c2dbd3` measured ~45/min all-room consumption
against ~5/min production. Food/water scale with dweller count the same way: the simulator's
`3.24`/min became `3.6`/min (standard, 10 dwellers) to `11.9`/min (boosted start) at live populations.

### The change

- `ResourceConfig.base_production_rate` default `0.0003 → 0.0012` (4×). Like 0.0003 this leaves the
  spec's `0.00025–0.00035` band deliberately; the band was calibrated to the same three-room model
  that failed, so it is not the constraint the live economy needs.
- Boosted seeds build the generator at its final **size-6** footprint at unit `(0, 1)` (output `58`,
  capacity `300`), which reads as a single generator row. It takes a **five-adult STR crew** (double
  `production_crew` minus the reserved apprentice slot, which still sits on the first production
  room), so the total non-legendary headcount is unchanged (33, plus 3 legendaries = **36**).
  Standard seeds are unchanged. *(Supersedes the earlier `(0, 2)` placement, which read as a stray
  generator beside the Diner.)*
- Every boosted production worker (power/diner/water/medbay/science crews) is equipped the **Common
  +3 outfit** matching their room stat — Military fatigues (STR), Handyman jumpsuit (AGI), Lab coat
  (INT), Armored vault suit (PER) — built through `item_factory.build_outfit` and equipped via the
  outfit CRUD. Base boosted stat 5 + outfit 3 = **effective 8** flows through the ordinary
  `effective_stat` production path; there is no parallel formula.
- The boosted legendary roster stays at **3** (`BOOSTED_LEGENDARY_DWELLER_COUNT`) so the seeded
  population (33 non-legendary + 3 legendary = **36**) fits the boost's living-space capacity of 36;
  the size-6 generator's crew fits the same slots, so the headcount is unchanged. Legendaries
  produce no resources, so this leaves every number above untouched.
- **Nothing else changed:** no consumption, capacity, output-formula, tier-multiplier, combat, spawn,
  frontend, schema/API, or migration (a config default plus seed-time rooms/crew need none).
- **Existing already-seeded vaults are out of scope** — this is seed-time only and does not backfill
  live vaults.

### New key numbers (0.0012, per minute, live all-room draw)

`room output 28 × (2 workers × SP5 = 10pt) × 0.0012 × 60 = 20.16/min` per fully staffed starter room,
and the size-6 generator `58 × (5 × SP8 = 40pt) × 0.0012 × 60 = 167.0/min` (adult crew only).

| Vault | Power staffing | Production/min | All-room draw/min | Net/min |
|---|---|---|---|---|
| Standard (1 generator) | 2 × SP5 | ~20.2 | 14.0 | **+6.2** (safe) |
| Standard (1 generator) | 1 × SP5 | ~10.1 | 14.0 | **−3.9** (shed-worker deficit) |
| Boosted (size-6 generator, outfitted 5×SP8 + seeded teen) | 5 × SP8 + junior | ~177.5 | ~51.5 | **+126.0** (safe) |
| Boosted, two generator workers left | 2 × SP8 + junior | ~77.3 | ~51.5 | **+25.8** (safe) |
| Boosted, one generator worker left | 1 × SP8 + junior | ~43.9 | ~51.5 | **−7.7** (deep-shed deficit) |
| Boosted diner (outfitted 2×SP8 + seeded teen) | 2 × SP8 + junior | ~37.3 food | ~11.9 | **+25.4** (positive) |

> **Superseded rows:** the earlier boosted entries (generator pair ~`55.4`, one worker shed ~`45.4`,
> diner ~`25.2`) measured the `(0, 2)` layout with un-outfitted SP5 crews; the size-6,
> outfitted rows above replace them. The standard rows and the `−51.5`/`−11.9` draws are unchanged.

Regressions: `test_seeded_standard_vault_live_power_survives_when_staffed_and_deficits_on_one_worker`
and `test_seeded_boosted_vault_size_six_generator_keeps_live_power_positive_with_margin` (with
`test_seeded_boosted_diner_outfitted_crew_keeps_live_food_positive` for the diner) compute these nets
from the real seeded room sets, so a future change to either the rate or the seed that breaks the
success criterion fails the suite. The three-room simulator contract
(`test_starter_vault_meets_resource_economy_baseline_contract`) is re-pinned to the shipped rate's
simulator integers but is no longer the tripwire source.

Boosted margin note: the size-6 generator's outfitted crew leaves a large positive margin, so the seed
now shows worker loss **at depth** — a fresh vault stays safe while shedding one or two generator
workers, and only the deep one-adult crew flips the big boosted draw negative. This model excludes
race/faction identity modifiers that real random-race dwellers carry, so live totals can differ
slightly in either direction; the margin is wide enough that the success criterion holds regardless.
