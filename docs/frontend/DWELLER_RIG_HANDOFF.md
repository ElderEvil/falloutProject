# Dweller 2D rig — handoff

Status: **experimental checkpoint; manual placement editor implemented.** Branch `feat/dweller-2d-rig`, main worktree
`/var/home/elder/Projects/falloutProject`. Last code baseline commit: `1a8dffd2`.
Written 2026-10-28.

This is the working state of the SVG cutout rig at `/dev/dweller-rig`. It is a development-only
study; nothing here is wired into production dweller rendering.

## Where the code lives

| File | Role |
| --- | --- |
| `frontend/src/modules/dwellers/dev/models/dwellerRig.ts` | Bone table, sprite frames, landmarks, clips, FK solver |
| `frontend/src/modules/dwellers/dev/components/DwellerRig.vue` | SVG renderer, head clip path, reference overlay, bone overlay |
| `frontend/src/modules/dwellers/dev/views/DwellerRigPreview.vue` | Workbench UI (clips, scrub, joint inspector, overlay) |
| `frontend/src/modules/dwellers/dev/assets/README.md` | Asset provenance + a running log of every fit pass |
| `frontend/tests/unit/modules/dwellers/dev/dwellerRig.test.ts` | Skeleton, clip and fit invariants (21 tests) |
| `frontend/tests/e2e/dweller-rig.spec.ts` | Pixel-anchor checks against the Chet reference (13 tests) |

Assets are lossless WebP crops of the supplied atlas plus a cutout of the original legendary Chet
sprite. **Never repaint, redraw or fill source pixels** — every fit is placement, scale and rotation
only. Keep the DEV-gated route and the provenance table intact (Bethesda IP boundary).

## Coordinate conventions (read before editing)

- `RIG_REFERENCE = { x: 107.5, y: 90.25, scale: 1.25, width: 136, height: 287 }` — the rig maps the
  original 136×287 Chet sprite at 1.25×, aligned at the neck.
- `landmarks` are joint points **in Chet reference pixels**; `RIG_BONES` derives `offset`, `end` and
  `bindAngle` from them. Moving a landmark moves the pivot; it does not move the artwork unless you
  also re-parametrise the sprite frame (see "re-pivoting" below).
- `bindHeading()` special-cases three bones whose artwork does not point along the bone:
  `backFoot` 55°, `frontHand` −19°, `backHand` −23°.
- Sprite `frame` is `[x, y, w, h]` in the bone's local space, applied **after** the bone rotation.
  `crop` is the atlas rect. Uniform scale is mandatory for limbs — the unit suite asserts
  `frame.w / crop.w === frame.h / crop.h` for every limb, hand and shoe.
- Limb capsules are centred on their bone (`x = -w/2`) with the top cap on the pivot, sprite
  `rotation: 0`. This is what makes a segment rotate about its own axis instead of orbiting it.
  Shoes and hands keep their own rotations because their artwork is not axis-aligned.
- **Clips are authored as absolute world headings**, then converted to parent-relative angles by
  `toRelative()`. This decouples clips from bind angles — that is deliberate, keep it. Sign
  convention: downward limbs, positive swings the tip toward the viewer's left; upright bones
  (spine, head), positive leans forward; feet, 0 is flat on the floor and positive raises the heel.

## What changed in this pass (all uncommitted)

### Fit to the original art

- **Torso**: least-squares fit of the five yellow-trim anchors → `frame [-57.682, -96.704, 103.929,
  124.724]`, `rotation: -3.6`. Every anchor is now within ~1.8 reference px (was 6.2 px, which had
  broken the e2e trim test).
- **Pelvis sphere**: shifted 6 rig px toward the belly (`frame x` −66.877 → −61.239, compensated for
  its −20° sprite rotation) so it continues the lower-torso curve instead of bulging.
- **Hip pivots**: moved from Chet's silhouette to the pelvis centre — `frontThigh (60,175)`,
  `backThigh (66,175)`. Thigh frames were re-parametrised so the bind artwork is pixel-identical,
  but a swinging thigh now stays attached to the waist.
