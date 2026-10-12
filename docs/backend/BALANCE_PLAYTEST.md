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
