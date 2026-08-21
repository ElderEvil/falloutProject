# The Wasteland Journal

The Wasteland Journal makes an exploration legible as a journey: what an explorer found, what happened to
them, and where discoveries sit in the wasteland. It is the per-vault, per-explorer layer of the World Map.

> Related feature: [World Map — Multiplayer-First](WORLD_MAP.md). Delivery status and future work live in
> [World Map delivery plan](../WORLD_MAP_PLAN.md).

## Player experience

### Journey record

An explorer's detail view presents a chronological event log alongside the rewards collected during the
expedition. Loot is shown by item and rarity rather than only as a counter. The current health journey is
shown as total damage, total healing, and a cumulative health-change trail.

The health trail is intentionally a record of changes, not an invented reconstruction of absolute historic
health. Radiation is not charted until exploration events persist radiation deltas.

### Discovery to map

Every newly discovered location is added to the vault's map and its journal event provides a **View on map**
action. The link opens that location's map detail for the same vault.

The map draws a dashed route for an exploration when it has at least two recorded discoveries. Routes use the
event order, so revisiting a known location remains part of the journey instead of being erased by the map's
de-duplicated place marker.

Older events that lack map metadata remain valid journal entries and markers; they simply do not produce route
points.

### Consistent exploration progress

All exploration surfaces use the same elapsed-time calculation and time-zone-safe start-time parsing. A
progress bar and remaining-time display therefore agree between explorer cards, the active list, and the
detail view.

## Boundaries

- The Journal does not change exploration combat, reward, or encounter probabilities.
- It is per-vault history; it neither exposes another player's exploration record nor creates live multiplayer
  behavior.
- A route is a visual journal trail, not a movement simulation or a navigation path.
- Map coordinates remain deterministic and are governed by the World Map feature contract.
