# UI Direction and Token Unification

Status: **direction agreed; migration in progress**. Profile, Preferences,
Settings, AI settings, About, and Changelog are receiving the modern account
presentation on `feat/profile-ui-refresh`. Account entry and recovery remain
for a subsequent reviewable PR.

Context: PR #775 refreshed Display Preferences onto shadcn-vue primitives.
The follow-up `feat/profile-ui-refresh` branch extends that work to Profile,
Profile Editor, Vault Operations, AI Usage, and Settings. The resulting mix of
rounded account UI and terminal-style profile records exposed a broader design
question: where should each visual treatment live?

## 1. App-wide direction

Use **modern, shadcn-based presentation for account and application UI** and
**terminal presentation for gameplay UI**. The boundary follows what the
player is doing, rather than whether a screen contains a form or read-only
data.

| Account and application UI: modern presentation | Gameplay UI: terminal presentation |
|---|---|
| Profile and dossier, Profile Editor, Preferences, account settings, AI settings, sign-in and account recovery, About, Changelog | Vault and rooms, dwellers, storage, resources, quests, exploration, incidents, combat, and other game systems |

Profile's Vault Operations and AI Usage summaries use the modern profile
presentation even though they show game data. The same kind of information
shown inside a game screen can use the terminal presentation there. An embedded
component follows the surface that contains it; its module path does not
decide its appearance.

Modern presentation means restrained glow, clearer spacing and hierarchy,
rounded shadcn `Card` surfaces, and standard controls. It still uses the
Fallout color themes and typography. Terminal presentation keeps the CRT
details that support the game world: stronger glow, scanlines where useful,
compact readouts, status markings, and distinctive borders. Both treatments
must keep readable text, visible focus, and usable controls.

On account screens, keep metric icons and values neutral. Use semantic color
when it communicates a state or action, such as a verification badge, quota
warning, error alert, or destructive control. Do not color otherwise equivalent
metrics independently just to add variety. Status color should have a text
label or icon meaning that remains clear without color.

**Components and appearance are separate decisions.** Shared shadcn-vue
primitives may be used in either part of the app for consistent behavior and
accessibility; game screens can style them to fit the terminal treatment.
The app has one semantic token foundation, with presentation choices applied
at the screen or component level. Do not create two competing palettes or
duplicate controls solely to achieve the two looks.

## 2. Current token audit

### 2.1 Shell text: `text-terminal-green` vs `text-theme-primary`

Census of root text color across `frontend/src/modules/*/views/*.vue` at the
time of this proposal:

- `text-terminal-green` — 15 views: TradingPost, AISettings, Map, Quests,
  Training, Objectives, Vault, Dwellers, DwellerDetail, Graveyard,
  ExplorationDetail, Relationships, Preferences, Settings, Profile.
- `text-theme-primary` — 2 views: vault HomeView, StorageView.
- No shell token (inherit `body`, which is `--color-theme-primary`) — 5 views:
  About, Changelog, Exploration, Happiness, VerifyEmail.

`--color-terminal-green` aliases `--color-theme-primary` in `tailwind.css`.
`useTheme.applyTheme()` updates `--color-theme-primary` on `<html>`, so the
alias follows theme changes. `text-theme-primary` is the canonical name, and
renaming these shell classes should not change their rendered color. This
cleanup may accompany a touched view; it does not require its own migration.

### 2.2 Gray references are an inventory, not a removal target

The initial census found 67 gray Tailwind utility occurrences across 21 files,
plus roughly 40 `var(--color-gray-*)` references. Utilities occur in profile,
vault, dwellers, AI settings, chat, combat, exploration, and social UI. CSS
variable references are concentrated in rooms, with others in Preferences,
Happiness Dashboard, Dweller Detail, Quests, Objectives, and Setting Item.

The warm gray scale in `tailwind.css` is still useful for neutral game
surfaces and deliberate contrast. `--color-quest-side` also depends on
`--color-gray-800`. Keep the palette while it has callers. A gray reference
is not automatically a design error and should not be changed solely to make
the census reach zero.

Review each use by role and background before replacing it:

| Role | Guidance |
|---|---|
| Primary and muted text | Use semantic theme or foreground tokens appropriate to the surface. Check small text in all three color themes. |
| Borders and dividers | Choose a strength that preserves the existing hierarchy; `gray-700` and `gray-800` need not map to the same opacity. |
| Neutral surfaces | Choose the appropriate canvas, sunken, default, or raised surface. Preserve opacity on overlays such as `bg-gray-900/30`. |
| Status and contrast | Preserve meaning and legibility. `ResourceBar` dark text on a bright fill and `IncidentAlert` light text on danger need contrast-specific colors. |
| Focus ring offsets | Match the actual surrounding surface. For example, `NavBar` uses `bg-surface-warm`, so its offset should be checked there before replacing `ring-offset-gray-800`. |

The gray `Technical` category and fallback colors in Changelog are category
semantics; keep a visible neutral distinction when updating that screen.

## 3. Rollout

1. **Profile UI:** complete the modern treatment in `feat/profile-ui-refresh`.
   Align the dossier, Profile Editor, Vault Operations, AI Usage, Preferences,
   and Settings on shared spacing, card hierarchy, controls, and muted text.
   Keep theme colors and use terminal details sparingly as content accents.
2. **Adjacent application UI:** align AI settings, About, and Changelog with
   Profile, then bring account entry and recovery into the same presentation
   in a separate reviewable PR. Confirm navigation between these screens and
   Profile feels continuous.
3. **Shared token cleanup:** rename legacy shell aliases as views are touched;
   replace gray values only where a semantic token improves consistency or
   theme behavior. Review game screens in context, including rooms CSS, rather
   than running an app-wide gray-to-green sweep. Keep their terminal treatment.

For each UI PR, run `pnpm run lint`, `pnpm run typecheck`,
`node scripts/check-boundaries.mjs`, `pnpm run test:run`, `pnpm run build`, and
`node scripts/check-bundle-budget.mjs`. Update tests that select specific
classes, such as the Resource Bar test, when those classes change. Visually
review touched screens in FO3 teal, FNV amber, and FO4 green, including muted
text, disabled states, focus rings, and high-contrast status colors. Automated
tests do not establish whether a token choice looks right on its surface.
