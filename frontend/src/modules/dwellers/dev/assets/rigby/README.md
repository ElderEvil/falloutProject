# Rigby2D dweller study

Preview: `/dev/dweller-motion-lab` (development only, no login or backend required).
Branch: `feat/dweller-rigby-study`. Start from `frontend/` with:

```sh
pnpm install --frozen-lockfile
pnpm exec vp dev --port 5174 --strictPort
```

The existing generated API types are used; no backend contracts changed.

## Artwork

The three PNG pages are byte-for-byte copies from the user's
`/home/elder/Downloads/fallout-asset-batch/Item/` directory. Regions are read at runtime from the
original pages, with coordinates in `../../models/rigbyStudy.ts`. No extracted/repainted PNGs.

| Local page      | Original filename                                         | SHA-256                                                          |
| --------------- | --------------------------------------------------------- | ---------------------------------------------------------------- |
| outfits.png     | Mobile - Fallout Shelter - Items - Male Outfits.png       | 6512282686049253ee024121f0d6f8e329064a3e65cfa0c732f392f0e8b8a875 |
| accessories.png | Mobile - Fallout Shelter - Items - Outfit Accessories.png | a21934bedb21372637a6dc049024161db2ce8dc585c2118a13900af7394c75ac |
| weapons.png     | Mobile - Fallout Shelter - Items - Weapons and Items.png  | 5e1673111962eefef52f85f7941a222cf3429be5ba70afa9f712a8e75fa4cffe |

`../chet-head.webp` is the existing experimental cutout of Chet. See its adjacent README for source
and extraction details. `front-head.svg` and `side-head.svg` are new provisional vector drawings,
not source Fallout sprites. View labels and the preview footer disclose that distinction.

## What is exercised

- The real Rigby2D v0.3.0 runtime, pinned in `frontend/vendor/rigby2d` with upstream licenses.
- Seventeen bones, separate draw-order slots, two outfit skins, two hats, and two weapons.
- Three projected view setups and human/bulky proportion profiles using identical clip definitions.
- Idle/walk/attack, pause, scrub, speed, mirroring, joint overlay, and 36 independently posed actors.
- Skin swapping without changing the current pose or animation phase.
- JSON serialization and parsing through the actual runtime, including on the Reload button.
- CPU update/draw-submission measurements. These are **not GPU time or an FPS guarantee**.
- Pausing animation when the document is hidden; reduced-motion users start with playback paused.

## Limits and export

This is an equipment/runtime feasibility study, not production animation. Front/side torso art is
foreshortened from the same three-quarter atlas. The bulky profile is a fitting test, not finished
super-mutant artwork. There is no foot planting or character locomotion, and joint overlaps need an
animation/art polish pass. Hair visibility for arbitrary hats is not solved.

The rifle support hand uses a small analytic two-joint correction in the preview. Weapon holding and
grip correction are application pose adjustments, not baked into the exported clips. The exported
JSON contains base setup, outfit skins, equipment attachments, and authored idle/walk/attack keys.

Export Rig JSON and Atlas separately. Place them alongside `outfits.png`, `accessories.png`,
`weapons.png`, `front-head.svg`, `side-head.svg`, and `../chet-head.webp` (copy the latter into the
export folder). Runtime JSON round-trip is tested. Importing/editing the complete bundle in the
external Rigby2D editor, including SVG image support, is **not yet verified**.

The dev route gates imports, so the vendor runtime and these large texture pages are not included
in production builds. No game equipment state, portraits, backend data, or combat playback is changed.
