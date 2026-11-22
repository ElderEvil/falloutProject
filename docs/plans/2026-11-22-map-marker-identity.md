# Map marker identity — waves

Status: wave 1 implemented in this branch. Waves 2–4 are design-only until played.

## Problem

The map spends its one glyph channel on two jobs: identity and discovery state.
When identity is unknown the state glyph wins, so the wasteland fills with
punctuation that says nothing:

- `wasteland_site` — the default archetype for every emergent discovery — was
  `mdi:map-marker-alert`, so each roam find landed as an alert pin.
- `MapMarker.displayIcon` swapped any unlocked-less place for `mdi:lock-question`,
  unknown vaults used `mdi:help-circle-outline`, and the `discovery` fallback
  used `mdi:map-marker-question`.
- `origin` / `visited` / `discovery` are *states*, but `locationMarkerIcon` fell
  back to their glyphs whenever a place had no `group_key`.

## Contract

Glyph = identity (archetype). Everything else = treatment: opacity, dashed ring,
badge, colour. Punctuation survives only as a small badge, never as the marker.

Hints reveal category (a decision, with the trade-off that fog leaks a little:
you can tell a military site is near before scouting it).

## Waves

### Wave 1 — punctuation out (this branch)

- `MapMarker` no longer swaps in `mdi:lock-question`; an unscouted pin keeps its
  archetype glyph at 50% opacity with a dashed backing ring.
- `locationMarkerIcon` returns `NEUTRAL_PLACE_ICON` (`mdi:map-marker-outline`) for
  archetype-less places instead of borrowing a state glyph. Vaults and the home
  vault keep their semantic icons.
- Unknown vault signals use `mdi:radioactive` rather than `mdi:help-circle-outline`.
- Legend's "Locked" row becomes "Unscouted" with the neutral pin.
- Catalog: `wasteland_site` icon `mdi:map-marker-alert` → `mdi:sign-direction`.

No wire change, no migration. `group_key` is already sent for ununlocked places,
which is what makes category-revealing hints possible without backend work.

### Wave 2 — family palette

Colours already exist and are togglable (`useGroupColors`, `map:group-colors`,
off by default, Preferences). Nineteen hues are past the point of decoding, so
collapse them to five families — civil, industry, threat, knowledge, spectacle —
and flip the default on. Same toggle, same code path.

### Wave 3 — emergent sites get a real archetype

Assign a group at discovery from a **low-tier pool only** (gas_station,
supermarket, ruin, entertainment, wasteland_site), so both the icon and the loot
table mean something. Guardrail: the pool must stay inside wasteland_site's band
(15–30 XP, low/low-medium loot) or emergent sites out-farm hand-placed military
sites at 165. Military, research, brotherhood and exclusion stay hand-authored.

### Wave 4 — fewer markers

Cluster hints by proximity at low zoom into one "N signals" marker, expanding
past the existing declutter threshold (`renderedVaultHints` already sits on it).
Last, because clustering can hide the place you are looking for.

## Tests

- `markerTypeMeta.test.ts`: neutral fallback for `origin`/`visited`/`discovery`,
  semantic icons preserved for vaults.
- `MapMarker.test.ts`: an unscouted marker keeps its identity glyph and carries
  `marker-locked`.
- `WorldMap.test.ts`: an archetype-less place renders the neutral pin.
