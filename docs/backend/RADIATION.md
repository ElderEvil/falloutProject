# Radiation Mechanics

This document is the backend contract for dweller radiation, radiation-reduced health, and medical supplies. Balance
values belong in `app/core/game_config.py`; services own the rules; routers only authorize, delegate, and map errors.

## Current model

`Dweller.radiation` is an integer from zero through the configured hard cap (`HealthConfig.max_radiation`, currently
1,000). Radiation reduces the health ceiling without directly setting health to zero:

```text
effective_max_health = max(1, max_health - radiation)
```

Any health restoration must cap at `effective_max_health`. Any radiation gain must cap at `max_radiation` and pull
health down to the new effective ceiling. Radiation death remains a separate game-loop rule using
`DeathConfig.radiation_death_threshold`.

## Single source of truth

`app/services/radiation_service.py` contains the shared pure helpers:

- `apply_radiation_gain(dweller, amount)` applies the configured cap and effective-health clamp.
- `radiation_removal_amount(radiation)` calculates one RadAway's removal as the configured share of current
  radiation, with a minimum removal of one and no negative result.

Callers persist the changed model; the helpers do not commit or own a session. Exploration events, Radscorpion
incidents, dehydration, and medical treatment must use these helpers rather than duplicate caps or percentages.

## Configured rules

`HealthConfig` owns radiation and treatment values:

| Setting | Meaning |
| --- | --- |
| `max_radiation` | Per-dweller radiation cap. |
| `dehydration_radiation_per_tick` | Radiation added to in-vault dwellers per game-loop tick while water is empty. |
| `radaway_removal_percent` | Fraction of current radiation removed by one RadAway; at least one point is removed. |
| `radaway_auto_use_threshold` | Raw radiation level above which an explorer may auto-use a RadAway. |
| `stimpack_heal_percent` | Fraction of base maximum health restored by one Stimpack. |

`HappinessConfig.radiation_penalty_threshold` and `radiation_penalty` own the happiness effect. Death thresholds
remain in `DeathConfig`; do not introduce another radiation threshold in a service.

## Treatment paths

Manual `use_stimpack` and `use_radaway` operations live in `medical_service`. They consume carried supplies only,
reject unavailable supplies, and map no-change operations to `ContentNoChangeException`. The dweller endpoint checks
ownership through the shared dependency and delegates to the service.

Exploration carries its own medical counters. Its auto-treatment path uses the same configured Stimpack healing and
RadAway removal rules, then records the actual result in the exploration event stream.

## Game-loop ordering

For each vault tick, resource processing happens before dweller processing. When water is empty, dehydration
radiation scales with elapsed game-loop ticks and excludes dwellers away in exploration or quests. The dweller pass
then checks health and radiation death conditions in the same tick, so reaching the configured radiation threshold
cannot wait for a later tick.

## Persistence and concurrency

Radiation helpers are intentionally session-free so raw SQLAlchemy task sessions can call the same rules as API
services. CRUD used by Dramatiq actors must continue to use `execute(...).scalars()` unless the session factory is
explicitly SQLModel-aware.

Medical consumption is currently a read/validate/update sequence. The planned row-locking change must make it one
transactional operation with `SELECT ... FOR UPDATE` on PostgreSQL, preserving the existing exception contract and
adding a real concurrent-consumer regression test. SQLite's serialized test fixture cannot prove that guarantee.

## Regression contract

Changes to radiation rules should cover:

1. cap and effective-health clamping for every radiation source;
2. RadAway minimum removal and no-radiation no-op behavior;
3. Stimpack healing against the radiation-reduced ceiling;
4. dehydration scaling by elapsed ticks and exemptions for away dwellers;
5. configurable happiness penalty and same-tick radiation death;
6. visible API/UI health values and progression feedback for player-facing medical actions.

Future work such as Rad-X must define its state lifecycle and interaction with these invariants before implementation.