- **Far shoulder (3/4 view)**: `backUpperArm` pivot moved from `(101,105)` to `(93,103)`, i.e. inside
  the torso outline and behind it in paint order. A unit test asserts the shoulder is >10 px inside
  the torso's right edge and that the idle far hand clears the hip.
- **Limb sizing**: both sides normalised toward one size per depth layer. Front upper arm 1.45× →
  1.1× atlas, back upper arm 1.02× → 1.0×, front thigh 1.27× → 1.15×, back thigh 0.96× → 1.05×,
  forearms/shins/shoes 0.78–1.05×. Previously the two sides differed by up to 40 %.
- **Joint overlap**: each shin and forearm starts ~12–16 rig px above its pivot while the parent
  part reaches past the joint, so knees and elbows stay covered through the full swing. Upper arms
  tuck ~18 px into the shoulder, thighs ~22 px into the pelvis.

### Motion

- `idle` (3.2 s): upright line-up stance from `legendary-dwellers-fallout-shelter-standing.png` —
  feet apart, arms hanging slightly out — plus a breath cycle. Replaces a stiff straight-legged
  mannequin with hands in front of the crotch.
- `walk` (1 s): phase 0 reproduces Chet's stride, 50 % mirrors it. Thighs swing ±25.5° about a 2.5°
  forward offset; knee bends most mid-swing (`9 − 17·cos + 30·sin²`); heel rises only at push-off
  (`14°·cos³`) and shoes are otherwise flat; 5° lean, 5 px bounce; forearms stay near vertical and
  lag the upper arm. The far arm swings about a forward-leaning centre with a smaller amplitude
  (`ARM_CENTER.back = −1.4`, `ARM_SWING.back = 14` vs front `6.75` / `21.65`) so perspective keeps it
  clear of the torso.
- `punch` (1.2 s): wind-up from the rest stance, lunging straight at shoulder height with the rear
  heel raised, recovery to guard.

### Tests

- Updated: hip/shoulder anchors, elbow-flexion test (now asserts no hyperextension instead of a
  fixed 25° range), foot test (flat except a 14° push-off heel).
- Added: walk passes through Chet's stride and mirrors at half cycle; shoes flat except push-off;
  idle rests upright; far shoulder hidden inside the torso.

## Current validation

```
cd frontend
pnpm run test -- tests/unit/modules/dwellers/dev/dwellerRig.test.ts   # 21 passed
PW_SKIP_BACKEND=1 pnpm exec playwright test tests/e2e/dweller-rig.spec.ts --project=chromium  # 13 passed
pnpm run lint        # 0 warnings, 0 errors
pnpm run typecheck   # clean
```

## Latest contour correction (2026-10-28)

The previous normalized limb sizes and the subsequent four-point fit were superseded by per-part
contour matching. See the asset README's **Contour fit** section and the independently traced
polygons in `frontend/tests/e2e/dweller-rig-outlines.json`. Both arms and legs now have individually
fitted uniform scale, translation and sprite rotation; **zero sprite rotation and centred frames
are no longer invariants**. Upper-arm crop assignments are swapped. Joint landmarks and motion
curves are unchanged. Hidden caps are estimated; visible suit/boot/Pip-Boy boundaries guide the fit.
The new browser alpha-contour test failed on seven limbs before the correction and passes after.
Review `frontend/rig-shots/traced-reference.png` beside `frontend/rig-shots/bind-contours.png`.

## Open work — start here

### 1. Keep the rig inside Chet's frame (in progress)

Measured share of rig pixels falling outside Chet's silhouette (see tooling below):

| Pose | Before this pass | Now |
| --- | --- | --- |
| Bind | 6.6 % | 5.4 % |
| Idle | — | 5.1 % |
| Walk 0 / 25 / 50 / 75 % | 12.3 / 11.3 / 12.6 / 9.1 % | 8.7 / 11.1 / 13.6 / 8.9 % |

