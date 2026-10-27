# Raider artwork

Six persona raider variants are style-matched re-renders of the Fallout Wiki raider
lineup:

- Reference: <https://images.fallout.wiki/a/a4/FoS_raiders_lineup.jpg>

Generation used the OpenAI Images API (`/v1/images/edits`, model `gpt-image-2.5-flare`,
quality `high`, transparent background, PNG output). The six persona variants were
generated at 1024x1536 from crops of the lineup, fitted to a 902px height, and encoded
as WebP at quality 90 with alpha preserved.

Every persona variant is flipped horizontally to face the viewer's left.

Each persona has two assets: `variants/{persona}.webp` is the default idle pose and
`variants/{persona}_alt.webp` is a weapon-appropriate action pose. Group scenes can mix
default and alternate poses so multiple raiders do not read as copies; the UI chooses a
pose for variety and does not persist it.

There is no generic base raider. Every raider resolves to one of the six personas:

- Trivia encounter: the run pins one persona and a pose.
- Arena and incident scenes: the frontend picks a persona deterministically from the
  fighter or incident seed.
- Dev asset gallery: all twelve assets are listed under the Raiders tab.

Exact prompts, source crops, model, canvas sizes and post-processing are recorded in
[`manifest.json`](manifest.json).

## Personas

- Female: `sable`, `rook`, `jinx`
- Male: `gristle`, `brick`, `cutter`

Raider art lives here rather than under `../creature_images/` so its ownership,
variants and provenance stay together.

Fallout Shelter artwork belongs to its original rights holders. These are style-matched
re-renders, not extracted game sprites, and they grant no independent license.
