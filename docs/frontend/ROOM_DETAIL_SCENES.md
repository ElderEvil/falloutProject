# Empty room detail scenes (#819)

The Arena is a former Vault-Tec recreation room converted for wasteland combat training.
Three approved cartoon scenes show the same room progressing from a patched duel pit to
a reinforced spectator arena and then a creature-containment arena. Printed Vault Boy
sports posters, an announcer booth, Nuka-Cola signage and a RobCo console add Fallout
details. The fighting floor stays empty; animation and actor rendering stay with #818.

## Asset contract

The shared fire/radiation response room has three empty scenes in the same
illustrated vault style as the Arena. Footprints 3/6/9 use 724×724, 1448×724 and
2172×724 artwork respectively, with two/four/six equipment places and clear
foreground floors. The compact room has basic fire/hazmat gear; the wider rooms
add decontamination and storage. `response-bay-size-{3,6,9}-v1.webp` is resolved
by the `response` category and actual room size, falling back to `size_min` when
size is absent. Backend sprites use matching `response-bay-size-{3,6,9}.webp` files.
The manifest records all generation prompts and the built-in image tool source.
The proposed room name is Emergency Bay; the catalog name remains Response Station
until the naming decision is settled.

`frontend/public/assets/room-scenes/manifest.json` records role, stable catalog key,
source/workflow, actual encoding/dimensions, camera, floor baseline, normalized actor
anchors and responsive placement. Artwork was generated and edited through the OpenAI
Images API using `gpt-image-2.5-flare` at medium quality, then recomposed into wide scenes.
The manifest preserves both the lore-informed concept prompts and the wide-edit prompts.
Seed and cost were not recorded. The delivered WebPs are 2172×724 (3:1), opaque and encoded
with cwebp quality 82. Superseded non-wide concepts and the unused industrial scene are removed.

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
when it fails to load, and hide the image when both fail. The backend Arena fallback sprite
uses the approved wide Tier 1 artwork.

The standard detail preview uses contain behavior, preserving both anchors at (0.35, 0.8)
and (0.65, 0.8); size-6 previews use a 3:1 cover frame shared with the Overseer's Office.
The native 3:1 images fit that frame without cropping away the floor or rear-wall details.
Incident status overlays remain independent and contain the backdrop at low opacity for
legibility. Arena's room-part precedence remains unchanged: the combat panel is its primary
detail even during an incident.

Unit checks validate WebP signature/dimensions, the native 3:1 ratio, catalog/tier selection, load-error fallback
and reset, and existing room/Arena/incident behavior. The manifest convention follows #817
without recovering the discarded #850 actor prototype or choosing a broader art pipeline.
