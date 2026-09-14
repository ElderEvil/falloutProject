# Dweller Detail Page Structure Update

## Completed

The dweller detail page was simplified to remove the previous Container → Pane → Panel prop and event forwarding chain.

- `useDwellerDetail` owns detail-page loading, UI state, and action orchestration.
- `DwellerDetailContainer` creates and provides a typed `DwellerDetailContext`.
- Detail-pane, panel, and tab components consume that context directly.
- Detail sections are defined by the `dwellerDetailSections` registry and rendered dynamically by `DwellerPanel`.
- `MapPlaceLink` was moved from a component export to `models/dweller.ts`.
- Navigation between `:dwellerId` route params retains stale-request protection.

## Deliberate boundaries

- This is a frontend-only refactor; no backend model or API changes were made.
- The section registry includes only the currently available sections: Profile, Appearance, Stats, Equipment, and Family.
- Pets and apprentices are not represented until their backend support and UI requirements exist.

## Validation

Before handoff, run:

```bash
cd frontend
pnpm run lint
pnpm run typecheck
pnpm run test:run
```

---

# Rework proposal — not decided

Reviewed a layout proposal (kept in a local sample-data design lab, deliberately not committed) against the
shipped `DwellerDetailPane`. Nothing below is agreed; this is the shortlist to think about.

## Independent of layout

- **Radiation as a banner with the fix inline.** Today a small `Radiated – 12` chip sits in the status line and the
  RadAway action is two levels down in the card's supply row, so the player connects them themselves. The proposal
  states cause → consequence → action in one block ("12 HP blocked… Use RadAway · 1"). Matches the
  progression-visibility rule in `docs/backend/GAME_MECHANICS.md`.
- **Health ceiling explained.** Today `82 / 88 (100)` — three numbers, no story. Proposal: `82 / 88` plus
  "Base 100 · 12 blocked by RAD".
- **Drop the duplicated level readout.** The card currently renders a `Level 12` bar *and* an `Experience 450/1350`
  bar for one fact. Proposal: a single block, "Level 12 · 237 XP to level 13". Wire to real values — the lab's bar
  and its own XP figure disagree.
- **Touch targets and roles.** 44px (`min-h-11`) on every control, `aria-pressed` on tabs, `role="status"` on action
  feedback, `aria-labelledby` per section. Our `Use` / `+` supply buttons are below touch-target size.
- **`<details>` for the field log** — progressive disclosure instead of hover, so it works on touch.
  *Shipped:* `DwellerBio` folds `FIELD LOG` behind a `FIELD LOG · N entries` summary (`collapsible` in
  `SECTION_META`); prose sections stay expanded.

## The structural idea: fact next to its action

Assignment is split across two places today — room name and `Matched` pill in the header meta line, actions
(`Unassign` / `Wasteland` / `Train`) in the left card. The proposal groups room + status + *reasoning* + actions into
one card and drops the `Matched` pill:

> `Power Generator` · Working · **Strength 6 used here · Agility 8 is strongest**

That answers "should I move her?" instead of only labelling state. Feasible with existing data: `ability:
SPECIALEnum | null` is already on the room schema in `core/types/api.generated.ts`, and `getAbilityConfig` exists in
`models/dweller.ts`. Constraint: derive the advice from the same rule that sets the backend assignment-correct flag,
or the copy will contradict the badge.

## Conflicts with decisions already shipped

- Header actions: the proposal shows `Chat` + a pencil and drops the overflow menu, so soft-delete disappears.
  Rename + soft-delete went behind the kebab deliberately — though the pencil button is better a11y than
  click-the-name.
- Everything through a modal (Train / Wasteland / Use / gear) adds a step to what are currently one-click actions.
- Gender and age demoted to plain text: drops them out of the badge-style preference, and gender stays
  gameplay-relevant (breeding requires male + female).
- Three dossier tabs vs the five in the section registry.

## Ignore

Sidebar, footer, and simplified breadcrumb are lab scaffolding. Chat-as-modal would regress the chat route. The
portrait is an SVG placeholder, not a portrait proposal.

# Badge sizing: why demographics read big and identity reads small

