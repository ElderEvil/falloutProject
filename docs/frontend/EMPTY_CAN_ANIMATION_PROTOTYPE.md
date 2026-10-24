# Empty-can animation prototype

A standalone low-food warning, played by the shared bottom-right vault feedback overlay. The accepted original pose sequences remain unchanged.

- Asset: `frontend/public/assets/vault-boy/VaultBoy_EmptyCanCheck-v1.webp`.
- Built-in image generation tool; the exact underlying model is not exposed.
- Reference: `VaultBoy_AnimationsFoodLow.webp`, used only for character/style guidance.
- Six generated frames, three columns by two rows, 1536 × 1024. Playback order: `0, 1, 2, 3, 4, 5`.
- Story: hold can → inspect → tilt → invert → check again → lower can and sigh.
- WebP at quality 95 with lossless alpha, optimized below the repository asset-size limit. No frames are mixed with original game art.
- This prototype replaces the discarded rush-success in-between experiment.

## Runtime integration

The shared overlay appears 1rem from the right edge and 5rem above the bottom edge, plus device safe areas,
so it clears the game control panel. Artwork and copy pass pointer events through; only Dismiss is interactive.
Playback and its 4.2-second lifetime start after the sprite loads. Reduced motion shows the final pose.
Feedback is queued (four events maximum), repeated warning/celebration keys have a 30-second cooldown,
and changing vaults, leaving the vault, or logging out clears pending feedback.

| Event | Animation |
| --- | --- |
| Low/critical food | New empty-can check |
| Low/critical water or dehydration | Original dry-tap gesture |
| Low/critical power | Original candle gesture |
| Birth notification | Original baby announcement |
| Entering low happiness | Original unhappy sigh |
| Storage reaches capacity while viewed | Original overloaded boxes |
| Level-up, training, quest/objective/achievement completion, room unlock, combat victory | Original thumbs-up |

Rush sheets are available in the developer gallery; wiring room-rush outcomes is deferred to the rush update.

Existing toasts and notification-bell entries remain. Storage/happiness feedback triggers on state transitions;
storage is checked from the already-loaded storage store, without adding background API calls.

`/dev/` lists the UI catalog, asset gallery, and animation gallery. The galleries do not cross-link.
Use **Show in corner** in the animation gallery to preview the real overlay. All dev routes are excluded
from production builds.

## Generation prompt

Use case: stylized-concept. Asset: one complete six-frame sprite animation for a Fallout-style vault resource warning, generated as one coherent sequence, NOT in-betweens for an existing sheet. Reference image is STYLE AND CHARACTER REFERENCE ONLY. Create a new waist-up blond male Vault-Tec dweller in blue jumpsuit with yellow collar, center stripe and yellow cuffs, cream skin, thick clean black cartoon outlines, flat solid colors, matching reference's retro game illustration style. No gradients, lighting, textures or shadows. Transparent alpha background. EXACT layout: THREE equally sized columns and TWO equally sized rows, six cells total, read left to right then top to bottom. Ideally 1536x1024 with 512x512 cells. No numbers, text, border, dividers or backdrop. Every cell contains ONE complete waist-up character fully inside its cell with transparent padding, SAME body, head, proportions, scale and center line; waist baseline fixed near y=490 within each cell. Motion is a simple EMPTY FOOD CAN CHECK, exactly this chronological story: cell 1 dweller holds a small already-open turquoise food can upright at waist in his right hand (viewer left), left hand rests on belly, hopeful neutral face; cell 2 raises the same can to chest, eyes look into its open top; cell 3 brings can closer to face and tilts it halfway, surprised eyebrows; cell 4 fully inverts the can above his other palm at chest height, nothing comes out, mouth makes small disappointed O; cell 5 rotates the same empty can upright again and peers into it, frown; cell 6 lowers can to waist and sighs, shoulders slightly sag, other hand on stomach. Keep arms and fingers plausible and can identical throughout. No falling contents, no new props, no wrench. Do not mimic the source sheet's disordered arrangement: the six cells MUST follow the specified chronological order. Each frame differs clearly from its neighbors. No thumbs-up, no celebration. Do not crop heads, hands, can or torso inside a cell. Output exactly this single transparent six-pose sheet.

## Background cleanup prompt

Use case: background-extraction. Edit the supplied six-pose sprite sheet. Change ONLY the background: completely remove ALL colored backdrop, blue/brown haze, gradient, glow, vignette, shadows and semi-transparent background residue between and around the six characters. Replace it with truly empty alpha=0 transparency. Keep all SIX characters and cans EXACTLY unchanged: same coordinates, exact colors, expressions, hands, sizes, outlines and 3-column 2-row layout. No repositioning, no redrawing, no new pixels outside characters. Preserve canvas 1536x1024. Keep the blue jumpsuits, yellow trim, skin, blond hair, turquoise cans and their black outlines opaque. No checkerboard baked into the image. This is a transparent game sprite-sheet cutout, not an illustration with a background.
