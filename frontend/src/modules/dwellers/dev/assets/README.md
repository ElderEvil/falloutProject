# 2D rig texture sources

## Contour fit (current pass)

The eight limb pieces now fit traced color/shape regions in the original 136×287 Chet image.
The reviewable polygons live in `frontend/tests/e2e/dweller-rig-outlines.json`; these include
estimated hidden joint caps where the torso or foreground limb occludes a part. The foreground
lower arm follows the Pip-Boy envelope; lower legs follow the dark boot shafts. Classic suit
textures remain unchanged, so these fitted parts still have classic suit colors and details.

Source contours come from each crop's alpha channel. A uniform similarity transform (translation,
rotation, scale) maximizes intersection-over-union with each traced region. The upper-arm crops
are swapped to put the broader capsule on the foreground shoulder. The browser regression renders
each actual source crop through its SVG transform and compares its alpha mask with the traced
polygon. Seven of eight limbs failed before this fit; all eight now pass. This replaces the prior
four approximate point anchors, which did not constrain the shapes between those points.

The torso trim, head, hands, shoes and pelvis retain their existing calibration. Do not interpret
these limb traces as exact outlines of occluded anatomy. The scratch review images are
`frontend/rig-shots/traced-reference.png` and `frontend/rig-shots/bind-contours.png`.
This supersedes the historical bone-centred capsule placement notes below.

These are lossless WebP crops, with no redrawing, from the supplied asset batch and an existing repository portrait. ImageMagick `-crop ... +repage -define webp:lossless=true` performs extraction. Sprite rectangles and joint pivots live in `../models/dwellerRig.ts`.

| Output                  | Input                                                                                                | Crop (width × height + x + y) | Input SHA-256                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------------------ |
| `vault-suit-parts.webp` | `/home/elder/Downloads/fallout-asset-batch/Item/Mobile - Fallout Shelter - Items - Male Outfits.png` | `520x260+560+0`               | `6512282686049253ee024121f0d6f8e329064a3e65cfa0c732f392f0e8b8a875` |
| `hand-poses.webp`       | Same batch, `Item/Mobile - Fallout Shelter - Items - Outfit Accessories.png`                         | `180x120+0+1580`              | `a21934bedb21372637a6dc049024161db2ce8dc585c2118a13900af7394c75ac` |
| `chet-head.webp`        | `backend/app/static/legendary_dweller_images/FOS_Dw_Chet.png`                                        | `94x96+19+0`, jaw mask below  | `0a5abe0416a97308522520a25c6bd95837340d78354204de91ad0697f5eb84dc` |
| `chet-reference.webp`   | Same original Chet sprite                                                                            | Whole `136x287` sprite        | `0a5abe0416a97308522520a25c6bd95837340d78354204de91ad0697f5eb84dc` |

The provided outfit sheet already separates torsos, hips, upper/lower limbs, and shoes. The head is a cutout of the original legendary Chet sprite; it does not deform or turn in 3D. Source sheets are not animation frames. Motion comes from the parented joint transforms.

This is a development-only study at `/dev/dweller-rig`. Its view imports these assets through the DEV-gated route, so production builds do not include the rig or its textures. It uses no Blender assets, models, renders, or runtime.

The prototype uses the original Chet head with classic vault-suit parts (the reference sprite wears the Vault 33 suit). Common/rare base and variant portraits are AI-generated and are not used in this study. It covers bind/idle/walk/punch clips, joint-angle trims, mirrored rendering, and a skeleton overlay. It does not replace live portraits, wire into combat playback, implement foot IK, or solve race/outfit/age combinations. Those decisions follow visual review of the rig.

In the unmirrored view, the foreground arm is the dweller's right arm on the viewer's left; the background arm is on the viewer's right. Open hands use atlas wrist `(25, 77)` with opposite mirrored orientations. The punch clip uses the original fist at wrist `(138, 32)`. Sprite-local rotation/mirroring aligns that source point with each wrist bone; source orientation is independent of bone rotation.

