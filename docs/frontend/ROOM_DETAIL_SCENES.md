# Empty room detail scenes (#819)

The maintainer chose a harsh industrial Arena. Its empty floor leaves two independent
actor positions; no painted occupants, weapons, hazards or combat effects are present.
Animation and actor rendering stay with #818.

## Asset contract

`frontend/public/assets/room-scenes/manifest.json` records role, stable catalog key,
source/workflow, actual encoding/dimensions, camera, floor baseline, normalized actor
anchors and responsive placement. Built-in image generation exposes no exact model,
seed or cost; those fields are marked unknown instead of invented. The delivered WebP
is 1536×1024, opaque, encoded with cwebp quality 82 (approximately 356 KiB).

KISS/YAGNI: a frontend catalog mapping is sufficient. No persisted field, migration or
new backend API is needed. Arena tiers 1–3 each map to their own curated scene; an unknown
tier/catalog key falls back to the existing backend grid sprite. The three scenes track a
real progression (duel pit → reinforced brawl floor → creature-containment arena) matching
the modes each tier unlocks.

`useRoomProduction` resolves detail versus grid roles once for the room modal. Ordinary
previews and Arena receive the resolved URL; incident views receive it and the grid
fallback separately. Image load failures try the grid sprite once, then show the existing
empty placeholder (preview) or no backdrop (incident). Changed URLs reset failed-image
state. Grid cells resolve the curated scene, fall back to their configured grid sprite
when it fails to load, and hide the image when both fail.

The standard detail preview uses contain behavior, preserving both anchors at (0.35, 0.8)
and (0.65, 0.8); size-6 previews use a 3:1 cover frame shared with the Overseer's Office.
Incident status overlays remain independent and contain the backdrop at low opacity for
legibility. Arena's room-part precedence remains unchanged: the combat panel is its primary
detail even during an incident.

## Browser evidence

Real RoomDetailModal + ArenaRoomDetail rendered in Chromium with fixture state:

| Viewport | Loaded image bounds | Result |
|---|---|---|
| 1440×1000 | 978×652 | complete frame, contained within modal; body scroll available |
| 390×844 | 344×229 | complete frame, contained within viewport |

Both loaded the 1536×1024 WebP successfully; no page errors occurred. This is layout
verification with fixture data, not a production usability study. Screenshot evidence:
[wide](reviews/arena-wide.webp), [narrow](reviews/arena-narrow.webp).

Unit checks validate WebP signature/dimensions, catalog/tier selection, load-error fallback
and reset, and existing room/Arena/incident behavior. The manifest convention follows #817
without recovering the discarded #850 actor prototype or choosing a broader art pipeline.
