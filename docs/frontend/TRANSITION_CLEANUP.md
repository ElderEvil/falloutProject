# Transition cleanup — follow-up plan

## The rule

`transition: all` also animates properties the author never chose — including layout ones (`width`,
`height`, `padding`, `margin`, `top`), which forces a reflow each frame instead of a compositor-only
change. Name the properties instead. `UButton` and the dweller display controls already do this.

## Current state

57 declarations remain: **52 across 38 `.vue` files**, plus **5 in plain CSS** (`tailwind.css` ×4,
`RoomGrid.css` ×1). Mapped by module: progression 7 files, dwellers 7, rooms 4, exploration 4,
core 4, auth 4, vault 2, social 2, radio 1, profile 1, map 1.

`DwellerDisplayControls` is already clean and deduplicated — it shares one `.display-controls button`
rule and lists `background-color`, `border-color`, `box-shadow`, `opacity`, `font-weight`.

## Why the first attempt was reverted

A sweep was attempted and reverted. It is worth understanding why, because the mistake is easy to
repeat:

- It derived each replacement from a **generic eight-property superset**, and any site it could not
  attribute got a **six-property fallback**. Neither was the site's actual set, so real animations
  were silently removed: the side panel's `240px → 64px` **width** collapse, and the happiness
  gauge's **`stroke-dasharray`**.
- Its matching only understood **base selector + state suffix**. Compound and parent selectors
  (`.collapsed .nav-item`) and class-specific variants (`.view-toggle-btn.active` under a shared
  `.display-controls button` base) were never attributed at all.

So the failing sites were not just the ones that fell back to the generic list — **every
auto-derived site was unverified**. A mechanical rewrite cannot be trusted here.

## Method for the redo

Per site:

1. Find the rule declaring the transition, then **every rule that changes the same element**:
   `:hover`, `:focus-visible`, `:active`, `.active`, `.selected`, `:disabled`, compound and parent
   selectors (`.collapsed .nav-item`), and Vue `<Transition>` classes (`-enter-from`, `-leave-to`).
2. List exactly the animatable properties those rules change — including SVG presentation
   attributes (`stroke`, `stroke-dasharray`, `fill`) and `font-weight`.
3. Keep that site's own duration and easing.
4. **If anything is uncertain, leave `transition: all` in place.** A wrong list silently removes an
   animation; leaving `all` is the safe default, and the guard for new code is a separate concern.

Land it **module by module, one PR each**, so every diff is small enough to verify by eye.

## Known non-obvious sites

These were identified by hand; each is the kind of property a mechanical pass drops.

| File | Property at risk |
| --- | --- |
| `core/components/common/SidePanel.vue` | `width` (240px → 64px collapse) |
| `modules/vault/components/HappinessDashboard.vue` | `stroke-dasharray` (SVG gauge) |
| `modules/rooms/components/RoomGridCell.vue` | `top` |
| `modules/rooms/components/RoomGrid.css` | `border-width` |
| `modules/progression/components/training/TrainingQueuePanel.vue` | `padding-top` |
| `modules/progression/components/training/TrainingRoomModal.vue` | `padding-top` |
| `modules/rooms/components/RadioControls.vue` | `font-weight` |

## Guard

Add it with the **first** sweep PR, so it can be absolute:

- reject `transition: all` **and** `transition-property: all`;
- scan `src/**/*.{vue,css}` — a `.vue`-only sweep missed five sites, two of them plain `.css`;
- prove the test fails by planting a violation.

Do not introduce a baseline of known offenders; a baseline would freeze the debt it is meant to
retire.

## Also open (not urgent)

`modules/dwellers/views/DwellersView.vue` is 561 lines; the Happiness Overview block (template plus
its computeds and four handlers) could move into its own component. Cosmetic — do it when the file
is next opened for another reason.
