# Vault Experiments — Underlying Systems Plan

Implementation plan for the data, persistence, modifier, and content systems behind
playable Vault-Tec experiments (canon: 17 control vaults, 105 experiments — food
shortages, skewed demographics, early openings, prototype testing). Control vaults
stay today's game, byte-for-byte; experiments are opt-in condition bundles.

Status: **plan only, nothing implemented**. Companion idea catalog lives in the roadmap
("Vault Experiments" section); this document is the build order for the machinery.

## 1. Design constraints

- **Control is sacred.** Every modifier resolves as overlay-on-base; with no experiment
  set, all code paths must behave exactly as today (existing suites prove it).
- **Data over code.** A new experiment ships as JSON + content, never a migration or a
  branch in game logic. If adding an experiment requires touching a service, the hook
  is missing — add the hook, not the special case.
- **Disclosed upfront.** Unlike canon, the picker shows every condition before creation.
  No hidden modifiers, ever; the Enclave-observation flavor is narrative, not mechanics.
- **One new table: zero.** Experiment state that must persist (cryo unlocks, prototype
  outcomes, election timers) lives in per-vault JSON flags, not new tables.

## 2. Data layer: `experiments.json`

New file `backend/app/data/experiments.json`, loaded by a cached
`load_experiments()` next to the exploration `data_loader` (same ergonomics,
Pydantic-validated, validated shapes in `app/schemas/experiment.py`):

```text
ExperimentDefinition
├── id, name, tagline, briefing (overseer text shown at creation)
├── modifiers: ExperimentModifiers
│   ├── consumption_mult: {power?, food?, water?}
│   ├── production_mult: {power?, food?, water?, stimpak?, radaway?}
│   ├── happiness_tick_delta: float (added per happiness tick)
│   ├── radio_recruitment_mult, radio_happiness_mult
│   ├── incident_chance_mult, incident_weights: {raider_raid: 2.0, ...}
│   ├── exclusive_incidents: [incident_type, ...] (must exist in incident tables)
│   ├── recruit_gender_weights: {male, female}, recruit_rarity_bonus
│   ├── affinity_mult, pregnancy_chance_mult
│   ├── starting_loadout: {weapons: [...], outfits: [...], caps?}
│   ├── frozen_dwellers: int (Cold Sleep seed count)
│   └── seed_stat_bias: {strength: +1, ...} (applied at dweller seeding)
├── objectives: [objective_chain_id, ...] (existing objective system)
└── observation_flavor: [journal lines drip-fed by the tick]
```

Validation rules enforced at load: multipliers are finite positives, referenced
incidents/objectives exist, `frozen_dwellers` requires a cryo unlock objective in
the chain. Unknown keys reject (fail fast on typos, same as site definitions).

## 3. Persistence: two columns, no new tables

Migration adds to `vault`:

- `experiment_id: VARCHAR(64) NULL` — plain string key into `experiments.json`,
  deliberately NOT a PG enum (experiments ship as data; enum churn per experiment
  would repeat the outage class in AGENTS.md).
- `experiment_flags: JSONB, default {}` — per-vault experiment state: cryo
  unlocked/revealed, prototype outcomes taken, last election tick, observation
  cursor. Name-keyed, idempotent writes; readers use `.get()` with defaults so
  old rows and control vaults behave identically.

No backfill needed (NULL/`{}` already mean "control"). Downgrade drops the columns.

## 4. Modifier overlay service

New `app/services/experiment_service.py` (thin, stateless, pure where possible):

- `get_experiment(vault) -> ExperimentDefinition | None` (None = control fast path).
- `modifier(vault, path, default)` — single choke point resolving
  `base → experiment overlay → value`, so call sites never branch on experiments.
- Per-system hook table (each hook is a 3–10 line call-site change):

