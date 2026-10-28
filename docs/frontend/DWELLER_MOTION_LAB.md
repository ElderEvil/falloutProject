# Dweller motion lab — implementation and findings

Recorded 2026-10-28. This documents the separate Rigby2D feasibility prototype. The
[research and tool comparison](DWELLER_ANIMATION_RESEARCH.md) explains the selection and alternatives.

## Integration into the SVG rig branch

The prototype is also available in the main checkout on `feat/dweller-2d-rig`, at
`/dev/dweller-motion-lab` on the normal frontend server (typically port 5173). Both this lab and
`/dev/dweller-rig` appear in the `/dev` menu. The prototype files, original asset pages, pinned
runtime/licenses, and focused tests were copied from the source worktree's uncommitted state;
the source worktree was left untouched. No package or lockfile changes were needed.

The sections below retain the original study's location and validation history.

## Location and scope

| Item | Value |
| --- | --- |
| Documentation checkout | `/var/home/elder/Projects/falloutProject` (main worktree) |
| Prototype checkout | `/home/elder/.codex/worktrees/22b9/falloutProject` |
| Prototype branch | `feat/dweller-rigby-study` |
| Starting commit | `1a8dffd2` |
| Development route | `/dev/dweller-motion-lab` |
| Local preview | <http://localhost:5174/dev/dweller-motion-lab> while its server is running |

At handoff, prototype changes are uncommitted in the separate worktree. Its branch name alone will
not recover those files in another checkout. The main worktree's existing experiment and uncommitted
changes were preserved. Paths below refer to the prototype checkout unless stated otherwise.

The preview exercises real skeletal playback and interchangeable artwork. It has no backend dependency,
login requirement, shared server state, or production equipment/combat integration. The route sits
inside the router's `import.meta.env.DEV` block and supplies development-menu metadata.

## Result and decision

Modular 2D cutout animation is a practical starting point for these assets: the supplied atlases already
separate body parts, and a second outfit can use the same joints and animation keys. Prefer a shared
bone convention with view/body-specific fitting over independently animating every outfit.

The prototype demonstrates three view setups, two outfit skins, two proportion profiles, two weapons,
two hats, and three clips. It does **not** demonstrate finished front/side artwork, every humanoid type,
or an efficient external-editor workflow. Keep Rigby2D as the candidate until the editor round-trip and
one polished character pass; SkelForm remains the next alternative if authoring proves cumbersome.

## Code ownership

| Path under `frontend/` | Responsibility |
| --- | --- |
| `src/router/index.ts` | Development-only lazy route and menu entry. |
| `src/modules/dwellers/dev/models/rigbyStudy.ts` | Source rectangles, atlas text, bone/slot definitions, body/view fitting, outfit skins, and authored clips. |
| `src/modules/dwellers/dev/components/RigbyStudyStage.vue` | Image loading, runtime parsing, poses, WebGL rendering, equipment corrections, joint overlay, and timing. |
| `src/modules/dwellers/dev/views/RigbyStudyPreview.vue` | Local controls, playback clock, reduced-motion handling, reload, and downloads. |
| `src/modules/dwellers/dev/assets/rigby/` | Original atlas copies, provisional heads, and provenance README. |
| `vendor/rigby2d/` | Pinned runtime, renderer, licenses, entry point, and types for the exercised API. |
| `tests/unit/modules/dwellers/dev/rigbyStudy.test.ts` | Real parser/writer/pose and equipment-skin checks for three views. |
| `tests/e2e/rigby-study.spec.ts` | Browser interaction, rendering, download, narrow-screen, and reduced-motion checks. |

