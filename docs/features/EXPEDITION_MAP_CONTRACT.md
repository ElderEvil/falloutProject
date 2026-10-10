# Expedition Map — Decisions and Visibility Contract

> **Status:** proposal / contract draft. No production code, schema, or API changes are
> authorized by this document. It supersedes the cross-cutting statements in
> [`MAP.md`](MAP.md) (§Fog-of-war contract) and [`TILE_MAP_INTEGRATION.md`](TILE_MAP_INTEGRATION.md)
> (§D4, §D5) where they disagree; those documents now point here.
>
> One document by request: it merges the `isVisible()` predicate specification with the
> road/ETA decision record and the delivery plan, so the contract is written before any
> implementation.

## Why this exists

The map makes two incompatible promises today:

- **Production terrain is decorative.** Nothing the player sees is derived from it.
- **Prototype terrain is simulated.** It determines travel cost, routing, and ETAs.

Two surfaces, two promises. The resolution is not "pick one" — it is to make the map an
**expedition-planning surface** in which geography becomes authoritative *gradually*, and
to hold a single rule while it does:

> **Terrain is decorative until the first player-facing number is derived from it.**
> The moment an ETA is shown, geography is a simulation claim and must be truthful.

Everything below follows from that rule. The target questions the map must eventually
answer are: *where should I send someone, why there, and what makes this journey
different?* That needs travel time, location purpose, discovery, and a few meaningful
route tradeoffs — not tactical movement or a game engine.

## Direction decisions

### DD1 — Expedition-planning surface, gradually authoritative geography

Adopt the planning surface as the product direction. Introduce authoritative geography in
increments, gated by the terrain rule above and by the integration boundary in `MAP.md`
Phase 5. No silent substitution of the tile world for the registry.

### DD2 — One player-facing ETA

The planning UI shows **exactly one** travel estimate. Showing both "prototype ETA" and
"production ETA" is a **developer-diagnostics-only** affordance and must be labelled as
such. This reverses `TILE_MAP_INTEGRATION.md` D4's "display both labeled" as a player
behavior.

- Production dispatch (`dispatch_travel_hours`) is authoritative once integration lands.
- The prototype ETA is illustrative until parity is proven.
- A **scout** ETA is a separate, explicitly approximate estimate (see DD4); it is not a
  second number for a known destination.

### DD3 — Roads must mean something, but not only speed

A prominent road network that confers no benefit is a **lying affordance** — worse than no
roads. Current prototype `findPath()` uses terrain costs only (`astar(..., TRAVEL_COST)`,
`worldgen.ts`), so roads are visually load-bearing but mechanically inert.

- **v1 experiment:** a road travel discount (~0.7× on road tiles), matching the proposal
  parked in `DECISIONS.md`.
- **Acceptance:** the discount must change the *chosen destination or route* in a
  meaningful fraction of representative cases. If it only changes the number slightly,
  roads are decoration: restyle them as background texture and stop calling them a network.
- **Deferred:** roads as faster-but-more-exposed vs slower wilderness. Do not add the
  exposure/risk system yet.
- **Dependency:** road semantics **gate the ETA freeze**. Changing road cost retunes every
  ETA, so decide DD3 before treating any ETA as stable.

### DD4 — Unknown territory needs an intentional action ("Scout this frontier")

Known-only routing is the right boundary, but players need a way past it. A scout
interaction selects a **revealed edge or broad unexplored sector** and returns an
**approximate duration**, never an exact hidden destination or hidden cost.

This is a **second targeting mode**, not a variant of destination routing. Define it
before the ETA contract hardens, or it will be bolted on badly.

### DD5 — Discoveries are additions to an atlas, not fog removal

On arrival: reveal a small patch of geography; introduce the location's name and
silhouette; show a discovery toast/card; add it to the location index and Journal.

**Mirror the existing production pattern** (unlock toast + Journal + notification bell per
`GAME_MECHANICS.md`, never bell-only). Do not invent a third discovery-surfacing pattern in
the prototype.

### DD6 — Visual direction: restrained CRT atlas

Quiet terrain, crisp water and roads, strong landmark silhouettes — chosen over a realistic
heightmap as the first player-facing treatment. A heightmap may improve hill readability
later; it is not the next milestone.

**Four-tier hierarchy** (three is not enough — this is where the locked-hint question
came from):

```
terrain / roads  <  unknown hint  <  known marker  <  home / selection
```

- Terrain differs by sparse textures/hatching as well as color.
- Roads, historical discovery trails, and the selected travel route use clearly different
  line styles.
- Labels appear primarily for home, selection, and hover/focus.
- Minor caches appear at closer zoom levels, not competing with major sites.
- Shape, outline, brightness, and line pattern carry information; color alone does not.

### DD7 — Prototype stays a de-risking surface

The prototype de-risks the geography and decision model; the **production map** owns the
player surface. Integrate only through the `MAP.md` Phase 5 mapping contract. Do not let
the prototype become the planning UI by default.

### DD8 — Projection is not compatibility

Projecting production coordinates onto the tile canvas is mathematically useful but does
**not** make the worlds geographically compatible. A real location can land on prototype
water or somewhere inconsistent with its category. The amber overlay is a **mapping
diagnostic**, not evidence the worlds fit. Resolving a conflict (terrain override vs
relocation) is a gameplay decision.

## Visibility contract — `isVisible()`

This is the single source of truth for "may the player see/interact with this?" It
replaces the ad-hoc visibility checks currently scattered through
`MapPrototypeView.vue` (rendering, selection, routing, ETA, hit-testing).

### Predicate

Two independent inputs, both per-vault:

