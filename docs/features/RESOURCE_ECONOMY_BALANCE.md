# Resource Economy Balance Baseline

## Goal

Make power, food, and water a visible staffing decision on the existing 60-second game tick. A healthy starter vault
must be safe when fully staffed, while moving or losing production workers must have an immediate, recoverable cost.

This is a baseline for play-testing, not a final economy specification.

## Current Problem

The room output formulas were imported from Fallout Shelter, but this project evaluates them once every 60 seconds.
The existing `0.1` production rate therefore produces far more than a vault can consume in one tick. Resources fill
almost immediately, so room staffing, SPECIAL, capacity, and upgrades do not create meaningful choices.

## Baseline Contract

For a standard starter vault with three tier-1, size-3 production rooms; nine dwellers; and two matching SPECIAL-5
workers per room:

| Staffing state | Power per tick | Food/water per tick | Intended player result |
| --- | ---: | ---: | --- |
| Two matching workers | `+1` | `+2` | Safe, gradual recovery from mid-storage |
| One matching worker | `-2` | `-1` | Reassigning a worker is an immediate trade-off |
| No matching workers | about `-4` | about `-3` | Neglect becomes visible before it is catastrophic |

The tick persists integer resources. The targets above therefore describe the effective stored-resource change after
rounding, not only the raw formula result.

## First Adjustment

Set `RESOURCE_BASE_PRODUCTION_RATE`'s default to `0.0003` per SPECIAL point per second.

At the 60-second tick this gives a fully staffed starter room `5.04` raw units per tick. Current baseline consumption
is `4.5` power per tick for the three size-3 rooms and `3.24` food/water per tick for nine dwellers, producing the
contract above after persistence rounding.

Only this constant changes in the first pass. Keep room output formulas, resource capacity, costs, tier multipliers,
thresholds, and consumption rates unchanged so player feedback has one clear cause.

## Tuning Plan

1. Play a starter vault for 20–30 ticks with the full staffing setup, then reassign one worker from each resource
   room for five ticks and restore them.
2. Verify the baseline contract in the live UI: rates are understandable, storage changes are visible, and recovery
   is possible without an admin action.
3. Test population pressure at 12, 18, and 24 dwellers. Add workers or rooms only when the preceding population band
   requires it.
4. Tune within `0.00025`–`0.00035` before changing a second system. Make one adjustment per play-test cycle.
5. Only after the starter loop is stable, assess capacity growth, room costs, tier multipliers, medical production,
   and objective/quest resource rewards.

## Guardrails

- Do not compare this project’s per-tick resource totals directly with Fallout Shelter’s client cadence.
- Use the deterministic resource report only to verify the current formula; older Monte Carlo balance scripts mirror
  some configuration and are not the baseline decision source until they are refreshed separately.
- Do not change production and consumption in the same tuning pass.
- Do not compensate for resource tuning with caps, quest rewards, or room prices before the starter loop is evaluated.
- Preserve the existing low (20%) and critical (5%) warnings for the first pass; revise them only after observing
  how often players encounter them.