**The cause is storage provenance, not a design decision.** `gender`, `rarity`, and `age_group` are first-class typed
enum columns on `Dweller` (`app/models/dweller.py`). `race`, `faction`, and `state_of_being` live inside the
`visual_attributes` JSONB blob — the same column the dweller generation agent writes to. `DwellerVisualAttributes` is
that agent's `output_type`, so the blob co-evolves with prompts and is validated only in the app layer.

Two containers produced two components, and two components produced two visual weights. Worth naming plainly: the size
difference currently encodes **which container a fact lives in** — something the player cannot see and does not care
about.

What the JSONB placement genuinely costs (these are real, not cosmetic):

- **No GIN index** on `visual_attributes`, so race / faction / state cannot be filtered or sorted. The filter panel
  offers status and age group only — of the six facts here, just age participates in faceting.
- **No PG enum-drift guard.** `gender` / `rarity` / `age_group` are covered by `PG_ENUM_LABELS_SNAPSHOT`; JSONB values
  are validated by the app-layer schema instead.
- **Sparse by design.** The schema docstring states "only populated fields are stored", so a human carries no
  `state_of_being` — hence two chips on humans and three on ghouls, super mutants, and synths.
- **The trio is not homogeneous.** `race` and `faction` are *user input* merged into a container otherwise filled with
  AI output (`height`, `hair_style`, `pose`, `voice_line_*`); `state_of_being` is AI-derived. Only the AI-derived one
  truly belongs in a blob that churns with prompt versions.

| | Gender / Rarity / Age | Race / Faction / State of being |
| --- | --- | --- |
| Component | `DwellerBadge.vue`, wrapped by `Dweller{Gender,Rarity,Age}Badge` | `DwellerIdentitySignal.vue` |
| Size API | `size="sm" \| "md"` | none — only `compact` (label on/off) |
| Shape | pill (`border-radius: 999px`) | `rounded-sm` |
| Colour | per-category via `--badge-color` | always `theme-primary` |
| Hover | none (documented: "a fact … never responds to hover") | `hover:border-theme-primary hover:bg-theme-primary/10` |
| Hint | native `title` | `UTooltip` |
| Order in list contexts | Age → Gender → Rarity | n/a |

On the detail page the trio is requested at `size="md"` while identity can only ever render at its single fixed size.
Nothing decided that identity matters less — it has no large mode to request.

Three further consequences:

- The badge-style preference (colourful / mono) drives `--badge-*` tokens, which `DwellerIdentitySignal` ignores. In
  colourful mode the page mixes coloured pills with green squares; in mono mode it converges.
- `DwellerBadge` uses a native `title` while `DwellerIdentitySignal` uses `UTooltip` — they disagree about
  `STYLEGUIDE.md` → Tooltips & Popovers, and each is right about a different aspect of it.
- Ordering is inconsistent: list contexts render Age → Gender → Rarity (alphabetical), `DwellerDetailPane` renders
  Gender → Rarity → Age.

## The decision

Three ways to resolve it, in increasing cost:

1. **Keep the split and document it as interim.** The badges stay as they are; this section records why — the facts are
   JSONB residents expected to move if they are ever promoted. Cheapest, but leaves the UI advertising the schema.
2. **Promote the stable ones.** `race` and `faction` are user input rather than AI output, so they have a column's
   stability profile: promotion needs a migration, a backfill out of the blob, `PG_ENUM_LABELS_SNAPSHOT` entries, and a
   GIN index if filtering is wanted. `state_of_being` stays in the blob, where prompt-driven churn is harmless.
3. **Decouple presentation from storage.** Leave the JSONB layout alone and render all six facts from one primitive,
   sized by context (sm in lists, md on detail). The player sees semantic weight; the schema stays provisional.

Option 3 is the smallest change that stops the UI leaking the storage layout. Option 2 is worth revisiting only if
filtering or sorting by faction becomes a product need.

Taking the shared primitive means moving three things into `DwellerBadge`: the `monogram` fallback (mutation
I/II/III — no glyph reads as "how mutated"), icon-only `compact`, and `UTooltip` in place of `title`. That is the
version with the least code and the fewest rules.
