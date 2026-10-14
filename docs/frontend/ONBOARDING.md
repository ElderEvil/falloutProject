# Spotlight onboarding

> Status: **design, not implemented.** Replaces the banner UI from #978 (`ObjectiveGuide.vue`). The backend it
> needs (ordered starter objectives, read-only progress credit, owner claims) ships in #995.

## Goal

From the moment a vault is created, the player always knows **one thing to do next**. The game highlights a single
button or number and dims everything else. No wall of text, no modal tour.

## Behaviour

- **One step at a time.** The current step is the lowest unclaimed `starter` objective. One element is
  highlighted; the rest of the screen is dimmed.
- **Never blocks.** The dimming is visual only (`pointer-events: none`). The player can click anywhere, leave the
  page or ignore the hint.
- **Advances by itself.** When the player does the action, the objective completes and the card switches to
  "Reward ready". No "Next" button.
- **Claim from the card.** "Claim 50 caps" calls the existing claim endpoint and shows the existing success toast.
  The next step then highlights.
- **Welcome card.** A short, targetless intro the first time a vault opens: role, goal, "Skip tour".
- **Skippable and quiet.** "Skip tour" is stored per vault. Finished or skipped tours never come back.
- **Hand-off.** When the last starter step is claimed, the Overseer Briefing takes over. No extra screen.
- **No anchor, no problem.** If a target is not on screen, show the card without a highlight and point at the
  sidebar link that leads there.

## Step map (from `starter.json`)

Anchors are proposals. None of them exists yet; add a `data-onboarding="<key>"` attribute to each.

| Seq | Step | Highlight | Anchor key |
|---:|---|---|---|
| 0 | Assign dwellers to Power | the Power Generator room | `room-power` |
| 1 | Produce 150 Power | power number in the resource bar | `resource-power` |
| 2 | Build a Living Quarters | build button | `build` |
| 3 | Assign a dweller correctly | Dwellers nav link | `nav-dwellers` |
| 4 | Scavenge 300 caps | Exploration nav link | `nav-exploration` |
| 5 | Reach 10 dwellers | population number | `population` |
| 6 | Reach 18 dwellers | population number | `population` |
| 7 | Build Overseer's Office | build button | `build` |
| 8 | Reverse-engineer a schematic | Storage nav link | `nav-storage` |
| 9 | Train a SPECIAL stat | Training nav link | `nav-training` |
| 10 | Complete 3 quests | Quests nav link | `nav-quests` |
| 11 | Develop a level 20 dweller | Dwellers nav link | `nav-dwellers` |
| 12 | Grow a 50-dweller vault | population number | `population` |

Side panel links already exist (`SidePanel.vue` `navItems`: `dwellers`, `exploration`, `quests`, `training`,
`storage`). `ResourceBar.vue` renders each resource but exposes no hook. Whether the population number and the
build button have a stable element still needs checking.

## Implementation notes

- **One component:** `OnboardingSpotlight.vue`, mounted once in `DefaultLayout.vue`.
  - Finds the target with `document.querySelector('[data-onboarding="…"]')`.
  - Tracks its rectangle with VueUse (`useElementBounding`; VueUse is already installed).
  - Draws the cut-out as one absolutely positioned box with a large `box-shadow` (`0 0 0 100vmax`), plus a pulse ring
    on the target.
- **Rendering:** teleport to `body`; no dependency on a tour library.
- **State:** `useStorage` keyed by vault ID for "skipped" and "welcome seen". Progress is server-side already.
- **Claiming and refreshing:** reuse the objectives store (`completeObjective`) and the vault refresh from #978. Keep
  `currentObjective()` and the objective-to-route mapping.
- **Drop:** `ObjectiveGuide.vue`, its `DefaultLayout` hook and its tests.
- **Surfacing rule:** a claim must still show a toast or modal, not just the bell entry
  (`docs/backend/GAME_MECHANICS.md`).

## Accessibility and polish

- The card is a labelled region (`aria-live="polite"`); the highlighted element keeps its normal focus order.
- "Skip tour" is reachable by keyboard; Escape dismisses the card for the session.
- Respect `prefers-reduced-motion`: no pulse, no animated cut-out.
- Mobile: dock the card to the bottom edge; never cover the highlighted element.
- Use theme tokens only (see `STYLEGUIDE.md`); no raw palette classes (color guard).

## Tests

- Chooses the lowest unclaimed starter step; ignores completed ones.
- Skip persists per vault and hides the tour.
- Missing anchor falls back to a card without a cut-out.
- Claim button calls the claim endpoint once and advances to the next step.
- Reduced-motion removes the animation.

## Out of scope

- A scripted tour for post-chapter systems (incidents, arena, wasteland); add later as more starter steps.
- Server-side "skipped" flag (per-vault local storage is enough for now).
- A tour library or video.

## Open questions

- Should the welcome card also appear for existing vaults, or only newly created ones?
- Should skipping hide the tour for the account, not just the vault?
