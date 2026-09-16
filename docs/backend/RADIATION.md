# Radiation Mechanics

Backend contract for dweller radiation, radiation-reduced health, and medical supplies. Balance values live in
`app/core/game_config.py`; services own the rules; routers only authorize, delegate, and map errors. Game-domain
invariants that must not drift are recorded in `docs/backend/GAME_MECHANICS.md`.

## Current model

`Dweller.radiation` is an integer that **saturates at the dweller's own `max_health`** — there is no flat cap. That
keeps the bar proportional to the dweller instead of overflowing past the health pool:

```text
effective_max_health = max(1, max_health - radiation)
```

Radiation reduces the health ceiling; it never sets health to zero. **Radiation cannot kill**: a saturated dweller
sits at 1 HP and only dies from damage (incidents, exploration, combat). Any health restoration must cap at
`effective_max_health`, and any radiation gain pulls health down to the new ceiling.

## Sources

Radiation is either **external** or **ingested**, and that distinction decides whether outfits help.

| Source | Kind | Outfit resistance |
| --- | --- | --- |
| Wasteland danger events — `radiation_gain = max(2, 12 - endurance)` | external | applies |
| Radscorpion incident damage | external | applies |
| Irradiated water drunk while the vault has no water | ingested | **none** — the radiation enters by drinking |

Ghouls are immune to every source. Outfit resistance is name-derived (`OUTFIT_RADIATION_RESIST_BY_TYPE` /
`OUTFIT_RADIATION_RESIST_BY_NAME`): power armor blocks 75%, rare/legendary 25%, tiered suits 10%, and hazmat names
block everything.

## Drought — irradiated water

While a vault has no water, in-vault dwellers accumulate `dehydration_percent_per_tick` of their max health **per
elapsed game-loop tick**, after `dehydration_grace_ticks` of quiet:

- only ticks past the grace boundary radiate, so a catch-up interval spanning the boundary credits just the overlap
  (never the whole window);
- the rate scales with elapsed ticks and saturates at `max_health`;
- dwellers `EXPLORING` or `QUESTING` are exempt — they carry their own supplies and settle on return;
- `GameState.water_empty_since` drives the grace clock and is cleared as soon as water returns;
- `dehydration_radiation_per_tick` is the master switch: setting it to 0 disables the whole effect.

## Single source of truth

`app/services/radiation_service.py` holds session-free helpers:

- `apply_radiation_gain(dweller, amount, *, resisted_by_outfit=True)` — caps at `max_health`, pulls health to the new
  ceiling, and returns whether anything changed. Ingested radiation passes `resisted_by_outfit=False`.
- `radiation_removal_amount(radiation, max_health)` — one RadAway's removal as the configured share of **max health**
  (not of current radiation), at least one point, never more than the dweller has.
- `outfit_radiation_resist(outfit)` / `dehydration_rads(max_health, ticks)` — pure lookups and rate math.

The helpers own no session and never commit; callers persist the dweller. Radiation has **no passive decay** — only
RadAway removes it, which keeps inventory a real decision.

## Configured rules

| Setting | Meaning |
| --- | --- |
| `dehydration_radiation_per_tick` | Master switch for drought radiation (0 disables it). |
| `dehydration_percent_per_tick` | Share of max health gained per post-grace drought tick. |
| `dehydration_grace_ticks` | Quiet ticks at zero water before radiation starts. |
| `recovery_radaways_per_dweller` | RadAway used per dweller by the one-shot recovery action. |
| `recovery_stimpaks_per_dweller` | Stimpack used per dweller by the one-shot recovery action. |
| `radaway_removal_percent` | Share of max health one RadAway clears (at least one point). |
| `radaway_auto_use_threshold` | Radiation level above which an explorer may auto-use a RadAway. |
| `stimpack_heal_percent` | Share of max health one Stimpack restores. |

`HappinessConfig.radiation_penalty_threshold` / `radiation_penalty` own the happiness effect. There is no radiation
death threshold — do not reintroduce one in a service.

## Treatment paths

- **Manual** — `medical_service.use_radaway` / `use_stimpack` spend carried supplies, reject unavailable supplies, and
  map no-change operations to `ContentNoChangeException`.
- **Exploration** — an explorer carries its own counters, auto-uses a RadAway above the configured threshold, and
  records the actual result in its event stream.
- **One-shot vault recovery** — `POST /storage/vault/{vault_id}/medical/distribute-recovery-supplies` treats every
  irradiated in-vault dweller with one RadAway **then** one Stimpack from vault storage. Order matters: RadAway raises
  the radiation-reduced ceiling before the Stimpack heals into it, so a dose is never wasted. It skips dead,
  soft-deleted, exploring and questing dwellers, locks the storage row (`get_by_vault_for_update`) so concurrent
  requests cannot double-spend stock, and reports dwellers treated, supplies used, and remaining stock. The happiness
  board surfaces it as **Treat Irradiated Dwellers**.

## API contract

`effective_max_health` is part of the wire shape, not just a server-side helper: `DwellerRead` (and everything built on
it — full, with-room, with-vault responses) and the compact `DwellerReadLess` list shape both serialize the computed
`max(1, max_health - radiation)` value. Clients render health as `health / effective_max_health (max_health)` and must
never compute the ceiling locally — the server's radiation state is authoritative after every heal, RadAway, radiation
gain, and game-loop tick. The chat prompt shows radiation as `radiation / max_health`, which stays proportional because
radiation saturates at max health.

## Game-loop ordering

Within a vault tick, resource processing runs before dweller processing, so `vault.water` (and the `water_empty_since`
clock) are current when the dweller pass decides whether to irradiate. That pass applies drought radiation and then
checks `health <= 0` death; there is no radiation death check.

## Persistence and concurrency

Radiation helpers are session-free so raw SQLAlchemy task sessions can call the same rules as API services. CRUD used
by Dramatiq actors must keep using `execute(...).scalars()` unless the session factory is explicitly SQLModel-aware.

Medical consumption is one transactional operation: `use_stimpack` / `use_radaway` read the dweller with
`SELECT ... FOR UPDATE` (`dweller_crud.get_for_update`), so concurrent requests serialize on the row instead of
spending the same supply twice. The recovery action takes the equivalent lock on vault storage.
`test_medical_concurrency.py` proves the dweller guarantee against live PostgreSQL (`@pytest.mark.integration`; SQLite
serializes every write and cannot prove locking).

## Regression contract

Changes to radiation rules should cover:

1. saturation at each dweller's own `max_health`, and effective-health clamping for every source;
2. outfit resistance for external sources and its deliberate bypass for ingested water;
3. drought grace, the post-grace tick overlap on catch-up, and exemptions for away dwellers;
4. RadAway minimum removal, max-health-relative chunking, and no-radiation no-op behavior;
5. Stimpack healing against the radiation-reduced ceiling;
6. recovery-action ordering, stock limits, and soft-deleted/away exclusions;
7. visible API values and progression feedback for player-facing medical actions.

## Future work

Rad-X (a distinct temporary radiation-resistance treatment), the RadAway economy check against Medbay output, and the
dweller assignment policy on the update path are tracked in `docs/ROADMAP.md`. Rad-X must define its state lifecycle
and its interaction with these invariants before implementation.
