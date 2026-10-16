# Room scene motion study (draft)

Open `/dev/room-motion/index.html` on the frontend server. The preview uses existing
Arena tier-1 and Response Station size-3 art with lightweight CSS/SVG overlays.
Management blocks are layout sketches. No live room components or game state change.

Implemented examples:

- Arena: soft lamp variation, four drifting dust motes, and slow fan shadows masked
  to the openings behind the fixed vent grille.
- Response Station: a radar beam anchored to the painted display's baseline, sweeping
  back and forth within its upper semicircle, plus a restrained console glow.
- Pause and reduced-motion support, plus selectable loading/missing-art layouts.

## Ideas by existing artwork

These are proposals, not implemented effects. Upgrade tiers and merged sizes are
separate axes: Arena artwork is selected by tier; Response Station artwork by size.

| Room / artwork | Cheap ambient effects to try | Effects driven by actual game events |
| --- | --- | --- |
| Arena tier 1 | Current fan, sparse dust under lamps, slow warm light variation | A short lamp accent at match start; bell movement only after isolating its artwork |
| Arena tier 2 | Reposition fan to its new grille; faint booth light and steady floodlight glow | A scoreboard highlight when the round changes; display numbers only from real match state |
| Arena tier 3 | Low CRT glow on the RobCo console; restrained containment lamp highlights | A brief containment-beacon pulse when a hunt starts, never a permanent alarm |
| Response size 3 | Current semicircular radar sweep and console glow | A brief dispatch-console highlight when responders leave or return |
| Response size 6 | Re-anchor radar to the left console; tiny monitor-bar variation on the right | A short decontamination shower effect only if gameplay later exposes a matching state |
| Response size 9 | Re-anchor radar and monitor effects; stagger a few equipment indicators | Separate fire/hazmat dispatch cues based on real assignments, without lighting every station |

Start with one signature movement and at most one supporting effect per scene.
More floor space does not mean more particles or faster animation. Avoid idle
beacons that imply an emergency, changing drawn scoreboard digits arbitrarily,
whole-image zoom/shake, moving fixed grilles, and permanent steam obscuring actors.

## Placement and reuse

- Both rooms already use `RoomPreviewSection.vue`. Extend it for real image loading,
  fallback and missing-art states; do not introduce a second generic scene wrapper.
- Keep management below the scene. Existing scene assignment affordances should stay
  recognizable until an intentional replacement is designed.
- Reuse an effect only after two real scenes need it. No plugin registry, animation
  engine, polling, runtime generation, or speculative actor system for this pass.
- Overlays need coordinates/masks per exact image, ideally keyed alongside the scene
  metadata in `roomScenes.ts`. Never select geometry from room size alone: each
  illustration moves the console, vent, and lamps.
- Use the image's native coordinate space (`viewBox`) so art and effects scale
  together. Preserve its full aspect ratio: current Arena scenes and Response size 9
  are 3:1; Response size 6 is 2:1; Response size 3 is square. Do not crop the floor.
- Keep floors/actor anchors clear and decorative overlays noninteractive and hidden
  from assistive technology. Effects must not cover focus rings or management controls.

## Before production integration

- Review each tier/size at desktop and narrow widths, especially both sweep endpoints
  and the spaces between grille bars. Current prototype geometry covers only two images.
- Pause when offscreen or the document is hidden; honor the user's visual-effects
  preference and reduced motion. No rapid flashes or high-contrast flicker.
- Prefer `transform`/`opacity` on a few small elements. Avoid animating large blurs,
  shadows, filters, or background pixels. Profile on a lower-powered device.
- Replace the simulated loading/missing-art selector with actual image lifecycle
  handling; management should stay available when art fails.
- This standalone HTML lives under `public/`, so Vite includes it in production
  builds. Move the accepted study into the existing dev-only asset gallery (or remove
  the standalone page) before marking a production implementation ready.

## Validation

Browser inspection covered image loading, aligned radar/fan placement, pause,
reduced-motion fallback and both simulated scene states. No asset-preview unit tests
were added. Gameplay components are untouched; production integration remains future
work. The rejected ComfyUI workflow/output stays outside this PR in the local ComfyUI
output directory; the draft contains no generated animation asset.
