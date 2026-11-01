# Dweller animation research

Research and prototype validation date: 2026-10-28. This records the research decision and initial
evidence, not a production implementation contract. See the
[motion lab implementation guide](DWELLER_MOTION_LAB.md) for code ownership, asset conventions,
startup instructions, export behavior, and validation details.

## Requirements

- Independently interchangeable outfits, weapons, and headwear.
- Front, three-quarter, and side views; no back view.
- A skeleton with joints and reusable animations.
- Support for humanoids, including substantially different body proportions.
- Reuse the supplied Fallout artwork where practical.
- Prefer free/open-source tools and a manageable browser integration.

The first research pass deliberately avoided evaluating the current experimental branch in depth.
Follow-up work is authorized in a separate worktree, with a development-only frontend preview.

## Recommended approach

Use **modular 2D cutout animation**, initially with rigid image attachments and a small humanoid
skeleton. Add weighted meshes only where bending visibly improves a joint or garment. Keep animation
data separate from equipment artwork so new equipment normally requires fitting, not reanimation.

Use one bone naming/hierarchy convention, with three view-specific setups and a small family of body
profiles. Shared structure does not imply that identical joint coordinates or animation keys fit every
view and body. Front/side artwork, changes in drawing order, and pose corrections remain authoring work.

The first prototype uses **Rigby2D's own JavaScript/WebGL runtime**, with **SkelForm** as the alternative.
Basic playback and equipment composition have now been exercised. The editor workflow and production
maturity remain unverified, so this is still a provisional tool choice. The user prefers free/open
source; Spine serves as a feature benchmark.

## Tool comparison

| Tool | Relevant capabilities | Integration and limitations | Assessment |
| --- | --- | --- | --- |
| Rigby2D | Bones, slots, skins, meshes, IK, PSD import, animation tracks and events | MIT/Apache-2.0 source; own JavaScript runtime and WebGL renderer. Documentation currently describes copying runtime modules into the application. Young project; test exported assets and rendering before adoption. | First browser prototype candidate. |
| SkelForm | Bones, IK, meshes, outfit/skin styles, PSD import, desktop and web editor | GPL-3.0 editor, MIT JavaScript runtime. Separate web-player example implements WebGL playback and style switching. The generic runtime alone does not unpack `.skf` files. Documentation describes the project as a work in progress. | Strong independent alternative. |
| Godot | Integrated cutout rigging, animation, texture swaps, drawing-order controls | Web export and JavaScriptBridge can connect an embedded game scene to the app. Requires an engine deployment/integration rather than only a character library. | Prefer if a broader game scene moves into Godot. |
| Spine | Equipment skins, attachments, constraints, meshes, official PixiJS runtime | Commercial editor/runtime licensing. Essential excludes advanced features such as meshes and IK. | Useful benchmark; lower priority under the free/open-source preference. |
| Rive | Bones, weighted raster/vector meshes, browser playback | Capable alternative, but character equipment composition and the selected export plan need validation. It is not an entirely open-source editor workflow. | Secondary candidate, not selected for the first prototype. |
| Live2D Cubism | Deformers, meshes, parameter-driven motion, reusable model templates | Technically capable; its workflow emphasizes authored deformations. For this project's equipment-heavy full-body action, a conventional skeleton/slot workflow appears more direct. | Lower priority; this is a project-fit judgment. |

DragonBones' current JavaScript repository points users to LoongBones. Do not assume the historical
free editor and current editor offerings have the same terms or integration status. Likewise,
“Spine-compatible export” does not by itself grant permission to use the official Spine runtime;
evaluate an editor's own runtime separately.

## Character and equipment structure

- Skeleton: root, pelvis, torso, head, paired upper arms/forearms/hands, and thighs/shins/feet.
- Outfit: separate torso, sleeve, trouser, boot, and optional accessory attachments. Replace or hide
  covered body pieces to prevent skin/clothing showing through during bends.
- Headwear: head attachment plus explicit visibility rules for hair. Some hats require foreground and
  background parts.
- Weapon: primary grip anchor; two-handed weapons also need a support-hand target. Keep hand artwork
  and weapon drawing order coordinated.
- Animation library: idle, walk, hit, and attack first; attacks grouped by weapon class rather than
  individual inventory item. Equipment swapping must preserve the current animation phase.
- Drawing order: explicitly controlled by view and, when needed, by the animation. Bone hierarchy
  and screen overlap order are separate concerns.

Use front, three-quarter, and side setups. Mirroring can supply the opposite facing direction where
acceptable, but Pip-Boys, lettering, handedness, and other asymmetric details need exceptions. A
skeleton cannot reconstruct a missing side view from front artwork. A projection/foreshortening study
must be labeled as such rather than presented as finished view-specific art.

Humans, human-shaped synths, and similar ghouls can reuse much of a profile. Children, super mutants,
and bulky armor need proportion changes, equipment fitting, and animation corrections. “All humanoids”
means a compatible family of rigs; it does not mean one universally stretched skeleton.

## Existing artwork

The initial sample of repository assets contained a flattened dweller portrait, a torso-only outfit
icon, and weapon art. These are useful references, but overlapped or absent body parts cannot simply
be separated without reconstructing missing surfaces.

The user subsequently supplied `/home/elder/Downloads/fallout-asset-batch/`. In particular:

- `Item/Mobile - Fallout Shelter - Items - Male Outfits.png`
- `Item/Mobile - Fallout Shelter - Items - Female Outfits.png`
- `Item/Mobile - Fallout Shelter - Items - Outfit Accessories.png`
- `Item/Mobile - Fallout Shelter - Items - Weapons and Items.png`
- `fos_legendary.png`

