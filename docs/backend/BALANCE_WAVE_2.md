# Wave 2 balance review — resources, objectives, and economy

Research date: **2026-10-13**. This report proposes changes; it does not change live settings, rewards, or database rows.

## Assessment

Resources are too brittle around a power deficit, while objectives pay too much for routine actions. These problems
coexist: spare caps do not repair a staffing deficit, and large resource rewards can temporarily hide one. The next
wave should create a longer recovery window and reduce routine reward income, while preserving useful staffing,
upgrades, exploration, and milestone recognition.

The database shows a split economy rather than universal scarcity: **10 of 20 active, unpaused vaults have zero
power, food, and water; 9 of those 20 are full in all three resources.** Four of the 20 have activity recorded within
24 hours. Older/test/abandoned vaults dominate the snapshot, so these counts are evidence of persisted conditions,
not a measured failure rate among current players.

Recommended order:

1. Fix objective qualification and persisted-template identity before selecting final reward values.
2. Trial a modest consumption reduction using complete room sets, alongside a deliberate recovery policy for
   legacy vaults. Preserve production at `0.0012` initially.
3. Reduce repeatable objective income and replace reassignment farming with useful goals.
4. Resolve unattended resource draining and power-out catch-up semantics as a distinct pacing decision.
5. Measure caps sources/sinks over representative sessions before changing room or crafting prices broadly.

## Evidence and scope

Production backend and worker image: `elerevil/fo-shelter-be:v2.200.0` at inspection. Local source:
`3421151f` (`chore: add backend test review plan (#980)`). Production resource/crafting settings were read from the
running backend, not inferred from local defaults. All 38 non-deleted vaults were queried using a PostgreSQL
**REPEATABLE READ, READ ONLY** transaction with a statement timeout; no player action or tick was invoked.
Resource rates were calculated with the deployed `ResourceManager`'s pure calculation methods and its actual CRUD
inputs. Vault labels V1–V38 are anonymous snapshot labels ordered by creation time, not durable identities.

Artifacts:

- [Production settings, rates, crews, objectives, and states](balance_wave2_data/production_snapshot.json)
- [Additional DB population, morale, medication, quest, and crafting aggregates](balance_wave2_data/production_progression.json)
- [Per-vault resource and caps comparison](balance_wave2_data/production_vaults.csv)
- [Complete persisted objective catalog](balance_wave2_data/objective_catalog.csv)
- [24 resource candidate scenarios](balance_wave2_data/resource_candidates.csv)
- [91 local objective entries with illustrative proposals](balance_wave2_data/objective_proposals.csv)
- [Exportable balance figure](balance_wave2_data/balance_overview.png)

The candidate scenarios reuse `_make_room`, `_make_workers`, and `ResourceManager` from the existing resource
simulator. Additional size-1 loads represent the rest of the vault's weighted room units. These are deterministic
static models: no births, deaths, assignment changes, new buildings, caps spending, or objective rewards during
simulation. Identity modifiers and juniors are included in production snapshots; synthetic candidate rows explicitly
use adult workers without equipment/identity bonuses beyond the stated effective stat. Production and local synthetic
results should not be treated as identical cohorts.

This extends [BALANCE_PLAYTEST.md](BALANCE_PLAYTEST.md), particularly its correction in §10. The historical
three-room `0.0003` contract and August Monte Carlo findings are not current balance evidence. The CLI simulator
still models only its three production rooms unless the analysis supplies the rest of the load.

## 1. What production actually contains

| Snapshot measure | Value |
| --- | ---: |
| Non-deleted vaults | 38 |
| Populated vaults | 37 |
| Active and unpaused | 20 |
| Explicitly paused | 12 |
| Remaining vaults | 6 inactive or without game state |
| Active/unpaused with all resources zero | 10 |
| Active/unpaused with all resources at capacity | 9 |
| Active/unpaused with no generator production | 4 |
| Active/unpaused with powered generator output below draw | 10 |
| Active/unpaused with recorded activity within 24h | 4 |
| Caps balance median / maximum, all vaults | 3,303.5 / 15,716 |
| Persisted objective templates | 89 |
| Local JSON objective entries | 91 |

Representative **calculated current rates**, units/minute:

