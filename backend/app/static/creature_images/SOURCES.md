# Creature artwork

Original Fallout Shelter sprite sheets were downloaded manually from The Spriters Resource:

- Deathclaw, Feral Ghoul, Mole Rat, Radscorpion and Radroach: [Fallout Shelter creature sheets](https://www.spriters-resource.com/mobile/falloutshelter/)
- [Eyebot](https://www.spriters-resource.com/mobile/falloutshelter/asset/218201/)
- [Protectron](https://www.spriters-resource.com/mobile/falloutshelter/asset/218200/)
- [Mr. Handy](https://www.spriters-resource.com/mobile/falloutshelter/asset/208044/)

The original sheets are retained as PNGs in this directory. The assembled previews in
`assembled/` are AI-assisted reconstructions produced with OpenAI's built-in imagegen
tool and encoded as WebP at quality 90 with alpha preserved. Exact generation and
correction prompts are recorded in `assembled/generation-prompts.json`.

`originals/mr-handy.webp` is the original Fallout Shelter Mr. Handy full-body sprite
(transparent), trimmed, padded and encoded as WebP at quality 90. The arena uses it
directly instead of the AI reconstruction.

Fallout Shelter artwork belongs to its original rights holders; reconstruction does
not turn these assets into original game artwork or grant an independent license.

The current arena roster uses Training Eyebot and Training Mr. Handy. Protectron remains
an experimental gallery preview; its head/neck assembly still needs visual approval.
`parts/protectron-head-clockwise90.webp` is the isolated head-rotation preview for that work.

The Protectron head reference was taken from [Bethesda's October 2022 update screenshot](https://fallout.bethesda.net/en-EU/news/all-new-content-arrives-in-fallout-shelter-today).

## Creature concepts

The assembled Yao Guai, Brahmin, Mirelurk, Bloatfly, Radstag and Night Stalker are
generated artwork, using the assembled Deathclaw and Mole Rat as style references.
They are not extracted game sprites. `assembled/yao-guai.webp` is the selected second,
less furry version. Generation used the built-in imagegen tool, which does not
expose a model selector, followed by WebP encoding at quality 90 with alpha preserved.
Prompts for the four additional creatures and the Yao Guai revision are recorded in
`assembled/concept-prompts.json`.

## Raider

`assembled/raider.webp` is generated artwork, re-rendered from the Fallout Wiki's raider
lineup screenshot (`FoS_raiders_lineup.jpg`) with `gpt-image-2.5-flare`, then flipped to
face the responders and encoded as WebP at quality 90 with alpha preserved. It is not an
extracted game sprite. The prompt and reference URL are recorded in
`assembled/concept-prompts.json`.
