# Balance wave 3 — rates, graded deprivation, and the measured bands

Source: issue #1456. Reviewed against the code in four rounds before implementation.

## What changed

1. **Rates retuned and measured**, not copied from the issue. Power got its own knob because one
   `base_production_rate` cannot give power one tension and food another.
2. **Deprivation is graded and non-lethal**: warnings, reduced crew output, health erosion down to a floor.
3. **The counting is persisted**: `GameState.food_deprived_ms` / `water_deprived_ms` accumulate active
   time, so retries, restarts and catch-up windows cannot disagree or heal a dweller.

## Rates (shipped)

| knob | before | now | unit |
| --- | ---: | ---: | --- |
| `base_production_rate` (food/water) | `0.0012` | `0.00020` | per SPECIAL point per second |
| `power_production_rate` (new) | — | `0.00040` | per SPECIAL point per second |
| `food`/`water_consumption_per_dweller` | `0.30` | `0.14` | per minute |
| `power_consumption_rate` | `0.40` | `0.19` | per minute, per room size × tier |

Capacities, room output formulas, tier multipliers and `offline_reserve_fraction` are untouched.

### Why these numbers

The seeded layouts are the gate (`backend/app/tests/test_services/test_balance_wave_3.py`):

| layout | measured result |
| --- | --- |
| standard starter (tier-1 size-3 rooms, SPECIAL 5, no outfit) | power **≈1.43×** surplus against its seeded draw |
| boosted starter (size-6 tier-2 generator, output 70, outfit-boosted SPECIAL 8, 5 adults + 1 apprentice) | power **≈5×** — a paid head start stays power-rich by design |
| boosted diner (three crew, one half-rate apprentice slot) | food **≈1.2×**; this is the binding case |

The issue's `0.00010` power rate was infeasible: it produced 1.68/min against 5.89/min draw on the
standard seed. The issue's "one worker sustains 8.7 dwellers" does not survive the boosted crew's
half-rate apprentice slot either; the shipped base lands near **12** dwellers per bare worker, so the
scarcity lever is the stock buffer, not the staffing ratio. The issue's absolute targets were treated
as hypotheses and replaced by these measurements.

### Starter lessons

Production-gated starter objectives keep their mechanical shape but halved their amounts
(`Collect 50 → 25`, `Produce 100 → 50`), because the arc must still fit its 30-minute budget. The
short-rations experiment multiplies food/water production by 0.35 on top of these rates, so its arc is
allowed 60 minutes by test rather than mutilating the shared tutorial.

## Deprivation ladder

Config lives in `HealthConfig`; logic in `app/services/game_tick/deprivation.py`.

| step | value |
| --- | --- |
| dry | resource at 0, warning only |
| hungry / thirsty | after 60 min (food) / 30 min (water) of accumulated dry time |
| crew output | ×0.7 while hungry or thirsty (applied before the production step) |
| food erosion | 0.10 % of max health per minute |
| water radiation | 0.15 % of max health per minute |
| floor | 25 % of max health — `deprivation_hp_floor_fraction` |
| refill | above 5 % of max resets the counter, after that tick's increment is applied |
| lethality | none; the death predicate stays incident-driven |

**Ordering invariant.** Each pass derives the cumulative amount from the persisted counter, applies
`cumulative(after) − cumulative(before)`, and only then resets on refill. Reversing that order makes the
increment negative and heals the dweller — this was caught in review before implementation.

**Immunity.** Non-humans keep radiation immunity; outfit resistance is deliberately not applied because
the radiation enters through drinking. The pass writes radiation directly, so it gates immunity itself
and never touches the `pet` relationship (a lazy load there would break the tick's async session).

**Warnings** reuse `RESOURCE_LOW` / `RESOURCE_CRITICAL`, which already have preference gating, bell icons,
routing and generated types. No new enum values, no client regeneration. Rows are staged in the phase
transaction and committed with it.

## Measured bands

| band | shipped result |
| --- | --- |
| parity-build buffer, pops 9 / 20 / 35 / 50 (one storage room per 8.5 dwellers) | **2.1 h – 4.0 h**, inside the 2–4 h target |
| whole food crew removed at pop 20 | empties in **≈2.7 h**, inside the 2–3 h target |
| one food worker short at pop 20 | **≈6.7 h** to empty — accepted as recoverable; the issue's `≥12 h` would need larger caps or lower consumption |
| food floor from full health | **12.5 h** (0.1 %/min) |
| water floor from full health | **8.3 h** (0.15 %/min) |
| deaths from deprivation | none, by construction; the ladder never calls the death path |

Floor arrival is a multi-hour property and belongs in scratch verification, never in the production pod
(the resource simulator OOMs there).

## Deployment notes

- Migration `b1e2f3a4c5d6` adds two non-null bigint counters defaulting to 0. That default is a true value
  ("no deprived time"), not a placeholder, so no backfill.
- Migrations live in `app/alembic/baseline_versions/` — `alembic.ini` overrides `version_locations`, so a
  file placed in `alembic/versions/` is silently ignored.
- Rates are process-wide config: every vault adopts them when the API and worker restart. Confirm no
  unintended `RESOURCE_*` / `HEALTH_*` override is set on either deployment.
- `GET /game/balance` should show the new numbers after rollout. The 30–90 minute live check is warnings,
  output drop, erosion onset and **no deaths**; the floor takes hours and is proven in scratch.

## Follow-ups

- The tick commits per phase by design. Unifying the resource window under one owner is optional future work; the
  dweller phase already stages counters, health and warnings together.
- Legacy dead knobs (`starvation_threshold`, `dehydration_threshold`, `regen_per_tick`) remain for a cleanup
  pass; `regen_per_tick` still feeds the incident simulator's default.