| Vault | Population | Power output / draw | Net power | Powered food / water output | Food/water draw each | Stock condition |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| V32 | 36 | 30.24 / 50.50 | −20.26 | 40.32 / 30.24 | 12.96 | all zero |
| V33 | 36 | 46.37 / 50.00 | −3.63 | 42.34 / 34.27 | 12.96 | all zero |
| V35 | 36 | 36.29 / 50.00 | −13.71 | 40.32 / 30.24 | 12.96 | all zero |
| V17 | 49 | 200.74 / 47.00 | +153.74 | 20.16 / 20.16 | 17.64 | all full |
| V37 | 36 | 342.43 / 57.50 | +284.93 | 42.34 / 30.24 | 12.96 | all full |
| V38 | 36 | 125.28 / 51.50 | +73.78 | 40.32 / 58.46 | 12.96 | all full |

“Powered” food/water output means potential output with positive power. At zero power those rooms currently produce
nothing. V32/V33/V35 have enough food/water workers but a power deficit shuts both down. Their persisted generator
footprints/output and staffing differ from the corrected boosted seed. Seed-time improvements do not repair an
existing vault. V17/V37 show how upgrades/merging can overshoot consumption by a large margin.

A uniform 20% reduction in power draw leaves **9/20** active vaults with a power deficit instead of 10/20; a 35%
reduction leaves **8/20**. Four have no generator output and cannot be rescued by a reasonable rate tweak.
These comparisons hold staffing fixed and evaluate potential powered output; they are not forecasts of player behavior.

### Morale, treatment, and actual progression records

A second read-only snapshot at a later timestamp adds population/status and retained progression data. Labels use
that snapshot's same creation order; the source JSON records its capture time. Non-deleted rows can still have a
DEAD status, so they are not automatically living population.

| Vault | Mean happiness (non-deleted) | Mean radiation / max HP | Unassigned non-deleted | Stored Stimpaks / RadAway |
| --- | ---: | ---: | ---: | ---: |
| V32 | 41.92 | 63.9% | 18 | 30 / 30 |
| V33 | 31.44 | 75.0% | 12 | 30 / 30 |
| V35 | 26.67 | 72.2% | 15 | 30 / 30 |
| V37 | 86.11 | 0.0% | 13 | 30 / 30 |
| V38 | 95.94 | 0.3% | 13 | 30 / 30 |

The dark legacy vaults have severe radiation and low morale despite medication in storage. This points to a recovery
workflow question: can the player see, transfer/use supplies, staff power, and clear the deficit without guesswork?
It does not prove that treatment is broken; recovery actions were not executed. More medication production would
not address these full stores. Likewise, aggregate idle dwellers include intended non-workers and combat/rest states;
verify assignment eligibility rather than assuming all unassigned rows should work.

Across the 38 vaults there is only **one retained crafting order** (0 recorded caps spent), **45 retained exploration
runs**, and **9 completed quest links**. Only 575 caps are represented in structured quest reward receipts; historical
completed links can have missing receipts. These are retained-record counts, not lifetime activity totals. The sample
cannot establish crafting throughput or reconstruct historical caps income. Current scripted prices and reward catalogs
are stronger evidence for the economy proposal than those sparse records.

## 2. Resource mechanics and the fragile margin

Effective production settings match local defaults:

| Parameter | Current |
| --- | ---: |
| Primary production rate per effective SPECIAL/second | 0.0012 |
| Power consumption per size × tier unit/minute | 0.50 |
| Food/water consumption per counted dweller/minute | 0.36 each |
| Tier output multiplier | 1 / 1.5 / 2 |
| Junior production contribution | 50% |
| Low / critical stock warnings | 20% / 5% |
| Regular tick / max single catch-up window | 60s / 3,600s |
| Medical production rate | 0.01 |

Production = persisted room output × sum of effective worker stats × production rate × tier multiplier × seconds.
Power draw = sum of **every room's size × tier** × power rate × seconds, including generators, door, elevators,
and idle utility rooms. Food/water draw uses the resource CRUD's dweller row count. That count has no
`deleted_at` filter and no age/status weighting; the configured child-consumption multiplier is not used here.
Audit actual intended eligibility before changing this query. Do not assume dead, departed, exploring, and junior
rows should all be treated identically.

Starter size-3, tier-1 output is 28. Two effective SPECIAL-5 workers produce 20.16/min; one produces 10.08/min.
A standard complete room set has 28 weighted units and draws 14/min. A legacy boosted set can have approximately
103 units and draw 51.5/min. Increasing only the global production rate would further accelerate already-full
advanced vaults and would not extend the survival window of an unstaffed vault.

