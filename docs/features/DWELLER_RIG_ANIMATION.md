# Dweller rig and animation sources — research

Research date: 2026-10-28. Code baseline: `1a8dffd2` on `feat/dweller-2d-rig`.
This is a design and tooling investigation. No extraction, importer, rig format or production
renderer is approved by this document; effort figures are estimates.

Legal boundary: Fallout Shelter artwork, skeletons and animation clips are Bethesda IP. The project
already keeps extracted art out of production builds and records each crop's source hash in
[`dev/assets/README.md`](../../frontend/src/modules/dwellers/dev/assets/README.md). Any extracted
animation data must follow the same rule: local study and reference only, DEV-gated, never shipped.

## Summary

- The current rig is **procedural, not animated**. `sampleRigClip()` derives four clips from sine and
  lerp math; there are no keyframes, easing curves, events or loop metadata.
- Production dwellers still render static portraits. The rig exists only at `/dev/dweller-rig`.
- Three sources can supply motion, in descending fidelity: **extract the original clips**, **reconstruct
  motion from footage**, **author original clips**. The third is required regardless of which of the
  first two succeeds, because both terminate in the same clip format.
- Recommended order: build the data-driven clip layer and authoring surface first; use extraction for
  reference where lawful; use video reconstruction as a drafting tool; ship authored or reconstructed
  motion with original art.
- A generic "AI reverse-engineering" tool is feasible as **perception + fitting + human review**. It is
  not feasible as a fully autonomous sprite-to-rig-from-one-image generator.

## What exists today

| Fact | Evidence |
| --- | --- |
| 15-bone forward-kinematics rig | [`dwellerRig.ts`](../../frontend/src/modules/dwellers/dev/models/dwellerRig.ts) `RIG_BONES` |
| Four procedural clips: `bind`, `idle`, `walk`, `punch` | `RIG_CLIPS`, `sampleRigClip()` (`dwellerRig.ts:279`, `:336`) |
| Motion comes from parented joint transforms, not animation frames | [`dev/assets/README.md`](../../frontend/src/modules/dwellers/dev/assets/README.md) |
| Art is lossless atlas crops with SHA-256 provenance | same README |
| DEV-only route, excluded from production builds | `router/index.ts` `import.meta.env.DEV` block |
| Production dwellers render static portraits | `modules/dwellers/components/DwellerPortrait.vue` |
| Combat motion is designed as reusable choreography per weapon family, not per asset | [`COMBAT_ANIMATION_MATRIX.md`](../frontend/COMBAT_ANIMATION_MATRIX.md) |

The gap is not art, and not skeleton math. It is **retargetable, authored motion data** plus a runtime
that can play it outside the dev page.

## Where animation data can come from

### Tier 1 — Extract the original data (highest fidelity)

Fallout Shelter ships Unity asset bundles; community extraction threads unpack its textures with Unity
tools. The animation representation is **unverified** and is the first thing to check.

1. Confirm the install layout (`FalloutShelter_Data/`, `resources.assets`, `sharedassets*.assets`,
   bundles) and the Unity version from `globalgamemanagers`.
2. Dump with **AssetRipper** (Unity 3.5 through 6000) or **AssetStudioMod**, which exports
   `Animator` as FBX with its bound `AnimationClip` and extracts sprites with pivots and atlas
   rectangles.
3. Look for, in order of payoff:
   - **Spine data** (`skeleton.json` + `.atlas`): exact slots, bone timelines and curves. If present,
     an importer is a few days. Spine-in-Unity is a known pattern; whether this game uses it is open.
   - **`AnimationClip` transform curves with an `AnimatorController`** per state: convert curves to
     joint-angle tracks.
   - **Custom `MonoBehaviour` bone tables**: decompile, recover the hierarchy and sampler, then
     reimplement the sampler rather than the data.
4. Estimated effort: 0.5 day to identify the format; 2–4 days if Animator or Spine; 3–10 days if
   script-driven.

Constraints: extracted clips encode the original art's proportions and are not a licence to ship the
art. Treat them as calibration data for authored clips.

### Tier 2 — Reconstruct motion from footage (AI-assisted)

```
60 fps capture → crop → part/person segmentation (SAM 2)
→ 2D keypoints (DWPose, RTMPose, MediaPipe)
→ temporal tracking and confidence smoothing (Kalman, Savitzky–Golay)
→ FK fit to RIG_BONES, minimising per-frame reprojection error
→ keyframe reduction (Ramer–Douglas–Peucker), loop detection, contact events
→ clip JSON → human review in /dev/dweller-rig
```

Reliability by part:

| Stage | Reliability |
| --- | --- |
| Segmentation, part or person | High |
| Torso, head, upper-arm keypoints | High |
| Feet and hands under occlusion | Low; needs interpolation and manual fixes |
| Out-of-plane rotation (twist) | Not representable in a 2D cutout |