Bind width is now inside his frame (rig x 7..134 vs his 0..134). Remaining overflow in bind is
concentrated at **y 200–220** (hands plus the thigh/shin junction) and at **y 110–140** (shoulder
line). Walk 50 % is the worst frame and got slightly worse — the front leg reaches furthest back
there. Inspect the overlay before trimming: some of that gap is the classic suit's shape differing
from Chet's Vault 33 suit and tall boots, not a scale error, and shrinking correct parts would make
it worse.

### 2. Then, in rough priority order

- Re-check the punch clip against the frame; it was authored before the limb rescale.
- Foot IK / contact locking: the walk currently bounces the root rather than planting feet, so the
  planted shoe slides slightly. A simple two-bone IK or a contact-phase root offset would fix it.
- Decide whether the rig should stay procedural or move to keyframe data. The other worktree
  (`feat/dweller-rigby-study`) already has a data-driven clip format; our absolute-heading
  convention makes baking `strideLeg`/`strideArm` to keyframe tracks straightforward.
- Only then consider production integration (move the renderer out of `dev/` behind a flag).

## Measurement tooling (temporary — delete before committing)

### Follow-up measurement pass (2026-10-28)

Reproduced all six bind/idle/walk overflow measurements above without changing the rig.
Extended the capture harness to punch, including exact authored keyframes rather than only
quarter-cycle samples. Captures remain in `frontend/rig-shots/`.

| Punch phase | Reference-space x bounds | Outside fixed Chet silhouette |
| --- | --- | --- |
| 0 / 100 % | 20..122 | 4.6 % |
| 22 % (wind-up) | -5..148 | 15.7 % |
| 42 % (extension) | 37..166 | 27.2 % |
| 66 % (recovery) | 30..140 | 12.4 % |

Visual inspection of the extension and walk-50 captures suggests the fixed-pose silhouette
metric conflates pose changes with fit errors. In particular, the extended punch naturally
crosses Chet's right outline. Do not turn these percentages into universal fit thresholds or
shrink limbs to reduce them. Use bind-pose comparisons for artwork calibration and a separate
motion envelope for animation. The punch remains within the SVG stage in the inspected captures;
contact locking and motion quality still need work. No artwork or rig parameters changed.

Validation rerun: 21 unit tests and 13 browser checks passed; the extended capture harness also
passed. Exact punch captures: `punch-22.png`, `punch-42.png`, `punch-66.png`, `punch-100.png`.

Local measurement artifacts are excluded from commits: `frontend/rig-shots/` is gitignored,
and the scratch capture spec is excluded locally.

- `frontend/tests/e2e/zz-rig-shots.spec.ts` — capture harness. Renders the rig and the Chet
  reference as separate alpha masks at the same transform, plus overlay screenshots, for bind/idle/
  walk at several phases. Run with
  `PW_SKIP_BACKEND=1 pnpm exec playwright test tests/e2e/zz-rig-shots.spec.ts --project=chromium`.
- `frontend/rig-shots/compare.mjs` — diffs each mask against `mask-reference.png` and prints, per
  10-px band, the reference-x range where the rig exceeds Chet's outline, plus the overall overflow
  percentage. Usage: `node rig-shots/compare.mjs bind-0 idle-0 walk-0 walk-25 walk-50 walk-75`.
- `frontend/rig-shots/silhouette.mjs` — prints Chet's per-row silhouette extents from
  `chet.rgba` (produced with `magick .../chet-reference.webp -depth 8 rgba:rig-shots/chet.rgba`).

If this pass continues, consider promoting the harness into a real spec with thresholds instead of
keeping it as a scratch file.

## Gotchas

- **Hard-coded anchors live in two places.** `dweller-rig.spec.ts` asserts exact reference
  coordinates for wrists, shoes, torso trim and the head/torso attachment; the unit suite asserts
  the bind landmarks. Moving a landmark or a frame means updating both, or the suite fails with a
  small pixel delta.