The Chet head extraction also clears pixels below the source jaw using a black polygon on the extracted alpha mask: `0,77 31,77 67,93 94,93 94,96 0,96`. This removes the original shirt collar without redrawing the face. Head point `(55, 87)` stays on its original neck joint. Torso placement follows Chet’s yellow collar, center stripe and waist trim; the suit’s existing half-circle remains beneath the chin, with a small neckline seam left for the later gap-filling pass.

In the unmirrored view, the foreground right leg is on the viewer's left and the background left leg on the viewer's right. The walk clip varies elbow flexion in opposition, rather than keeping both forearms rigid.

Chet’s whole sprite is a translucent, independently adjustable reference layer, never a replacement for the separated suit/body pieces. The bind skeleton uses joint landmarks measured on the 136 × 287 reference, mapped with a uniform 1.25 scale at `(107.5, 90.25)`. Atlas sprite frames are positioned and scaled to follow that silhouette; the torso and waist overlap, while the original thigh/shin/foot parts remain separate. The source artwork is unchanged. The Vault 33 suit, Pip-Boy and boots in the reference still have different contours from the classic suit pieces.

Shoe calibration uses two outline anchors per foot, independently of the ankle pivot. The front shoe’s atlas heel `(493, 237)` and toe `(448, 239)` map to Chet `(70, 283)` and `(110, 274)`; the back shoe’s heel `(426, 237)` and toe `(381, 239)` map to `(19, 260)` and `(42, 281)`. Uniform scaling and rotation fit these pairs without stretching the shoes. Ankle pivots remain inside their shoe silhouettes. The raised back foot follows the reference’s heel-up stance.

Bind refinement changes only sprite placement, scale and rotation. Limbs, hands and shoes preserve their source aspect ratios; the front upper arm is enlarged another 16% around its shoulder pivot, the front thigh is longer, and the shin and shoe frames follow Chet’s leg contours. The torso is rotated from 3° clockwise to 1.5° counter-clockwise, its frame begins 10 rig pixels farther left, and its width increases from 85 to 103 while its height changes from 126.5 to 124. Yellow collar, center-stripe and belt landmarks guide the fit; skeleton joints and all source pixels are unchanged. Classic suit cuffs, hands and low shoes have different contours from Chet’s Pip-Boy and tall boots, so not every edge can coincide. Remaining joint gaps are visible for a later pass; body part pixels have not been repainted, redrawn or filled.

The latest hand fit raises the right wrist (viewer left) from Chet `(20, 185)` to `(20, 182)` and moves the left wrist outward from `(119, 177)` to `(122, 178)`. Open-hand scale changes from 1 to 0.97 on the right and from 0.775 to 0.8 on the left, with bind headings of −19° and −23°. Both forearm cuffs follow their revised wrist positions; open hands and punch fists retain their native wrist attachment. Source crops and aspect ratios are unchanged.

The subsequent silhouette pass flattens and narrows the pelvis beneath the belt so it no longer covers the crossing thighs with a round bulge. Both thighs and shins are uniformly enlarged and repositioned; the back thigh rotates another 9° counter-clockwise to follow the diagonal into the raised knee. The torso moves left and grows upward while retaining its belt alignment, bringing the collar closer to the jaw. The right wrist (viewer left) lowers another 6 reference pixels to `(20, 188)`, with its forearm cuff following; the right upper arm grows another 20% uniformly to broaden the shoulder. Head and shoe placement, the other skeleton landmarks, source crops and source pixels stay unchanged. The classic suit still differs from Chet’s detailed Vault 33 outfit and tall boots.

The current hip fit restores the atlas sphere’s round proportions at `103 × 101.759` rig pixels, matching the lower torso’s width. It rotates −20° and sits beneath the torso and crossing thigh, with its center near Chet `(62, 167)`. Both thighs paint over their shin caps; the front thigh and both shins rotate to follow the reference’s leg contours. The left hand (viewer right) scales down from 0.8 to 0.7 and its wrist moves inward to `(120, 179)`, keeping the hand within the portrait frame while the forearm cuff follows. Shoe anchors remain unchanged.

