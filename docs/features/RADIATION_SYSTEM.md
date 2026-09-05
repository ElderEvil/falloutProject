# Radiation System — Current Mechanics & Follow-up

> **Status:** Implemented in v2.72.0; fixed RadAway capacity and the radiation healing cap landed after.
> Related: `EXPLORATION_SYSTEM.md`, `RESOURCE_ECONOMY_BALANCE.md`, `DWELLER_TEMPLATES.md`

## Current mechanics

Radiation is a dweller value capped at 1,000. It is gained through wasteland radiation events and Radscorpion incident damage; it reduces happiness above 50 rads, caps healing at `max_health - radiation`, and causes death at the configurable `death.radiation_death_threshold` (1,000 by default).

| Area | Behavior |
|---|---|
| Wasteland | Danger templates containing `rad` create `radiation_gain`, mitigated by Endurance (`max(2, 12 - endurance)`). The exploration event is recorded and live explorer updates include radiation. |
| Incidents | A Radscorpion attack adds radiation alongside its health damage. |
| Health bars | `UProgressBar` renders radiation as a red segment that replaces the rightmost healthy portion. It is used by the dweller card/grid and explorer summary/detail views. |
| Consequences | Happiness loses 1 point per tick when radiation is above 50. The game loop records a radiation death once radiation reaches the configured threshold. |
| Manual treatment | `POST /dwellers/{id}/use_stimpack` heals 40% of max health but never past `max_health - radiation`; at the cap it reports that RadAway must unlock the rest. `POST /dwellers/{id}/use_radaway` removes up to 50% of max health in radiation without healing. The detail UI can issue supplies from vault storage before use. |
| Exploration treatment | An explorer consumes one carried RadAway automatically when radiation is above the exploration threshold; its event log records the removal. |

## RadAway behavior

### Current behavior

Both manual and exploration paths remove up to 50% of the dweller's maximum health worth of radiation, clearing a smaller remaining amount:

```text
radiation_removed = min(current_radiation, floor(max_health * 0.5))
```

The same fixed-capacity calculation is used by both manual and exploration treatment. Treatment starts at 30% radiation relative to max health:

- Chat recommends RadAway at `radiation / max_health >= 30%`.
- Exploration auto-use checks `radiation / max_health >= 30%`.

### Normalization (implemented)

One RadAway removes a fixed capacity — up to 50% of max health — clearing a smaller remaining amount.

```text
radiation_removed = min(current_radiation, floor(max_health * 0.5))
new_radiation = current_radiation - radiation_removed
```

For a dweller with `max_health = 130`, one RadAway removes at most 65 radiation. The same max-health-relative threshold should govern chat recommendations and exploration auto-use.

## Implementation checklist

1. Add one backend medical helper/service for RadAway removal; use it from the manual endpoint/CRUD path and exploration auto-use. Inventory ownership stays separate: a dweller carries manual supplies, while an exploration carries its own supplies.
2. Define one shared RadAway threshold as a percentage of `max_health`; use it for chat medical recommendations (including deterministic action validation) and exploration auto-use. Expose it as configuration if tuning requires it.
3. Write regression tests before changing behavior: low radiation clears; high radiation removes exactly half of max health; repeated uses remove fixed chunks; radiation never becomes negative; manual and exploration removal paths agree; and changing the shared threshold changes both chat and exploration decisions together.
4. Keep the existing health-bar contract: red radiation consumes visible healthy width and remains visible even at full health.
5. Recheck medical production against the changed RadAway demand, then run the full backend and frontend suites plus an end-to-end exploration flow.

## Decisions still needed

1. Should passive decay exist, or should only RadAway remove radiation? Recommendation: RadAway only, so the system retains a meaningful inventory decision.
2. Should water shortage become a separate vault-wide radiation source? It is not part of the implemented system today.
3. Is a direct-use audit event needed, so player-initiated use can be distinguished from a chat recommendation or exploration auto-use?

## Non-goals

- No new rooms, crafting recipes, or ghoul-immunity mechanics.
- No API shape change for `use_radaway`.
- No replacement of the current threshold-death model with effective-max-health damage without a dedicated design decision.