- **Re-pivoting a bone** (moving its landmark without moving the artwork) requires re-parametrising
  the sprite frame: translate the frame by `rotate((old − new) · scale, −(heading + spriteRotation))`
  and adjust `sprite.rotation` by `headingOld − headingNew`. This is how the hip move kept the bind
  pose pixel-identical.
- The head is clipped by an SVG polygon in native head coordinates
  (`0,0 94,0 94,77 83,77 80,82 75,87 69,90 64,93 0,96`) to remove the collar fragment beside the
  chin. It is asserted by an e2e test that samples alpha at cheek/chin/collar.
- `frontend/AGENTS.md` governs state/transport ownership; this module is dev-only and has no store
  or API calls, keep it that way.

## Related work

- `docs/features/DWELLER_RIG_ANIMATION.md` — research on where animation data could come from
  (extraction, video reconstruction, authoring). Recommends a rig/clip/renderer split.
- `docs/frontend/DWELLER_ANIMATION_RESEARCH.md` and `docs/frontend/DWELLER_MOTION_LAB.md` — the
  Rigby2D study in worktree `/var/home/elder/.codex/worktrees/22b9/falloutProject` on branch
  `feat/dweller-rigby-study` (route `/dev/dweller-motion-lab`). It owns the data-driven clip format
  and equipment slots/skins; its clips are coarser than ours. Complementary, not competing.
- `docs/frontend/COMBAT_ANIMATION_MATRIX.md` — reusable choreography per weapon family, the eventual
  consumer of these clips.

Those three docs and the `COMBAT_ANIMATION_MATRIX.md` / `docs/frontend/README.md` edits are the
other agent's work; this pass did not touch them.

## Latest torso correction

The earlier −3.6° five-anchor torso fit is superseded by the asset README's **Yellow-region torso
correction**. Rotation is now 3.9839° with frame `[-69.8495, -97.1017, 113.95, 113.8325]`.
The browser test compares yellow collar/stripe/belt regions instead of five approximate points.
The original three-band belt and classic single-band belt remain different source artwork.

## Latest hand correction

Open hands now fit the reference skin silhouettes with fixed wrist attachments; see asset README.
Both are smaller and their sprite rotations changed. Source pixels, skeleton and punch fists stay
unchanged. Browser coverage now measures the visible hand silhouettes as well as wrist placement.

Foreground/right open hand refinement: +8% uniform scale, wrist raised 2 reference pixels to
`(20,186)`. The forearm's sprite rotation compensates for its revised heading. Left hand unchanged.

## Manual placement workbench

At `/dev/dweller-rig`, select a joint and use **Part placement** to edit its artwork separately
from the skeleton. X/Y and one-pixel nudges use the artwork's rotated local axes. Width/height
scale together; rotation and horizontal/vertical flips are independent. Reset selected part
restores its checked-in sprite, including the right upper arm's user-requested vertical flip.
Placements survive clip switches and Reset pose, but are in-memory only. Copy Placement JSON
before reloading; it contains complete sprite overrides keyed by bone ID. There is no import UI.
The renderer/solver accepts these overrides without changing joints or descendants. When editing
hands in punch, a manual hand override takes precedence over the automatic fist sprite.

Validation: 21 unit tests, 16 browser checks, lint and typecheck passed. The new browser check
covers editing, linked scaling, unchanged descendant transforms, clip switching, export and reset.

### Direct manipulation

**Edit mode** in the stage toolbar now makes artwork selectable directly. Drag a piece to move it;
its four corner handles resize it uniformly about the opposite corner. The stage toolbar flips the
selected piece horizontally or vertically. Enter/Space selects focused pieces; numeric placement
controls remain available. Pointer capture keeps dragging active outside the part, and inverse SVG
transforms account for joint rotation, sprite rotation and the mirrored view. Skeleton hit targets
and playback are disabled during editing; moving a piece does not move its joints or children.
Selection handles render above the reference overlay. Draft/export lifetime is unchanged.
Validation: all 17 browser checks pass, including direct selection, drag, resize, flip and mirrored
movement; frontend lint and typecheck pass.