Storage is a short emergency buffer. With capacity 150 and no generator workers, a standard vault empties in
10.7 minutes from full, or **5.4 minutes from half**. Once the 20% warning fires at 30 units, only **2.1 minutes**
remain at −14/min. Food/water and medical rooms then stop together, worsening recovery.

### Candidate settings

These are candidates to playtest, not changes already applied:

| Candidate | Production | Power/unit/min | Food & water/dweller/min |
| --- | ---: | ---: | ---: |
| Current | 0.0012 | 0.50 | 0.36 |
| **Gentle — first trial** | **0.0012** | **0.40 (−20%)** | **0.30 (−16.7%)** |
| Relaxed comparison | 0.0012 | 0.35 (−30%) | 0.27 (−25%) |

All-room power nets and **raw** time from half storage to empty:

| Scenario | Current net/min | Gentle net/min | Current empty time | Gentle empty time |
| --- | ---: | ---: | ---: | ---: |
| Standard, 2 × SP5 | +6.16 | +8.96 | — | — |
| Standard, 1 × SP5 | −3.92 | −1.12 | 19.1 min | 67.0 min |
| Standard, no workers | −14.00 | −11.20 | 5.4 min | 6.7 min |
| Expanded, 40 units, 2 × SP5 | +0.16 | +4.16 | — | — |
| Expanded, 40 units, 1 × SP5 | −9.92 | −5.92 | 7.6 min | 12.7 min |
| Legacy boost, 103 units, 3 × SP5, small generator | −21.26 | −10.96 | 3.5 min | 6.8 min |
| New boost, 103 units, 5 × SP8, size-6 generator, adults only | +115.54 | +125.84 | — | — |
| Developed, 121 units, 4 × SP8, tier-3 size-6 generator | +317.36 | +329.46 | — | — |

The gentle candidate makes a **single-worker disruption recoverable**, but leaves missing staffing and obsolete
seed layouts as real problems. It preserves a reason to reassign workers and upgrade. The relaxed candidate makes
the standard one-worker generator net-positive; decide whether that removes too much of the desired staffing tradeoff.

Rounding matters: the expanded current +0.16/min becomes zero persisted change on a 60-second tick. Forecasts based
only on raw rates can disagree with observed storage. The full CSV includes persisted tick deltas. Do not tune a
margin to less than one stored unit without resolving fractional accumulation or acknowledging the staircase.

Increasing capacity by 25–50% is a separate lever for unattended recovery, but cannot fix a persistent deficit.
A two-hour warning/recovery window with zero production is much more than a modest capacity adjustment: at 11.2/min
it needs about 1,344 units for two hours from full. Choose session expectations before promising hours of safety.

### Unattended drain and catch-up

An active, unpaused vault continues receiving resource ticks regardless of recent activity. The incident code
checks online activity; resource processing does not. The 1-hour catch-up cap limits a single processing gap,
**not total loss over a day of normal background worker ticks**. A player can therefore return to depleted stock
without having faced online incidents.

For a complete standard set, two SP5 workers in each primary room, power initially 0 and food/water 75:

| Same elapsed hour | Final power / food / water |
| --- | --- |
| One 3,600-second resource calculation | 150 / 0 / 0 |
| Sixty persisted 60-second calculations | 150 / 150 / 150 |

The single window tests power at its start and disables other production for the whole hour even though the generator
recovers power. This is an isolated kernel reproduction, not a live mutation or the normal uninterrupted tick path.
Fix/redefine catch-up before evaluating a power-out return experience.

Suggested normal-mode policy to design: bounded unattended negative resource loss or explicit automatic rest/pause
with clear resumption, while retaining useful positive progress. Keep survival mode separate. Test consistency
between repeated ticks, reconnects, and one catch-up window so repeatedly logging in/out cannot change the result.

## 3. Objective rewards: source of inflation and misleading effort

The production catalog contains 22 daily, 26 weekly, 34 achievement, and **7 starter** templates.
The local JSON describes 9 starter entries, but `Collect 150 Power` and `Reach 10 Dwellers` share their challenge
names with other categories. Seeding uses challenge alone as its uniqueness key and skips existing rows. In production
those names resolve to daily `100 power` and achievement `1000 caps`, respectively, rather than starter `50 power`
and `100 caps`. These are identity/rollout issues, not just payout values. Changing JSON alone does not update
persisted rewards. A migration must preserve completed history and intentionally handle in-flight links.

