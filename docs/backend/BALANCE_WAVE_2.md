# Wave 2 balance review — resources, objectives, and economy

Research date: **2026-10-13**. Read-only production inspection plus deterministic
simulation. The report proposed changes; this file records the assessment and the
outcome that shipped.

## Assessment

Resources were brittle around a power deficit, while objectives paid too much for
routine actions. Spare caps cannot repair a staffing deficit, and large resource
rewards can temporarily hide one. The applied pass creates a longer recovery window
and reduces routine reward income while preserving staffing, upgrades, exploration
and milestone recognition.

The production snapshot was split rather than uniformly scarce: of 20 active,
unpaused vaults, 10 had zero power/food/water and 9 were full in all three; only 4
had recorded activity within 24h. Older/test/abandoned vaults dominated the sample,
so these are persisted conditions, not a measured failure rate among current players.

## Applied decisions

### Resource drain and offline reserves

- Power draw **0.50 → 0.40** per weighted room size/tier/minute; food and water
  **0.36 → 0.30** per counted dweller/minute. Production stays at **0.0012**.
- Drain steps in ≤60s increments so restored power re-enables other production on the
  next step; fractional stock persists on `GameState`.
- After the 10-minute activity timeout, net-negative changes stop at **25% capacity**
  (or the current amount if already below that floor). No free stock is granted.
- Dead/deleted and exploring/questing dwellers are excluded from consumption and
  crews; the existing 70% youth multiplier applies.

Rationale: a uniform 20% power reduction cut active vaults with a deficit from 10/20
to 9/20. The "gentle" setting makes a single-worker disruption recoverable while
leaving missing staffing and obsolete seed layouts as real problems. A single 3,600s
catch-up window is not equivalent to sixty 60s ticks when power starts at 0.

### Objective rewards and counting

- Routine payouts were reduced and reassignment farming replaced with distinct-dweller
  goals: an expected fully completed batch is now **~216 caps daily** and **~590 caps
  weekly** (was ~1,034 / ~2,960); the achievement caps pool fell from **95,250 to
  43,765**. Starter grants are unchanged.
- Primary-resource tasks count **gross output**, including at full storage, with
  fractional output carried across ticks/restarts; gifts and refunds do not advance
  them. Medical tasks count supplies actually stored; item tasks accept item events.
- **Build** requires a new room; quest objectives say **Quests**. Non-starter
  assignment/correct-assignment/training/level-up tasks count **distinct dwellers**;
  training thresholds check the resulting stat value.
- Templates keep stable category-qualified keys. The catalog migration updates the
  persisted catalog and inserts missing templates without discarding custom templates,
  links or progress, and freezes earned rewards so a pending claim keeps its payout.

### Qualification fixes

The reward nerf followed correctness fixes that were themselves inflation sources:
`TrainEvaluator` ignored `target_value` (a value-less training event matched "Train to
10 Strength"); `AssignEvaluator` counted events, not distinct dwellers;
`BuildEvaluator` counted upgrades; and production emitted gross output to
"Collect"-labelled tasks. These are now bounded as described above.

## Competitive reference

The Fallout Shelter objective pool pays roughly **50 caps** for collecting 100–200 of
a resource and **~100 for 300**. Routine resource tasks here deliberately sit at about
half that, keeping routine objectives a modest bonus rather than the primary cap
source. Exploration, useful loot sales and quests remain the primary income;
achievements primarily mark progression. See issue #982.

Reference: [Fallout Shelter objectives](https://fallout.fandom.com/wiki/Fallout_Shelter_objectives)
(comparative design evidence, not this game's formulas).
