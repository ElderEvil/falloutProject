# Blue-ish Background Investigation — Profile, Preferences, Changelog

**Date:** 2026-06-27
**Investigator:** Sisyphus

## Issue

User reported that the background areas of Profile, Preferences, and Changelog views appear "blue-ish" rather than pure black.

## Investigation Findings

### Background Colors (all pure black)

| View | Class Used | Resolved Color |
|------|-----------|----------------|
| `ProfileView.vue` | `bg-black` | `#000000` |
| `PreferencesView.vue` | `bg-terminalBackground` | `#000000` |
| `ChangelogView.vue` | none (inherits body) | `var(--color-terminal-background)` = `#000000` |
| Body (`tailwind.css`) | `background-color` | `var(--color-terminal-background)` = `#000000` |

### Card Backgrounds (Nuxt UI UCard)

- Nuxt UI Card with variant `outline` uses `bg-default`
- In dark mode, `--ui-bg` = `var(--ui-color-neutral-900)` = `#1a1a1a` (neutral dark gray)
- This has NO blue component (rgb(26, 26, 26) — all equal)
- Defined in `nuxt-ui.config.ts` neutral palette

### Suspected Root Cause

No explicit blue color was found in the backgrounds. The perceived blue-ish tint is most likely caused by **cumulative theme glow effects**:

1. **Box shadows on cards:** `shadow-[0_0_10px_var(--color-theme-glow)]` applied to all `UCard` components. When the FO3 (teal `#00ff9f`) theme is active, the glow `rgba(0, 255, 159, 0.3)` has a significant blue component (159/255) that casts teal/cyan ambient light.

2. **Body text-shadow:** `body { text-shadow: 0 0 10px var(--color-theme-glow); }` — creates a global colored glow on all text, contributing to the ambient color cast.

3. **CRT screen effect:** `crt-screen` class has `box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.5), 0 0 20px var(--color-theme-glow)` — the outer glow amplifies the colored cast on card edges.

4. **SidePanel scanlines overlay:** Uses `var(--color-theme-glow)` at 15% opacity as a horizontal line pattern overlay on the side panel.

The effect is most noticeable with the FO3 (teal) theme, less so with FO4 (green), and least with FNV (amber).

### Relevant Files

- `frontend/src/assets/tailwind.css` — body styles, `.crt-screen`, `.terminal-glow-*`
- `frontend/src/core/composables/useTheme.ts` — theme definitions (fo3 teal, fnv amber, fo4 green)
- `frontend/nuxt-ui.config.ts` — Nuxt UI neutral palette
- `frontend/src/modules/profile/views/ProfileView.vue`
- `frontend/src/modules/profile/views/PreferencesView.vue`
- `frontend/src/modules/profile/views/ChangelogView.vue`
- `frontend/src/core/components/common/SidePanel.vue`
- `frontend/node_modules/@nuxt/ui/dist/runtime/index.css` — Nuxt UI dark mode CSS variables

## Potential Fixes (not implemented)

If this needs to be addressed:

1. **Reduce glow intensity on card shadows:** Remove or dim `shadow-[0_0_10px_var(--color-theme-glow)]` on background cards.
2. **Adjust FO3 theme teal color:** Shift primary/glow from `#00ff9f` to a less blue-tinted green.
3. **Add explicit `bg-black` to ChangelogView's wrapper** (currently missing, inherits from body — purely cosmetic).
4. **Prefer `bg-terminalBackground` over Nuxt UI `bg-default`** on cards to keep them pure black.