Repeatable assignment is uniform sampling, 5 daily and 3 weekly after refresh; initial seeding has different counts
and boosted achievement selection. These are scheduled batches, not an endless immediate replacement queue.
Assuming every sampled objective is completed and no stage filtering:

| Category | Catalog cap payouts total | Expected caps per fully completed random batch | Possible cap-only batch range |
| --- | ---: | ---: | ---: |
| Daily: 5 of 22 | 4,550 | 1,034 | 0–2,550 |
| Weekly: 3 of 26 | 25,650 | 2,960 | 0–7,500 |
| Achievement: all 34, theoretical lifetime | 95,250 | not recurring | plus one lunchbox |

The recurring full-completion expectation is approximately **10,198 caps/week** (7 × daily + weekly), before quests,
exploration, sales, milestones, and one-time starter grants. This is a catalog expectation, not measured player income;
not every task is feasible or completed, and not every achievement is assigned to every vault.

Examples:

| Task | Current reward | Problem | First proposal |
| --- | ---: | --- | --- |
| Collect 200 caps | 150 caps | 75% additional payout for ordinary income | 20 caps (external earnings only) |
| Collect 500 caps | 300 caps | 60% additional payout | 50 caps |
| Collect 2,000 caps weekly | 1,000 caps | 50% additional payout | 200 caps |
| Collect 150 food/water/power | 100 same resource | 66.7% injection; cap may discard much of it | 15, or a small caps reward |
| Build 2 rooms | 500 caps | potentially pays more than cheap builds cost | 50 caps; preserve net construction cost |
| Assign 2 / correctly assign 2 | 200 / 300 caps | pays for clicks; eligible tasks can overlap | replace repeatable version with useful sustained staffing |
| Reach 30 population weekly | 3,000 caps | large repeatable reward for a state already achieved | stage-gated growth goal; illustrative 250 caps |
| Train a dweller, achievement | 800 caps | large payment alongside training benefit | 100 caps |
| Train to 10, each stat | 2,000 caps | qualifier ignores target value | fix qualification first; then 250 caps |
| Build a living room, achievement | 600 caps | cheap construction can pay for itself many times | 50 caps |
| Reach 100 dwellers, achievement | 10,000 caps | growth pays heavily on top of unlocks | 500 caps plus visible recognition |

A first target for **fully completed** typical batches is 150–300 daily caps and 400–800 weekly caps, with starter
onboarding grants treated separately. These targets are proposals, requiring session measurements. The CSV sketches
all local objectives: assignment replacements are marked `0 caps` placeholders, **not an instruction to ship empty
rewards**. Add a 25–75 daily / 100–200 weekly budget for meaningful replacement goals. The illustrative achievement
pool is 7,250 caps instead of 95,250; this is an aggressive comparison to discuss, not a mandate for a blanket 92% cut.
Preserve or separately value item/lunchbox rewards rather than treating them as free.

### Qualification problems to fix before nerfing rewards

- `TrainEvaluator` checks `stat_trained` but ignores `target_value`. The training event includes no final stat value.
  A pure matcher reproduction confirms that a Strength event with no value matches “Train Dweller to 10 Strength.”
  Seven such templates represent **14,000 caps** of potential falsely qualified achievement rewards if assigned.
- `LevelUpEvaluator` checks whether a new level is at least the threshold, but neither it nor the base progress engine
  records distinct dweller identities. The same dweller at levels 5 and 6 matches “Level up 2 Dwellers to Lv.5.”
- `AssignEvaluator` counts events rather than distinct useful dwellers. Same-room reassignment is rejected, but
  alternating valid rooms can still produce repeated events. Validate the complete player path before calling this
  a confirmed farming exploit.
- `BuildEvaluator` also counts upgrades, despite task labels saying “Build.” Either restrict counting or make labels
  and targets explicit.
- `ExpeditionEvaluator` subscribes to `QUEST_COMPLETED`, not exploration return. “Complete Expeditions” needs naming
  or event-contract reconciliation.
- Random assignment does not filter stage/capability. A starter can get an irrelevant rare-scrap or later-stage goal.
- Production emits **gross calculated output**, not retained stock or net gain, to collect objectives, even at storage
  cap. This may be correct for a renamed “Produce” task; it is misleading if the player reads “Collect” as retained loot.

