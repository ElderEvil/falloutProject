# 2D rig texture sources

These are lossless WebP crops, with no redrawing, from the supplied asset batch and an existing repository portrait. ImageMagick `-crop ... +repage -define webp:lossless=true` performs extraction. Sprite rectangles and joint pivots live in `../models/dwellerRig.ts`.

| Output                  | Input                                                                                                | Crop (width × height + x + y) | Input SHA-256                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------------------ |
| `vault-suit-parts.webp` | `/home/elder/Downloads/fallout-asset-batch/Item/Mobile - Fallout Shelter - Items - Male Outfits.png` | `520x260+560+0`               | `6512282686049253ee024121f0d6f8e329064a3e65cfa0c732f392f0e8b8a875` |
| `hand-poses.webp`       | Same batch, `Item/Mobile - Fallout Shelter - Items - Outfit Accessories.png`                         | `180x120+0+1580`              | `a21934bedb21372637a6dc049024161db2ce8dc585c2118a13900af7394c75ac` |
| `dweller-head.webp`     | `backend/app/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp`                              | `165x196+65+28`               | `04b040da85b18101981d53d2d9b4f629172e2451c90d75d71a47b520c90208dc` |

The provided outfit sheet already separates torsos, hips, upper/lower limbs, and shoes. The head is a cutout of the existing static portrait; it does not deform or turn in 3D. Source sheets are not animation frames. Motion comes from the parented joint transforms.

This is a development-only study at `/dev/dweller-rig`. Its view imports these assets through the DEV-gated route, so production builds do not include the rig or its textures. It uses no Blender assets, models, renders, or runtime.

The prototype covers one adult male head/outfit, bind/idle/walk/punch clips, joint-angle trims, mirrored rendering, and a skeleton overlay. It does not replace live portraits, wire into combat playback, implement foot IK, or solve race/outfit/age combinations. Those decisions follow visual review of the rig.

In the unmirrored view, the foreground arm is the dweller's right arm on the viewer's left; the background arm is on the viewer's right. The original hand atlas wrist attachment is `(145, 35)`. Sprite-local rotation/mirroring aligns that source point with each wrist bone; source orientation is independent of bone rotation.