Rigby2D is pinned to tag `v0.3.0`, commit `6778d30a5337bb35e88c658d67292fc982599b05`.
Upstream `src/core` and `src/webgl` are vendored with repository lint/format normalization; the small local entry point exposes `Pose`,
`readSkeletonJson`, `writeSkeletonJson`, `parseAtlas`, and `WebGLRenderer`. Both upstream licenses
(MIT OR Apache-2.0) are included. No upstream demo artwork is used. See the
[pinned upstream source](https://github.com/jaisurya-dev-art/rigby2d/tree/6778d30a5337bb35e88c658d67292fc982599b05).

No package or lockfile change was needed. Assets are imported through the development module graph,
not placed in `public/`. The successful production build was checked for study-specific JavaScript
markers; the development route, runtime, and associated imports were eliminated.

## Asset pipeline

Three PNGs are byte-for-byte copies from `/home/elder/Downloads/fallout-asset-batch/Item/`:

| Local file | Source filename | Dimensions |
| --- | --- | --- |
| `outfits.png` | `Mobile - Fallout Shelter - Items - Male Outfits.png` | 2761 × 4552 |
| `accessories.png` | `Mobile - Fallout Shelter - Items - Outfit Accessories.png` | 2164 × 1860 |
| `weapons.png` | `Mobile - Fallout Shelter - Items - Weapons and Items.png` | 1776 × 1740 |

SHA-256 hashes, in the same order:

```text
6512282686049253ee024121f0d6f8e329064a3e65cfa0c732f392f0e8b8a875
a21934bedb21372637a6dc049024161db2ce8dc585c2118a13900af7394c75ac
5e1673111962eefef52f85f7941a222cf3429be5ba70afa9f712a8e75fa4cffe
```

`outfitRects` and `REGIONS` record `[x, y, width, height]` in source-image pixels. `ATLAS_TEXT`
turns those bounds into regions for the runtime; the renderer samples the original pages. No cropped
PNG variants or destructive source edits are needed. Region bounds locate pixels; attachment offsets,
dimensions, flips, and bone placement determine how those pixels fit the rig.

The three-quarter head reuses `src/modules/dwellers/dev/assets/chet-head.webp`, the existing Chet
cutout documented by its adjacent README. `front-head.svg` and `side-head.svg` are new provisional
vector drawings. They are not recovered Fallout sprites. `HEAD_IMAGES` loads these as separate
textures, and the exported atlas also lists their filenames and bounds.

To add an outfit using this prototype:

1. Identify torso, pelvis, upper arm, forearm, thigh, shin, and foot rectangles in the source page.
2. Add the rectangles to `outfitRects`, add the skin to the `skins` initializer, and expose its ID in
   the outfit selector. Both current skins share the same `part` attachment name in each body slot.
3. Fit the attachment dimensions/offsets; inspect overlaps at bent joints in every view and profile.
4. Pause a clip, switch outfits, and confirm that the pose/phase stays fixed while the artwork changes.

The current sample has no separate bare-body layer beneath each garment: outfit pieces provide the
visible body regions. Partial clothing, exposed skin, unusual armor, hair, and split hats need explicit
coverage and drawing-order rules before catalog-wide use. Female outfits were available but not fitted
in this study.

## Rig and view conventions

The rig has 17 bones. `front` and `back` limb names mean foreground/background limbs; they do not
indicate a back-facing character view.

```text
root
└─ pelvis
   ├─ torso
   │  ├─ head                         [head and hat slots]
   │  ├─ backArm → backForearm → backHand
   │  └─ frontArm → frontForearm → frontHand → weapon
   ├─ backThigh → backShin → backFoot
   └─ frontThigh → frontShin → frontFoot
```

Coordinates are Y-up. The setup places the pelvis at Y=160 and the head bone 97 units above the torso.
Arm segment offsets are 50/45 units; leg segment offsets are 70/60 units. Rendering converts joint
overlay coordinates to canvas Y-down. Attachments are rigid regions; weighted mesh deformation is not
used in this prototype.

Front, quarter, and side use width factors `1`, `0.86`, and `0.59`, with narrower shoulder/hip separation
in side view. Bulky applies a `1.32` breadth factor to selected offsets and attachment widths. These are
projection/fitting parameters, not a 3D turn or a validated super-mutant anatomy model. All setups
currently share the same clips and slot ordering.

Drawing order is independent of bone hierarchy: background arm/leg, pelvis, foreground leg, torso,
head/hat, foreground arm, weapon, then foreground hand. Moving the hand slot last lets fingers cover
the weapon grip. Production poses may need different orderings per view and during an action.

## Playback and equipment

The view owns a normalized phase in `[0, 1)`. VueUse `useRafFn` advances it from elapsed time, selected
speed, and clip duration; each delta is capped at 100 ms. Durations are idle 3 s, walk 1.2 s, and attack
1.5 s. Selecting a clip resets phase; equipment changes preserve it. Scrubbing pauses playback.
Hidden documents pause the clock, and reduced-motion users start paused.

The stage maintains one actor in single mode, three actors in view comparison, or 36 in a 9 × 4 crowd.
Crowd actors have separate poses and staggered phase offsets. A view/body/reload signature rebuilds
actors only when their setup changes; switching equipment reuses them.

Each update:

1. Select the outfit skin, reset the pose, and apply the chosen clip at the current phase.
2. Place/scale the root and optionally reflect its X scale.
3. Set hat/weapon slot attachments and the appropriate hand shape.
4. Apply weapon holding corrections, update world transforms, and draw through Rigby2D.
5. Draw the grid, labels, ground markers, and optional joints on the second canvas.

Pistol/rifle holding raises the foreground arm and counter-rotates the weapon to keep it level. A rifle
also uses an application-side analytic two-link arm correction to target a support grip at weapon-local
`(52, 5)`. The calculation clamps reach and accounts for reflection. This exercises a usable grip,
but it is not an authored Rigby2D IK constraint and it is not included in exported animation keys.

The WebGL and overlay canvases both use a 1200 × 560 backing resolution. Images load before playback;
loading/render initialization failures surface through the existing error-message helper. Unmounting
disposes the renderer and uploaded textures, and an asynchronous-load guard prevents late setup after
navigation. `preserveDrawingBuffer` is enabled for browser readback checks; production rendering and
device-pixel-ratio sizing need a separate pass. WebGL context restoration is not implemented here.

## Reload and export contract

The runtime writer returns **`{ json, warnings }`**, not a skeleton document directly. The initial
integration passed that wrapper to the parser and failed with “not a skeleton JSON file.” The focused
runtime regression now serializes `writeSkeletonJson(skeleton).json` and parses that document.

Every setup rebuild, including the Reload button, exercises the actual writer/JSON/parser path.
Reload reconstructs the generated model and reapplies current controls; it does not import an arbitrary
user-edited file. Thus it verifies the runtime round-trip, not external-editor interoperability.

“Rig JSON” exports the selected view/body setup, both outfit skins, attachment definitions, selected
hat/weapon setup attachments, and idle/walk/attack keys. It does not export the current screen pose,
phase, mirror setting, weapon holding corrections, or support-hand solver. Although export assigns
`skeleton.skin`, the writer does not serialize that active-skin selection: consumers must choose the
desired outfit skin after loading.

“Atlas” downloads the atlas text separately. A portable bundle also needs `outfits.png`,
`accessories.png`, `weapons.png`, `front-head.svg`, `side-head.svg`, and `chet-head.webp` beside it.
There is no complete archive download. Import/edit/export in the external Rigby2D editor, including
its SVG handling, has not been tested. The JSON's Spine-style version field describes the interchange
format; playback uses Rigby2D's own runtime.

## Run and validate

From the prototype checkout:

```bash
cd /home/elder/.codex/worktrees/22b9/falloutProject/frontend
pnpm install --frozen-lockfile
pnpm exec vp dev --host 0.0.0.0 --port 5174 --strictPort
```

Open <http://localhost:5174/dev/dweller-motion-lab>. The direct `vp dev` invocation uses existing
generated API types and avoids the normal development script's API-generation prerequisite. No API
contracts changed. Port 5174 keeps this preview separate from the existing frontend on 5173.

Checks completed during implementation:

| Check | Result and scope |
| --- | --- |
| `pnpm run typecheck` | Passed. |
| `pnpm run lint` | Passed. |
| Full frontend suite | 307 files / 3,943 tests passed during implementation. |
| `pnpm exec vp test run tests/unit/modules/dwellers/dev/rigbyStudy.test.ts` | 3 cases passed; rerun after final edits. Real runtime round-trip, changing outfit artwork without changing world transforms, and animation movement with finite coordinates. |
| `tests/e2e/rigby-study.spec.ts` | 2 tests passed after final edits: interaction/rendering and 390 × 844 reduced-motion layout. |
| `pnpm run build` | Passed; study-specific JavaScript markers absent from production output. |
| `git diff --check` | Passed for the prototype changes. |

The interactive browser check verifies that an outfit swap changes canvas pixels without advancing a
paused phase; it also exercises a rifle, fedora, bulky profile, joints, mirror, reload, walk, crowd mode,
and the JSON download filename with no page errors. It does not validate exported file contents or
editor import. The narrow-screen check verifies no horizontal page overflow and paused startup;
it does not establish ideal character readability at mobile size.

Browser checks ran against the already-running 5174 server using
`pnpm exec playwright test --config /tmp/fallout-rigby-playwright.config.mjs`. That temporary config is
local, not committed. To recreate it, use the following content, updating `testDir` if the checkout moves:

```js
export default {
  testDir: '/home/elder/.codex/worktrees/22b9/falloutProject/frontend/tests/e2e',
  testMatch: 'rigby-study.spec.ts',
  outputDir: '/tmp/fallout-rigby-test-results',
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5174',
    browserName: 'chromium',
    viewport: { width: 1440, height: 1100 },
  },
}
```

## Performance evidence and remaining work

With 36 walking actors, a headless Chromium run at 1440 × 1100 collected eight displayed CPU samples:
`1.40, 1.50, 1.50, 1.80, 1.50, 2.10, 1.40, 1.30 ms` (median 1.5 ms; range 1.3–2.1 ms).
The renderer was ANGLE/Vulkan using SwiftShader. The measured interval includes the stage's pose work,
WebGL draw submission, and overlay drawing; metrics are emitted at most once per 400 ms. It does not
wait for GPU completion or measure total application frame time. These samples are feasibility
evidence, not a mobile benchmark, sustained-load result, or FPS guarantee.

Before choosing the production pipeline:

1. Import the complete asset bundle into the external editor, edit a joint/clip/skin, export, and replay
   it here. Confirm what survives and whether head images need rasterization.
2. Finish one character in all three views with authored art, convincing joint overlaps, and a planted
   walk cycle. Then fit a second outfit to measure the actual incremental authoring effort.
3. Fit distinct humanoid proportions, including female and substantially larger/smaller bodies, rather
   than treating the width-only bulky sample as universal support.
4. Define reusable weapon-class grip targets and hair/headwear coverage rules; test asymmetry under
   mirroring. Move pose corrections into reusable data or authored constraints where appropriate.
5. Measure physical desktop/mobile devices with representative scenes, including memory, texture
   sizes, draw calls, and long-running playback. Repack atlas pages or adjust batching only from evidence.

Combat events, locomotion, hit/death clips, blending, catalog bindings, and game-state integration are
subsequent implementation work. The prototype establishes equipment/runtime feasibility and makes
the remaining art and authoring questions visible.