The outfit atlases already contain separate torsos, pelvis pieces, upper/lower limbs, and footwear.
The accessory atlas contains hands, hair, and headwear. This materially improves reuse compared with
cutting flattened portraits apart. Atlas pieces still need measured rectangles, pivots, scale, and
rotation; they are not animation frames or a complete set of front/side character views.

Prefer using original atlas pixels with recorded source rectangles. Preserve the source files and
document asset provenance. Reuse compatible artwork, and prepare new art only for missing views,
surfaces, or body fits. Keep portrait artwork separate from the standardized animated body templates.

## Prototype acceptance criteria

1. Render supplied outfit pieces with a real skeletal runtime in the frontend.
2. Compare human and bulky humanoid body profiles, two outfits, headwear, and pistol/rifle attachments.
3. Inspect front, three-quarter, and side setups; identify reused/projection art versus authored views.
4. Play idle, walk, and attack; pause, scrub, mirror, and inspect joints.
5. Swap equipment without replacing or restarting the animation.
6. Export/reload the rig through the chosen runtime; identify editor round-trip limitations explicitly.
7. Measure browser playback with several dozen instances. Report measured behavior and environment,
   not vendor benchmark numbers as application performance.

The key scalability test is the effort required for the **second outfit and second body profile**.
A good first walking character alone does not validate the equipment pipeline.

Keep the preview under a development-only `/dev/...` route with menu metadata. Production character
replacement, backend equipment wiring, combat integration, and a complete art catalog follow visual
evaluation; they are not prerequisites for this research prototype.

## First prototype findings

Implemented in a separate worktree on `feat/dweller-rigby-study`:
`/home/elder/.codex/worktrees/22b9/falloutProject`.
Development route: `/dev/dweller-motion-lab`; preview server port: `5174`.
The existing experiment and its uncommitted changes remain in the main worktree.

The study uses Rigby2D v0.3.0, commit `6778d30a5337bb35e88c658d67292fc982599b05`, with its
actual skeleton parser, pose evaluator, and WebGL renderer. The supplied atlas PNGs are copied without
altering their pixels. A 17-bone setup supports two outfit skins, two headwear attachments, pistol/rifle
attachments, human/bulky proportions, and idle/walk/attack clips. Equipment changes preserve phase.

Front and side heads are provisional vector drawings; the three-quarter head reuses the existing
Chet cutout. Front/side outfit pieces are projected from the same atlas, not genuinely authored new
views. The bulky profile is a proportion test, not a finished super-mutant character. The preview
labels these limits. Foot planting, garment/joint polish, and arbitrary hair/hat visibility remain open.

The JSON writer returns `{ json, warnings }`, not a bare skeleton document. The initial integration
mistook that wrapper for the document; the runtime test reproduced the failure, and the integration
now serializes/parses `json`. All three view setups pass the round-trip and equipment-skin test.
The browser also exercises reload, equipment changes, mirroring, crowd mode, and JSON download.
The external editor's import/edit/export workflow has not yet been verified. Rifle grip correction
is currently an application pose adjustment and is not baked into exported clips.

A headless Chromium check at 1440 × 1100, with ANGLE/SwiftShader and 36 walking actors, sampled
CPU pose-update plus draw-submission costs of 1.3–2.1 ms (eight samples, median 1.5 ms). This excludes
GPU completion, is not a mobile benchmark, and does not establish a frame-rate guarantee. The preview
shows live timing so actual hardware can be assessed. Texture batching and atlas repacking have not
been optimized.

Validation: frontend typecheck, lint, and production build; full frontend suite (307 files, 3,943
tests); three focused runtime cases; two browser checks for interactive controls and a 390px viewport
with reduced motion. The [implementation guide](DWELLER_MOTION_LAB.md) records asset provenance,
startup commands, validation scope, and export limitations in this worktree.

The early result supports the cutout/equipment approach. It does not yet settle Rigby2D's editor
usability or the cost of making production-quality front/side artwork.

## Sources

Primary sources consulted on 2026-10-28:

- [Rigby2D source and license](https://github.com/jaisurya-dev-art/rigby2d)
- [Rigby2D runtime guide](https://github.com/jaisurya-dev-art/rigby2d/blob/develop/docs/runtimes.md)
- [Rigby2D bones, slots, and attachments](https://github.com/jaisurya-dev-art/rigby2d/blob/develop/docs/bones-and-slots.md)
- [SkelForm features](https://skelform.org/)
- [SkelForm editor source](https://github.com/Retropaint/SkelForm)
- [SkelForm JavaScript runtime](https://github.com/Retropaint/skelform-js)
- [SkelForm web player](https://github.com/Retropaint/skelform-web-player)
- [Godot cutout animation](https://docs.godotengine.org/en/stable/tutorials/animation/cutout_animation.html)
- [Godot web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- [Godot JavaScriptBridge](https://docs.godotengine.org/en/stable/classes/class_javascriptbridge.html)
- [Spine equipment composition example](https://esotericsoftware.com/spine-examples-mix-and-match)
- [Spine PixiJS integration](https://esotericsoftware.com/spine-pixi)
- [Spine licensing and edition comparison](https://esotericsoftware.com/spine-purchase)
- [Rive bones](https://rive.app/docs/editor/manipulating-shapes/bones)
- [Rive pricing/export plans](https://rive.app/pricing)
- [Live2D deformers](https://docs.live2d.com/en/cubism-editor-manual/deformer/)
- [DragonBones JavaScript repository](https://github.com/DragonBones/DragonBonesJS)

Feature, pricing, and maintenance information can change. Small-project feature lists are maintainer
claims until exercised by the prototype. The tested subset is described above; broader runtime
correctness, performance on target hardware, and editor usability remain open.