- **Tile mask** — `explored[x, y]` for terrain, roads, and decorative geography.
- **Discovered marker IDs** — for landmarks, vaults, and sites (a marker is known because
  it was discovered, **not** because its icon touches a revealed cell).

```
isVisible(x, y)        → dev/showAll OR explored[x, y]
isMarkerVisible(id)    → dev/showAll OR id ∈ discoveredIds
```

There are exactly two mechanisms. Everything that needs visibility calls one of them; no
consumer re-derives it.

### Consumer obligations

| Consumer | Must do when not visible |
|---|---|
| Terrain / decor rendering | Not drawn. Clip roads/decor at the explored boundary. |
| Marker rendering | Not drawn. Icons must not overhang from a hidden cell into revealed space; clip or cull by marker visibility, not by paint order. |
| Selection / hit-testing | No-op. A hidden place must never become the selection. |
| Route origin | Origin must be a visible tile. A hidden vault cannot set the origin in player mode. |
| Route destination | Must be a discovered marker **and** a visible tile. |
| Pathfinding | Search **explored + traversable** cells only. A known destination must not yield a route through unknown cells. If none exists: "No known route". |
| ETA | Derived from the same constrained path. No full-world cost. No number when the route is not known. |
| Detail panel | Discovered markers only. |
| Index / lists | Discovered markers only. |
| Keyboard / touch / focus | Focus lands only on visible entries. A known-location list is the non-mouse access path. |
| Developer mode | `showAll` bypasses for diagnostics, clearly labelled as developer-only. |

### Invariants

- **One rule.** The fog overlay is presentation; it must never be the only thing enforcing
  visibility (an overlay that only paints opaque rectangles is insufficient).
- **No leak through geometry or cost.** Hidden route geometry and exact hidden travel costs
  are never rendered, returned, or hinted at.
- **Per-vault isolation.** Switching vaults must not reuse another vault's discoveries,
  selection, or cached visibility.
- **Dev/player split is explicit.** `playerPreview` gates the strict contract; developer
  diagnostics may expose the full world but must be labelled.

### Production vs prototype: two sanctioned presentations

Both preserve the invariant "unknown *identity* is never exposed":

- **Production map (chosen):** locked places render as **anonymous hint pins** — position
  shown, name/type/actions withheld (`marker-locked` style, no Dispatch). This is the
  "explicit projection" permitted by `MAP.md` §Phase 5.
- **Prototype player preview:** unknown places are **hidden entirely** until discovered.

The difference is intentional (the prototype tests discovery feel; production motivates
chat and expedition). It must be reconciled before there is a single player surface — see
Open questions.

## Verified implementation gaps

All verified against the current prototype. These are the contract violations DD1's rule
makes load-bearing; fix the predicate once and they collapse into it.

| Ref (`MapPrototypeView.vue`) | Gap |
|---|---|
| `:1096` (root cause) | Fog is a paint operation drawn after markers, so it culls nothing structurally. No shared visibility rule feeds selection, routing, ETA, or detail. |
| `:873` | `onCanvasClick` resolves vaults/locations from `world.value.*` before any visibility check: a hidden location becomes `selectedLocation`; a hidden vault sets `routeStart`. In `playerPreview`, destination is gated (`:908`) but origin is not. |
| `:905` | Player routing checks the destination is explored, but `findPath()` searches the full terrain, so a known destination can route through unknown cells and draw them. |
| `:682` | `selectedLocationEta` independently runs full-world `findPath()` from `world.origin`, with no preview/fog guard. |
| `:1200` | Canvas binds only mouse events; there is no known-location list or keyboard/touch selection path. |

## Delivery plan

1. **Wire `isVisible()` through every consumer** (rendering, selection, origin,
   destination, pathfinding, ETA, detail, lists, focus, hit-testing). Fixes the gaps above.
2. **Decide road semantics (DD3) and ETA authority (DD2)**, then freeze the ETA.
3. **Build one complete loop:** scout → discover → inspect → dispatch → revisit.
4. **Apply the restrained CRT atlas (DD6)** — three-to-four-tier hierarchy and
   zoom-dependent detail — as part of step 3's verification, not after it.
5. **Settle production geography/identity mapping** (`MAP.md` Phase 5) last.

Do **not** broaden the generator further before step 3. Proving that one small area
produces interesting expedition decisions tells you more about the right map than another
layer of cartography.

## Open questions

- **Single player surface:** anonymous hint pins (production) vs hidden-until-discovered
  (prototype)? Pick one before the surfaces merge.
- **Road benefit shape:** speed only, or speed-plus-exposure later? v1 assumes speed only.
- **Scout contract:** sector vs edge targeting; how approximate may the estimate be.
- **Regional identity:** a few recognizable patterns (industrial corridor, lake basin,
  ruined-town cluster, isolated hills) — uniform opportunity, varied kind — before
  increasing density.
- **ETA parity:** when the prototype ETA and `dispatch_travel_hours` diverge, which wins
  and how is the gap closed?

## Related

- [`MAP.md`](MAP.md) — Wasteland Atlas rendering/fog plan; this doc owns the cross-cutting
  visibility contract and the road/ETA decisions.
- [`TILE_MAP_INTEGRATION.md`](TILE_MAP_INTEGRATION.md) — prototype → production integration
  contract (D1–D7) and the sign-off gate.
- [`WORLD_MAP.md`](WORLD_MAP.md), [`WASTELAND_JOURNAL.md`](WASTELAND_JOURNAL.md),
  [`../backend/GAME_MECHANICS.md`](../backend/GAME_MECHANICS.md) — world identity, Journal
  trails, progression-surfacing rules.
- Prototype notes: `frontend/src/core/views/map-prototype/DECISIONS.md`.
