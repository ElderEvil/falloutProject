# Rigby2D dweller study

Preview: `/dev/dweller-motion-lab` (development only, no login or backend required).
Branch: `feat/rigby2d-quarter-view`. Start from `frontend/` with:

```sh
pnpm install --frozen-lockfile
pnpm exec vp dev --port 5174 --strictPort
```

The existing generated API types are used; no backend contracts changed.

## Artwork

The four PNG pages are byte-for-byte copies from the user's
`/home/elder/Downloads/fallout-asset-batch/Item/` directory. Regions are read at runtime from the
original pages, with coordinates in `../../models/rigbyStudy.ts`. No extracted/repainted PNGs.

| Local page         | Original filename                                         | SHA-256                                                          |
| ------------------ | --------------------------------------------------------- | ---------------------------------------------------------------- |
| outfits.png        | Mobile - Fallout Shelter - Items - Male Outfits.png       | 6512282686049253ee024121f0d6f8e329064a3e65cfa0c732f392f0e8b8a875 |
| outfits-female.png | Mobile - Fallout Shelter - Items - Female Outfits.png     | af363a80dd9caf5704910caee7bb0a2bd46b04995dcad39774deb107113710c2 |
| accessories.png    | Mobile - Fallout Shelter - Items - Outfit Accessories.png | a21934bedb21372637a6dc049024161db2ce8dc585c2118a13900af7394c75ac |
| weapons.png        | Mobile - Fallout Shelter - Items - Weapons and Items.png  | 5e1673111962eefef52f85f7941a222cf3429be5ba70afa9f712a8e75fa4cffe |

`../chet-head.webp` is the existing experimental cutout of Chet. See its adjacent README for source
and extraction details. `../amata-head.png` is cropped from Amata's legendary-dweller card in
`/home/elder/Downloads/fallout-asset-batch/fos_legendary.png` (SHA-256
`f443dcd5ba8714c2d579478841eb205765248fa1a0d251f82227e5a8b26eb522`); the crop keeps the head and
neck and stops above the Vault 101 collar.

## What is exercised

- The real Rigby2D v0.3.0 runtime, pinned in `frontend/vendor/rigby2d` with upstream licenses.
- Seventeen bones, separate draw-order slots, two outfit skins, two hats, and two weapons.
- A single three-quarter view setup with male and female (Amata) proportion profiles using identical clip definitions.
- Idle/walk/attack, pause, scrub, speed, mirroring, joint overlay, and 36 independently posed actors.
- Skin swapping without changing the current pose or animation phase.
- JSON serialization and parsing through the actual runtime, including on the Reload button.
- CPU update/draw-submission measurements. These are **not GPU time or an FPS guarantee**.
- Pausing animation when the document is hidden; reduced-motion users start with playback paused.

## Limits and export

This is an equipment/runtime feasibility study, not production animation. The female profile uses
Amata's cutout and the female Vault 101 parts; other female outfits are not wired yet. There is no
foot planting or character locomotion, and joint overlaps need an animation/art polish pass. Hair
visibility for arbitrary hats is not solved.

The rifle support hand uses a small analytic two-joint correction in the preview. Weapon holding and
grip correction are application pose adjustments, not baked into the exported clips. The exported
JSON contains base setup, outfit skins, equipment attachments, and authored idle/walk/attack keys.

Export Rig JSON and Atlas separately. Place them alongside `outfits.png`, `outfits-female.png`,
`accessories.png`, `weapons.png`, and the matching head cutout (`../chet-head.webp` or
`../amata-head.png`; copy it into the export folder). Runtime JSON
round-trip is tested. Importing/editing the complete bundle in the external Rigby2D editor is **not
yet verified**.

The dev route gates imports, so the vendor runtime and these large texture pages are not included
in production builds. No game equipment state, portraits, backend data, or combat playback is changed.