Objective rewards deliberately suppress collect events (`emit_event=False`), so these findings do **not** show an
infinite reward-to-reward caps loop. Ordinary quest/sale income can still complete caps objectives on top of its own
reward. Check transaction/retry correctness independently from payout tuning.

## 4. Caps sources and sinks need a common scale

Useful current price anchors:

| Sink or item | Caps |
| --- | ---: |
| New basic production/living segment, first of its type | 100 base, +25 per existing same-name room |
| Basic production upgrade, tier 2 / tier 3 | 500 / 1,500 per segment |
| Overseer's Office build / tier-2 / tier-3 upgrade | 1,000 / 3,500 / 15,000 |
| Weapon workshop build / tier-2 / tier-3 upgrade | 800 / 8,000 / 60,000 |
| Outfit workshop build / tier-2 / tier-3 upgrade | 1,200 / 12,000 / 90,000 |
| Common / rare / legendary craft | 0 / 100 / 500 plus required junk |
| Common / rare / legendary junk sale | 2 / 50 / 200 per piece |
| Manual recruitment | 500 |
| Revival | level-based, 50–2,000; distinct difficulty/lifecycle policy |

Build prices use current stored room-row count, while upgrade costs multiply segment count. Thus the table's base
costs are not a quote for every room in every vault. Destruction refunds 50% of stored cost components and upgrades;
refunds should be distinguished from genuine income. Verify merged-layout refund parity before designing a farming
fix or changing prices.

Catalog weapon sale values: common 10; rare median 100 (range 100–500); legendary 500. Outfit medians are 10/100/500,
with exceptions. These are catalog values, not necessarily every pre-existing persisted item's value.
A legendary craft consumes three common, three rare, and three legendary compatible materials: their liquidation
value is **756 caps**, plus 500 crafting caps = **1,256 opportunity cost**, versus a typical 500-cap item sale.
Rare crafting uses materials worth 156 plus 100 caps, versus a usual 100-cap sale. Crafting is usually an equipment
upgrade rather than a profitable conversion under these values; verify catalog exceptions before claiming no arbitrage.

A single normal completed daily batch (~1,034 caps) can fund the first Office's base cost, around two basic tier-2
segment upgrades, or two legendary crafts' cash fees. But the weapon workshop's tier-3 upgrade is 60,000 per segment:
**180,000** for its fixed size-9 footprint. Easy routine income coexists with a very steep late construction wall.
Reducing all rewards while keeping all late costs would create a different grind, not a coherent economy.

### Other progression anchors

- Free-roam event interval is 10 minutes; a 10% discovery roll precedes the remaining 35%-loot weighted draw.
  Expected loot events ≈ **1.89/hour** in a stationary cadence model. Caps per loot event average
  `20 + 2×Perception + 3×Luck`: ≈85 caps/hour at P=L=5, ≈132 at P=L=10, before pets, item sales, site rewards,
  return travel, interruptions, and actual duration limits. This is an analytical baseline, not a whole-expedition yield.
- Quests add substantial one-time income: the four Vault-Tec training-chain entries contain 200 + 500 + 750 + 2,000
  guaranteed caps (**3,450**) plus items. “Overseer Certification” also lists five lunchboxes and a legendary dweller.
  Eligibility and actual lifecycle must determine effort; narrative text alone is not a duration contract.
- Incident loot already differs by type: fires pay no caps, infestations fractional caps, intrusions higher caps plus
  catalog gear. Do not use the obsolete August “all incidents dispense free caps” conclusion to tune current incidents.
- Current crafting is a timed order system, despite older roadmap/reference text describing instant crafting.
  At total relevant base stat 10, common/rare/legendary durations are **40 minutes / 4h / 16h**; at stat 40,
  **20 minutes / 2h / 8h**; the floor is **15 minutes / 1.5h / 6h**. Orders snapshot worker base stats at start;
  this path does not apply outfit/pet effective stats. Also inspect simultaneous orders per workshop before equating
  wall-clock duration with throughput; the start path has no single-active-order restriction.
- Stat 1→2 training takes **2.5h**, not the docstring's 2h. Stat 5→6 takes 4.5h and 9→10 takes 6.5h.
  Training 1→10 totals **40.5h** at tier 1 or 24.3h at tier 3, excluding pets, youth mechanisms, and interruptions.
  Large milestone rewards should correspond to this real effort rather than one ordinary training event.

