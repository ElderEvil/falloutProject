# World Map — Style References

Saved visual targets for future map styling work. These are **look targets only** — data contracts
(terrain snapshot, road mask, `place_groups` taxonomy) are unaffected. Both references were provided
by the maintainer (Oct 2026); the original images are not stored in-repo, descriptions below are
written so the look can be reproduced without them.

Delivery status and sequencing are **not** tracked here — this file records look targets only. For
what is actually shipped, in progress, or planned, see the delivery plan
([`../WORLD_MAP_PLAN.md`](../WORLD_MAP_PLAN.md)) and the location taxonomy audit
([`../features/LOCATION_KINDS_AUDIT.md`](../features/LOCATION_KINDS_AUDIT.md)). Work referenced below
may live on unmerged feature branches rather than the current checkout.

## Reference A — Fallout 1/2 overworld (color)

Dark olive/brown landmass on near-black, with a dense tan road web (node ticks at junctions),
a horizontal blue river band, and glowing color-coded circular location icons:

- green vault/cave circles, orange/red danger skulls, blue water drops, gold city markers,
  red tents, white/grey minor markers, bone piles.
- Full-bleed map, minimal chrome; region labels only.

## Reference B — RobCo Termlink Protocol map (monochrome ASCII)

Black background, single-accent (white/green) line-art. Everything is glyph-drawn:

- Forest = small tree glyphs (`♣`-like clusters), hills = `^^^` strokes, water = `~` waves,
  road = `=` double line, dirt road = dotted line, ruins = square outline, major location =
  building glyph, vault = gear/cog emblem, radio tower = tower glyph.
- Right rail: `BIOME LEGEND:` with one glyph row per entry (`= Forest`, `= Hills`, `= Road`,
  `= Road (dirt)`, `= Water`, `= Ruins/Buildings`, `= Major Location`, `= Vault`,
  `= Radio Tower`), plus a `N/W/E/S` cross compass below it.
- Top: `ROBCO INDUSTRIES (TM) TERMLINK PROTOCOL` header with date/time, tab bar
  `[ MAP ] [ DATA ] [ INVENTORY ] [ QUESTS ] [ RADIO ]` (active tab inverted).
- Bottom: `[ COMMONWEALTH REGION ]` left, `SCALE: 1:25000` + `0–5 km` tick bar right.
- Thin double-rule frame around the map pane.

How it maps to our stack when we get there:

- Glyphs per terrain tile → extend `AtlasTerrain` canvas painting (currently per-tile fills)
  or an SVG `<text>`/`<path>` overlay driven by the same snapshot grid; legend entries map
  1:1 onto the existing `MapLegend` TERRAIN section.
- Compass → reuse `map/utils/bearing.ts` math; scale bar derives from `MAP_UNITS = 160`
  and the snapshot tile size.
- Monochrome fits the CRT theme: implement as a theme variant (single accent token), not a
  parallel component set. Keep the existing marker/legend components and swap their
  presentation via tokens + the legend model.
- Tab bar / region footer are chrome: build only if a full terminal-screen map view is
  scoped; otherwise take the glyph + legend + compass language alone.

## Non-goals for both references

- No wire-contract, snapshot-schema, or generation changes come from styling alone.
- New location kinds (tents, bones, raider/water groups) still go through `place_groups.json`
  + seeds per `LOCATION_KINDS_AUDIT.md`, not through style work.
