# World Map — Multiplayer-First Architecture

The wasteland map is the game's multiplayer surface: one deterministic world that every player explores with
their own fog of war. It supports the Wasteland Journal today and can later host asynchronous raiding,
cross-vault encounters, visits, and leaderboards.

> Related feature: [The Wasteland Journal](WASTELAND_JOURNAL.md). Delivery sequencing, status, and phase
> implementation contracts live in the [World Map delivery plan](../WORLD_MAP_PLAN.md).

## Shared-world model

The map uses a deterministic coordinate engine, not a per-player drawing:

| Utility | Behaviour |
|---|---|
| `schematic_coords(name)` | `sha256(place name) → (x,y)` in the 10.0–89.9 band. The same normalized name always lands in the same place. |
| `collision_nudge(base, occupied)` | Deterministic spiral resolution for coordinate conflicts within a vault's persisted map state. |
| `seeded_vault_specs(...)` | A fixed, viewer-independent roster of temporary neighbor-vault signals. |
| frontend `wastelandTerrain.ts` | Fixed-seed procedural terrain, identical for every viewer. |

Persistence stays on a 0–100 grid (`WastelandLocation.coord_x/y`, DB check-constrained); the map API scales
it with `WORLD_SCALE = 1.6` to the 0–160 render world (`MAP_SIZE = 160`).

Place rows are scoped to `vault_id`, which gives every vault independent discovery and unlock state. A place
name resolves to the same shared base coordinate for every vault. Until Phase D introduces a global location
registry, a vault-local `collision_nudge` can move an overlapping persisted marker differently in each vault;
the current map is therefore a shared-base-coordinate schematic with per-player fog, not yet an exact global
marker registry.

## Invariants

1. **One deterministic base world, per-player fog.** Base coordinates derive from names. Per-player discovery,
   unlock state, and collision resolution belong to vault-scoped state until a global registry exists.
2. **Async multiplayer.** A raid resolves against a snapshot, never a live vault simulation. The offline game
   loop makes live shared-world authority incompatible with this architecture.
3. **`Vault.number` is global identity.** A real vault's world marker derives from its number, never from the
   viewer's identity.
4. **Names are coordinate authority.** Future denormalization deduplicates normalized names, not stored
   coordinates.

## Vault signals

Temporary neighbor signals come from one fixed global roster. Each signal's coordinate derives from its target
vault number, with deterministic collision handling, so a given signal stays in the same place for every
viewer. A viewer's own vault remains a separate home marker during the Journal stage.

When real raid targets are introduced, a real vault marker replaces the matching temporary signal without
moving it. A temporary signal is visual scaffolding only: it is not an authority for a target, raid result, or
private vault data.

## Multiplayer surface

| Feature | Map role |
|---|---|
| Wasteland Journal | Explorer route, loot, discoveries, and map deep-links for one vault. |
| Async raiding | Vault markers become targets for snapshot-based raid expeditions. |
| Fallen dwellers | Deterministic encounters can reuse an eligible fallen dweller as an enemy. |
| Vault visits | Friends can view a permissioned, read-only vault snapshot. |
| Leaderboards | Aggregate discoveries, population, and raid results can be ranked safely. |

## Boundaries

- No live shared-world simulation.
- No global location registry until cross-vault queries justify one.
- No map-driven changes to exploration reward or combat mechanics.