Supporting evidence: [SpriteToMesh](https://arxiv.org/html/2602.21153v1) reports learned sprite
segmentation at IoU 0.87 while direct learned vertex/bone prediction failed to converge. The lesson is
to use models for perception and deterministic fitting for geometry, not a single end-to-end model.

### Tier 3 — Author original clips (safest, and required)

- Author `idle`, `walk`, `punch` and combat reads on the existing rig: keyframes per bone, easing,
  events, loop points, mirroring.
- Retarget by normalising angles and scaling limb lengths, so one clip serves human, ghoul, super
  mutant and synth, matching the combat matrix's "reusable choreography" principle.
- AI drafting is useful but not an asset source: video-to-motion (Plask, Rokoko, DeepMotion,
  Cascadeur) and Spine auto-riggers (SpineFactory, Riggy, rig-c, God Mode, GameImageToolkit,
  Stretchy Studio) produce references, timings or Spine data — not this SVG rig.

## Proposed rig system

Split the current single file into three data layers:

1. **Rig definition** — bones (`id`, `parent`, `pivot`, `bindAngle`, limits) and sprites (atlas rect,
   pivot, z-order, bone). Per character and outfit.
2. **Clip** — data only:

   ```ts
   interface RigClipData {
     id: string
     duration: number
     loop: boolean
     tracks: Partial<Record<BoneId, Array<{ t: number; angle: number; easing?: string }>>>
     root: { x: Array<{ t: number; value: number }>; y: Array<{ t: number; value: number }> }
     events: Array<{ t: number; type: 'footstep' | 'hit' | 'vocal'; payload?: unknown }>
   }
   ```

3. **Renderer** — consumes a sampled pose; SVG now, atlas or canvas later.

Runtime requirements: a controller with a state machine (`idle`/`walk`/`combat`), crossfade blending,
event dispatch for sound and hit feedback, and deterministic sampling so clips are testable without a
browser clock.

Authoring surface: extend the dev page with a keyframe timeline, onion skin, copy/paste pose, mirror,
JSON import/export, and a source-frame overlay for Tier 2 review.

Production integration: move the renderer out of `dev/` into `modules/dwellers/animation` behind a
feature flag; the dev route remains the authoring tool.

Provenance: extend the existing source table with clip origin (`authored`, `reconstructed`,
`extracted-reference`) and the licence or ownership note for each clip.

## AI reverse-engineering tool (proposal)

Working name: **rig-forge**. Local, review-gated, generic to any 2D character; Fallout Shelter is the
test corpus.

| Stage | Technique | Trust |
| --- | --- | --- |
| Part split | existing atlas cuts, or SAM 2 / GroundingDINO | High |
| Skeleton | DWPose or RTMPose keypoints mapped to the 15 bones; pivots from bind pose | High with review |
| Motion | per-frame IK fit, temporal smoothing, confidence interpolation | Medium; weak on hands |
| Clip synthesis | loop detection, RDP keyframe reduction, contact-event detection | High and verifiable |
| Review | skeleton overlay on source frames, per-frame error, accept/reject | Human-owned |

Non-goals:

- Inferring bone data from one flat image. Published work indicates direct learned prediction does not
  converge; segmentation plus explicit fitting is the viable route.
- Writing clips without human approval.
- Bundling an asset ripper into the application or its CI.

MVP scope: an offline Python script that consumes a video plus keypoints and emits clip JSON, and an
`/dev/dweller-rig` import/review surface. Estimated 5–10 days.

## Experiments and decision rule

| Experiment | Purpose | Estimate |
| --- | --- | --- |
| Format recon | List assets, Unity version, search for Spine and `AnimationClip` | 0.5 day |
| Single-character dump | AssetRipper one bundle; inspect curves | 0.5 day |
| Clip-format prototype | Convert `idle`/`walk`/`punch` to JSON tracks on the dev page | 3–5 days |
| Reconstruction spike | One clip from 60 fps footage, hand-reviewed | 2–3 days |
| Production renderer | Move renderer behind a flag and play one clip in-game | 3–5 days |

Decision rule:

- **Fidelity first** → Tier 1, then author the rest against extracted timing.
- **Ship animations** → Tier 3, with Tier 2 as a drafting tool.
- **Build a tool/product** → generic Tier 2 pipeline, extraction kept out of the shipped artifact.

Experiments 1 and 2 decide whether Tier 1 costs hours or weeks. Experiment 3 is required in every path
and can start immediately.

## Open questions

- What animation representation does Fallout Shelter actually use — Spine, Unity `AnimationClip`, or a
  custom cutout sampler?
- Is the build IL2CPP (`global-metadata.dat`) or Mono? That determines decompilation tooling for a
  script-driven rig.
- Which capture sources are acceptable for reconstruction, given the IP boundary?
- Which clips belong in the first production slice — combat reads, or ambient vault idles?

## Sources

Repository:

- [`dwellerRig.ts`](../../frontend/src/modules/dwellers/dev/models/dwellerRig.ts)
- [`dev/assets/README.md`](../../frontend/src/modules/dwellers/dev/assets/README.md)
- [`COMBAT_ANIMATION_MATRIX.md`](../frontend/COMBAT_ANIMATION_MATRIX.md)

External:

- AssetRipper — <https://github.com/AssetRipper/AssetRipper>
- AssetStudioMod — <https://github.com/aelurum/AssetStudio>
- AssetStudio (Unity 2.x–6, multi-threaded) — <https://github.com/Razviar/assetstudio>
- Fallout Shelter Unity asset discussion — <https://www.vg-resource.com/thread-39465.html>
- Spine-in-Unity extraction walkthrough — <https://github.com/yotan-dev/mi-anim-docs>
- SpriteToMesh (segmentation vs. learned vertex prediction) — <https://arxiv.org/html/2602.21153v1>
- Plask motion capture and retargeting — <https://plask.ai/en-US/docs/47>
- Cascadeur retargeting — <https://cascadeur.com/help/category/219>
- SpineFactory — <https://spinefactory.com/>
- Riggy — <https://riggyapp.com/>
- rig-c toolchain — <https://rig-c.org/>
- God Mode AI — <https://www.godmodeai.co/>
- GameImageToolkit auto-rig (local YOLOv8n-pose) — <https://gameimagekit.com/en/tool/auto-rig>
- Stretchy Studio (DWPose auto-rig) — <https://github.com/nikhilash6/stretchystudio>
