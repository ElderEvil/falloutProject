---
name: tailwindcss-v4
description: TailwindCSS v4 best practices and conventions. Use when writing or modifying TailwindCSS utilities, customizing themes, or working with @theme, @apply, @utility, or CSS-first configuration. Covers v4-specific patterns that differ significantly from v3.
---

# TailwindCSS v4

This project uses **TailwindCSS v4** with the Vite plugin (`@tailwindcss/vite`). v4 has significant differences from v3 — do NOT use v3 patterns.

## Key v4 Differences from v3

| v3 Pattern | v4 Pattern |
|---|---|
| `tailwind.config.js` with `content`, `theme`, `plugins` | CSS-first config via `@theme` in CSS |
| `theme: { extend: { colors: {} } }` | `@theme { --color-*: value; }` in CSS |
| `@tailwind base; @tailwind components; @tailwind utilities;` | `@import 'tailwindcss';` |
| `@layer components {}` | `@utility name { ... }` or plain CSS classes |
| `tailwindcss/nesting` | Native CSS `@import` nesting |
| JIT mode (explicit) | Always-on (no config needed) |
| `postcss.config.js` required | No PostCSS config needed with Vite plugin |

## Project Configuration

- **Entry point**: `frontend/src/assets/tailwind.css`
- **Plugin**: `@tailwindcss/vite` in `vite.config.ts`
- **Additional imports**: `@import '@nuxt/ui';` after tailwindcss import

### Import Order (MANDATORY)

```css
@import 'tailwindcss';
@import '@nuxt/ui';

@theme {
  /* design tokens */
}
```

TailwindCSS must be imported FIRST, then other CSS libraries, then `@theme`.

## @theme Directive

All design tokens are defined in `@theme` block in `src/assets/tailwind.css`:

```css
@theme {
  /* Colors: use --color-* prefix */
  --color-primary: #00ff00;
  --color-terminal-green: var(--theme-primary, #00ff00);

  /* Fonts: use --font-* prefix */
  --font-family-mono: 'Courier New', Courier, monospace;

  /* Spacing: use --spacing-* prefix */
  --spacing-4: 1rem;

  /* Breakpoints: use --breakpoint-* prefix */
  --breakpoint-md: 768px;

  /* Z-index: use --z-index-* prefix */
  --z-index-modal: 100;
}
```

### Token Naming Conventions

- Colors: `--color-{name}` → generates `text-{name}`, `bg-{name}`, `border-{name}`
- Fonts: `--font-family-{name}` → generates `font-{name}`
- Spacing: `--spacing-{name}` → generates `p-{name}`, `m-{name}`, `gap-{name}`, etc.
- Breakpoints: `--breakpoint-{name}` → generates `@{name}:` media queries
- Z-index: `--z-index-{name}` → generates `z-{name}`

### CSS Variables in Tokens

Tokens can reference CSS variables for dynamic theming:

```css
@theme {
  --color-theme-primary: var(--theme-primary, #00ff00);
  --color-success: var(--color-theme-primary);
}
```

This enables runtime theme switching by updating CSS custom properties.

## @utility Directive

For custom utilities that don't fit `@theme`:

```css
@utility scanlines {
  background: repeating-linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.1),
    rgba(0, 0, 0, 0.1) 1px,
    transparent 1px,
    transparent 2px
  );
}
```

Usage: `<div class="scanlines">`

## @apply Directive

Use `@apply` sparingly. Prefer plain CSS classes with CSS variables when possible:

```css
/* Good: uses theme variables */
.terminal-card {
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(0, 0, 0, 0.9);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

/* Acceptable: @apply for simple compositions */
.btn-primary {
  @apply px-4 py-2 rounded border font-mono;
}
```

## Styling Patterns

### Prefer Tailwind Utilities Over Inline Styles

```vue
<!-- Good -->
<div class="flex items-center gap-4 p-6 bg-surface rounded-lg border border-theme-primary">

<!-- Bad -->
<div style="display: flex; align-items: center; gap: 1rem; padding: 1.5rem;">
```

### Use Design Token Classes

```vue
<!-- Good: uses @theme tokens -->
<div class="text-theme-primary font-mono text-glow-pulse">

<!-- Bad: hardcoded values -->
<div style="color: #00ff00; font-family: monospace;">
```

### CRT/Terminal Effects

The project has built-in utility classes for terminal aesthetics:

- `.scanlines` — CRT scanline overlay
- `.flicker`, `.flicker-random`, `.flicker-slow` — Text flicker animation
- `.terminal-glow`, `.terminal-glow-subtle`, `.terminal-glow-strong` — Text shadow glow
- `.glow-pulse`, `.glow-pulse-subtle`, `.text-glow-pulse` — Animated glow
- `.crt-screen` — CRT screen curve effect
- `.terminal-card`, `.terminal-button`, `.terminal-input`, `.terminal-badge` — Component classes

These are defined in `src/assets/tailwind.css` outside the `@theme` block.

## Component Styling

### UI Components (`src/components/ui/`)

All UI components use Tailwind utilities exclusively. When modifying:

1. Use existing design tokens from `@theme`
2. Prefer `class` bindings over `style`
3. Use `cva` (class-variance-authority) patterns for variants
4. Keep component-specific styles in the SFC `<style>` block only when Tailwind can't express it

### Nuxt UI Integration

The project imports `@nuxt/ui` styles. When using Nuxt UI components:

- Nuxt UI components have their own Tailwind-based styling
- Override via `ui` prop or CSS variables, not by modifying Nuxt UI source
- Do NOT add `tailwind.config.js` — Nuxt UI v4 works with CSS-first config

## Common Pitfalls

- **DO NOT** create `tailwind.config.js` — v4 uses CSS-first config
- **DO NOT** use `@tailwind base/components/utilities` directives — use `@import 'tailwindcss'`
- **DO NOT** use `postcss.config.js` — the Vite plugin handles everything
- **DO NOT** use v3 `theme: { extend: {} }` syntax — use `@theme` in CSS
- **DO NOT** import from `tailwindcss/colors` — define colors in `@theme`
- **DO** restart dev server after modifying `@theme` tokens
- **DO** use CSS variables for dynamic/themed colors

## Adding New Tokens

1. Add to `@theme` block in `src/assets/tailwind.css`
2. Use the correct prefix (`--color-`, `--font-`, `--spacing-`, etc.)
3. Test that Tailwind generates the expected utility classes
4. Update `STYLEGUIDE.md` if it's a semantic/design-system token