| System | Hook point | Modifier used |
|---|---|---|
| Resources (`resource_manager`) | consumption/production calc | `consumption_mult`, `production_mult` |
| Happiness tick | per-tick delta | `happiness_tick_delta` |
| Incidents (`incident_spawning`) | `spawn_chance_per_hour`, `get_spawn_weights()` | `incident_chance_mult`, `incident_weights`, exclusive types seeded into the weight table only for that vault |
| Radio recruitment | rate calc | `radio_recruitment_mult`, `radio_happiness_mult` |
| Seeding/recruitment | gender + rarity rolls | `recruit_gender_weights`, `recruit_rarity_bonus`, `seed_stat_bias` |
| Relationships (`family_tick`) | affinity increment | `affinity_mult`, `pregnancy_chance_mult` |
| Starting loadout | vault seed | `starting_loadout` (built via `item_factory`, never direct constructors) |
| Cryo (Cold Sleep) | seed + unlock objective | `frozen_dwellers` + flags; frozen = existing unavailable treatment, no new status |

Caching: resolve the vault's definition once per tick/request (lru on id + flags
revision), never per-dweller-per-formula.

## 5. Creation flow: picker + disclosure

- Vault creation accepts optional `experiment_id` (validated against loaded
  definitions; unknown id → 400, never silent control fallback).
- Picker UI lists Control plus experiments with tagline + full condition disclosure
  (every modifier rendered human-readable — the briefing text is generated from the
  same JSON, so docs can't drift from mechanics).
- Seeding applies `starting_loadout`, `frozen_dwellers`, `seed_stat_bias` in the
  existing seed transaction (all-or-nothing with vault creation).
- Overseer briefing modal on first load (progression red line: modal + bell, and
  the experiment banner persists on the vault header while active).

## 6. Exclusive content plumbing (no new frameworks)

- **Incidents**: exclusive types are ordinary incident definitions gated by
  `experiment_id` in the spawn query; weights merge per vault at spawn time.
- **Objectives**: chains reference existing objective/evaluator machinery
  (`objective_evaluators.py`); experiment chains are data, e.g. "stockpile 500
  food", "first Cold Sleep revival", "complete 3 prototype tests".
- **Choices** (elections, Prototype Lab ethics): reuse the expedition choice/event
  plumbing — prompt schema, options, outcome branches — surfaced as modals, never
  bell-only.
- **Observation journal**: tick-advanced cursor over `observation_flavor`,
  delivered as flavor notification entries; purely cosmetic, zero mechanics.

## 7. Testing plan

- Loader: every preset validates; unknown incident/objective reference fails load;
  multiplier bounds enforced.
- Unit per hook: overlay math (mult composition order), cryo flag transitions,
  election timer, prototype branch outcomes — seeded RNG like expedition tests.
- Integration per preset: create vault with experiment → run ticks → assert the
  differentiated behavior vs a control vault created in the same test (the core
  regression: control behavior unchanged).
- Migration: chain pin test (same style as expedition migration test); NULL/empty
  defaults asserted.
- Anti-frustration: disclosure text generated from JSON is asserted to mention
  every nonzero modifier (docs-can't-drift test).

## 8. Rollout phases

- **Phase 0 (this doc + roadmap section)**: agree on the overlay contract and the
  eight launch presets.
- **Phase 1**: data schema + loader + migration + `experiment_service` with the
  resource/happiness/incident hooks; Control + Short Rations playable.
- **Phase 2**: creation picker + disclosure + briefing; remaining hooks
  (radio, seeding, affinity, loadout, cryo).
- **Phase 3**: exclusive incidents/objectives per preset; observation journal.
- **Phase 4**: choice events (elections, prototypes); balance pass on clear-rate
  and economy telemetry per experiment.

## 9. Open questions

1. Can an overseer change or abandon an experiment mid-game, or is it permanent
   at creation? (Recommendation: permanent; abandonment voids the fantasy.)
2. Do experiments gate multiplayer-adjacent features (trading post) or stay
   single-vault? (Recommendation: single-vault; cross-vault balance is a later phase.)
3. Should Cold Sleep's frozen state reuse `is_dead`-adjacent plumbing or a plain
   `status` value? (Decide in Phase 2 with the death-flow owners.)
4. Boosted vaults: subsume into experiments as a preset, or keep as an orthogonal
   toggle? (Recommendation: one experiment preset, "Ample Stores", so the code has
   one seeding path.)
5. Telemetry: which per-experiment counters ship in Phase 1 vs Phase 4?