Suggested economic model: exploration, useful loot sales, and meaningful quests form primary income; routine objectives
provide a modest bonus; achievements primarily mark progression. Price expansion in meaningful sessions and use junk,
recipes, worker time, and capacity as deliberate constraints. Avoid adding arbitrary upkeep fees to remove excess caps.
Measure existing flows before reducing large upgrade prices; candidate late-price reductions should be tied to time to
first useful upgrade, not a guessed inflation percentage.

## 5. Wave 2 rollout proposal

| Slice | Change | Evidence required / guardrail |
| --- | --- | --- |
| 2A — correctness | target-value and distinct-dweller qualification; template identity; labels/event contracts | Failing regression first for each confirmed bug; migrate persisted rows without repaying completed objectives |
| 2B — resource relief | Trial power 0.40/unit/min and food/water 0.30/dweller/min; keep production 0.0012 | Standard + full utility rooms; legacy boosted; new boosted; marginal staffed vault; no-worker outage; advanced merged vault |
| 2C — existing-vault recovery | Decide previewable legacy generator/crew repair or player-driven recovery assistance | Do not apply new seed assumptions to stored vaults blindly; preserve placements, inventory, and progression |
| 2D — reward budgets | 10% collection bonuses; small routine payouts; useful replacements for assignment churn | Actual completion times and overlap; both refreshed and initial assignments; fit stage/capability |
| 2E — unattended pacing | Deliberate normal-mode negative-drain limit/rest policy; correct zero-power catch-up | Repeated ticks equal intended catch-up; explicit pause and survival rules; clear return feedback |
| 2F — prices and throughput | Revisit late upgrade walls, crafting bottlenecks, and reward-value consistency | Measured source/sink mix, material scarcity, queue throughput, and time to useful upgrade |

Suggested playtest targets to refine: a healthy starter remains positive with normal staffing; temporarily losing one
worker leaves enough time for a normal session to recover; no useful progression action requires hidden Endurance
leveling history; routine objectives cannot fund repeated expansion through reassignment alone; growth has an attainable
next purchase; advanced surplus does not invalidate all staffing decisions. Set numerical session targets with observed
playtime rather than importing the original game's cadence.

For a one-week observation period, record per-vault caps credited/spent by existing operation boundary, objective type
and completion duration, time at zero/cap, actual worker moves, shortage recovery time, and useful purchases.
Current caps balance and aggregate profile earnings cannot reconstruct source attribution. Objective links have no
completion timestamp and daily/weekly refresh deletes them, so historical objective income cannot be inferred reliably
from the snapshot. A small source-tagged metric at deposit/withdraw boundaries may be sufficient; an elaborate economic
subsystem is not required.

## 6. Reference policy and verification

[Issue #982](https://github.com/ElderEvil/falloutProject/issues/982) guides this review. The useful FAQ lessons are that
production/storage need separate explanations and objectives can incentivize artificial actions:
[resources §3](https://github.com/therabidsquirel/The-Fallout-Shelter-FAQ/wiki/Section-3:-Rooms,-Resources,-and-Storage),
[objectives §11](https://github.com/therabidsquirel/The-Fallout-Shelter-FAQ/wiki/Section-11:-Objectives).
Those are comparative design evidence, not this game's formulas. Preserve the maintainer's explicit decision:
**leveling before Endurance training must never permanently reduce a dweller's health potential.** Preserve race
immunity, outfit resistance, progression visibility, and intentional notification preferences in
[GAME_MECHANICS.md](GAME_MECHANICS.md).

Validation performed:

- Read-only deployed configuration and DB snapshot; actual stored crews/room outputs used for live rates.
- Deterministic resource candidates and single-window/stepped outage reproduction using current kernel.
- Pure objective matcher reproductions for target-value and distinct-dweller qualification gaps.
- Existing resource/objective coverage: **51 passed, 2 SQLAlchemy teardown warnings**:
  `cd backend && uv run pytest app/tests/test_services/test_resource_manager.py app/tests/test_scripts/test_simulate_resource_economy.py app/tests/test_services/test_objective_evaluators.py app/tests/test_services/test_objective_assignment_service.py -q`.
  Passing existing tests does not validate the uncovered qualification gaps or player-facing balance.
- Existing unrelated `backend/app/tests/test_crud/test_room.py` local changes were left untouched.

The research did not change game implementation, APIs, production configuration, migrations, or deployments. The next implementation should split confirmed correctness fixes from value tuning, with before/after
scenario evidence and appropriate regression coverage.