The torso frame is a least-squares fit of the five yellow-trim anchors (`−3.6°`, every anchor within 2 reference pixels), and the hip sphere is shifted 6 rig pixels toward the belly so it continues the lower-torso curve. Both hip pivots moved from Chet’s silhouette to the pelvis centre (`(60, 175)` and `(66, 175)`); thigh frames were re-parametrised so the bind artwork is pixel-identical, but a swinging thigh now stays attached to the waist.

Limb frames were rescaled about their pivots toward one size per depth layer (front arm/leg ≈ 1.3/1.15 × atlas, back arm/leg ≈ 1.15/1.05 ×; forearms, shins and shoes 0.78–1.05 ×) so the two sides no longer differ by up to 40 %. Each limb capsule is centred on its bone (`x = -width/2`, sprite rotation 0) with its top cap on the pivot, so a segment rotates about its own axis instead of orbiting it; the parent part reaches past every joint, so knees and elbows stay covered through the full swing, and upper arms and thighs tuck ~20 px into the shoulder and pelvis.

Motion clips are authored as absolute world headings per bone and converted to parent-relative angles, so they no longer depend on the bind angles. `idle` rests in the upright line-up stance seen in the legendary-dweller roster (feet apart, arms hanging slightly out) with a breath cycle. `walk` is a one-second strut whose phase 0 reproduces Chet’s stride and whose half cycle mirrors it: thighs swing ±25.5° about a slight forward offset, the knee bends most mid-swing, shoes stay flat on the floor apart from a small push-off heel lift (`14°·cos³`), the torso leans 5° with a 5 px bounce, and forearms stay near vertical and lag the upper arm as in the Vault Boy sheets. `punch` winds up from that stance, lunges into a straight at shoulder height with the rear heel raised, then recovers to guard.

The head renderer additionally clips the small blue/yellow collar fragment beside the chin with an SVG polygon in native head coordinates: `0,0 94,0 94,77 83,77 80,82 75,87 69,90 64,93 0,96`. This refines the extraction boundary without changing the source WebP or repainting the face.

### Yellow-region torso correction

The five approximate trim-point checks were replaced by a browser comparison of actual yellow
pixels in three reference regions: collar (y 88–103), vertical stripe (104–152), and belt (153–174),
all within x 35–108. Each region contributes equally to the mean intersection-over-union. The
old torso scored 0.447 in the browser and failed the new 0.60 threshold. Color-mask fitting scores
about 0.695 after correction. The fit uses rotation 3.9839° and frame
`[-69.8495, -97.1017, 113.95, 113.8325]`, moving the belt upward and aligning the stripe boundaries.
Torso width remains constrained by the existing hip/torso proportion check. No source pixels change.
The classic suit's single belt band cannot reproduce the reference's three separate bands by
placement and scaling alone; this is an alignment improvement, not an identical outfit texture.

### Open-hand silhouette correction

Both open hands are uniformly smaller and rotated against Chet's actual skin masks while keeping
atlas wrist `(25,77)` exactly on the existing wrist joints. Foreground scale is now 0.7401 rig px
per atlas px (was 0.9), rotation −104.2039° (was −90°); background scale is 0.625 (was 0.78),
rotation 75.4353° (was 90°). No source pixels or joint positions change; punch fists are unchanged.
The new browser regression compares hand alpha silhouettes to reference skin regions, covering
palm, thumb and fingers rather than wrist position alone. The former thumb-direction check now
asserts direction rather than an arbitrary five-screen-pixel minimum; reference silhouette overlap
checks size. The source hand has more spread fingers than Chet's, so contour agreement is partial.

The user-directed foreground-hand refinement enlarges the right open hand by 8% and raises its
wrist from reference `(20,188)` to `(20,186)`. Forearm sprite rotation compensates for the revised
bone heading, preserving the sleeve's bind placement. The left hand remains unchanged.

The foreground/right upper-arm source crop is now vertically flipped inside its existing frame,
per user direction. Its joint, frame and other limb pieces are unchanged. The preview's Part
placement controls allow manual sprite overrides, including both mirror axes, without altering
source textures. Overrides are temporary and can be copied from Placement JSON.
