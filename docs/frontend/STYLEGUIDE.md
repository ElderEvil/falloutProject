# Fallout Shelter Frontend Styleguide

> **Version:** 1.2.0
> **Last Updated:** 2026-08-30
> **Design System:** TailwindCSS v4 with custom @theme

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Color System](#color-system)
3. [Intent & Emphasis Semantics](#intent--emphasis-semantics)
4. [Typography](#typography)
5. [Spacing & Layout](#spacing--layout)
6. [UI Consistency Baseline](#ui-consistency-baseline)
7. [Components](#components)
8. [Animations & Effects](#animations--effects)
9. [Accessibility](#accessibility)
10. [Best Practices](#best-practices)

---

## Design Philosophy

The Fallout Shelter UI embodies a **retro-futuristic terminal aesthetic** inspired by 1950s-era computer terminals and the Fallout universe. Key principles:

- **Monochrome terminal green** as the primary color
- **CRT monitor effects**: scanlines, flickering, phosphor glow
- **Minimalist and functional** design
- **High contrast** for readability
- **Consistent spacing** and typography

---

## Color System

### Theme System

The UI supports **3 dynamic themes** that can be switched at runtime. Themes are controlled via CSS custom properties set on the document root.

#### Available Themes

| ID    | Name                     | Primary   | Secondary | Accent    | Glow                     |
| ----- | ------------------------ | --------- | --------- | --------- | ------------------------ |
| `fo4` | Fallout 4 — Modern Green | `#00ff00` | `#003300` | `#00cc00` | `rgba(0, 255, 0, 0.3)`   |
| `fo3` | Fallout 3 — Classic Teal | `#00ff9f` | `#003322` | `#00cc88` | `rgba(0, 255, 159, 0.3)` |
| `fnv` | New Vegas — Amber        | `#ffb700` | `#332200` | `#ff9900` | `rgba(255, 183, 0, 0.3)` |

**Default theme:** `fo4` (green). Theme preference is stored in `localStorage` under key `theme`.

#### Core Theme Variables

These variables are set dynamically based on the active theme:

| Variable            | Description                | Default                |
| ------------------- | -------------------------- | ---------------------- |
| `--theme-primary`   | Primary text color         | `#00ff00`              |
| `--theme-secondary` | Secondary/dark backgrounds | `#003300`              |
| `--theme-accent`    | Accent/hover states        | `#00cc00`              |
| `--theme-glow`      | Glow effects               | `rgba(0, 255, 0, 0.3)` |

#### Design Token Mappings

Use these tokens in your CSS/components (mapped in `tailwind.css`):

| Token                     | Maps To                  | Usage                         |
| ------------------------- | ------------------------ | ----------------------------- |
| `--color-theme-primary`   | `var(--theme-primary)`   | Primary text, active elements |
| `--color-theme-secondary` | `var(--theme-secondary)` | Secondary backgrounds         |
| `--color-theme-accent`    | `var(--theme-accent)`    | Hover states, accents         |
| `--color-theme-glow`      | `var(--theme-glow)`      | Glow effects                  |

**Legacy aliases** (for backward compatibility):

- `--color-terminal-green` → `--color-theme-primary`
- `--color-terminal-green-light` → `--color-theme-primary`
- `--color-terminal-green-dark` → `--color-theme-accent`
- `--color-terminal-green-glow` → `--color-theme-glow`

**Usage Example:**

```vue
<!-- Using theme variables in scoped CSS -->
<style scoped>
.my-component {
  color: var(--color-theme-primary);
  border: 1px solid var(--color-theme-accent);
  box-shadow: 0 0 10px var(--color-theme-glow);
}
</style>

<!-- Or use Tailwind classes that reference the tokens -->
<button class="text-theme-primary hover:text-theme-accent">
  Click Me
</button>
```

### Warm-Neutral Surfaces

Every structural background uses one semantic warm-neutral role. Do not use raw black, gray, Slate, Stone, or
neutral Tailwind backgrounds for cards, panels, tracks, or overlays.

| Token                    | Value     | Use                                           |
| ------------------------ | --------- | --------------------------------------------- |
| `--color-surface-canvas` | `#141210` | Application/page canvas and modal scrim base  |
| `--color-surface-sunken` | `#0f0e0d` | Progress tracks and recessed readouts         |
| `--color-surface`        | `#1c1917` | Default card and panel surface                |
| `--color-surface-raised` | `#28231f` | Modals, popovers, selected panels, and inputs |
| `--color-surface-hover`  | `#302a25` | Hovered surface state                         |

`terminal-background`, `surface-light`, `surface-dark`, and `surface-warm*` remain compatibility aliases while
callers migrate. Legacy `gray-*` utilities now render warm neutrals but must not be selected for new backgrounds.
Use `text-theme-primary/70` and `text-theme-primary/50` for muted terminal text instead.

### Semantic Colors

| Purpose | Variable          | Value     | When to Use                      |
| ------- | ----------------- | --------- | -------------------------------- |
| Success | `--color-success` | `#00ff00` | Confirmations, positive feedback |
| Warning | `--color-warning` | `#ffaa00` | Alerts, cautions                 |
| Danger  | `--color-danger`  | `#ff0000` | Errors, destructive actions      |
| Info    | `--color-info`    | `#00aaff` | Informational messages           |

### Resource Colors

Special colors for game resources:

| Resource | Variable        | Value     | Icon Color |
| -------- | --------------- | --------- | ---------- |
| Power    | `--color-power` | `#ffdd57` | ⚡ Yellow  |
| Food     | `--color-food`  | `#ff6b6b` | 🍰 Red     |
| Water    | `--color-water` | `#4dabf7` | 💧 Blue    |
| Caps     | `--color-caps`  | `#ffd43b` | 💰 Gold    |

---

## Intent & Emphasis Semantics

**Glow is attention, and attention must be earned by intent.** Before styling any element, decide which of three
intents it carries — the intent chooses the emphasis level, never the other way around. The tokens live in
`tailwind.css` (`--glow-0` … `--glow-3`); never hand-roll shadow values.

### The three intents

| Intent            | Meaning to the user                              | Emphasis                                                             | Examples                                                                      |
| ----------------- | ------------------------------------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Actionable**    | "You can do something here, now"                 | `--glow-2` on hover/active; at most one primary CTA may glow at rest | Buttons, links, claim-reward / revive badges                                  |
| **Live status**   | "Something is happening and may need a reaction" | `--glow-3`, animated pulse — the **only** tier allowed to animate    | Dweller status badge (training, fighting), incident alerts, resource warnings |
| **Informational** | "This is a fact about the thing"                 | `--glow-0` — no glow, no animation, no hover response                | Gender, race, faction, rarity, age group, room ability, XP values             |

### Emphasis scale

| Token      | Value          | Use                                                                                                |
| ---------- | -------------- | -------------------------------------------------------------------------------------------------- |
| `--glow-0` | none           | Informational facts. Default for badges, stat values, labels                                       |
| `--glow-1` | static, subtle | Ambient CRT flavor on headings and titles — theme identity, never on chips or interactive elements |
| `--glow-2` | interactive    | Buttons and links (rest or hover); actionable badges on hover                                      |
| `--glow-3` | live pulse     | Live-status badges only, animated                                                                  |

**Hierarchy rule: a badge must never out-glow an adjacent button.** If an informational chip draws more attention
than the primary CTA next to it, the hierarchy is broken — demote the chip, not the button.

### Badge intents (`badge-info` / `badge-live` / `badge-action`)

Utility classes in `tailwind.css` make the intent enforceable by construction:

- `.badge-info` — quiet tinted chip: colored border/text codes the category, no shadow, no hover response. This is
  what `DwellerBadge` (gender, rarity, age group) implements.
- `.badge-live` — the pulsing tier; reserved for state that changes (`DwellerStatusBadge`). Not clickable, so no
  hover emphasis either.
- `.badge-action` — clicking the badge does something; behaves like a button (glow on hover). Use sparingly — most
  badges are facts.

### Buttons & space budget

- One **primary** CTA per view (filled `theme-primary`); **secondary** is outlined; **danger** never glows
  (destruction is not an invitation); **disabled** has no glow and no pointer.
- Buttons own the filled background: informational chips are never filled with `theme-primary` — fill reads as
  "clickable" just like glow does.
- Density intentions: management actions fit in one row per view; bulk toolbars exist only in selection mode;
  interactive chrome (buttons + inputs) stays under ~15% of a view's vertical space. If a page needs more, it gets
  a toolbar or a modal — not more buttons.

### Backgrounds & color allocation

- Surfaces never glow and never respond to hover unless they are interactive. "Interactive" is a property of a
  surface role, not a role of its own.
- One meaning per color per context: `theme-primary` = interactivity/brand; **rarity colors = identity coding only**
  (chip text/border, never buttons, never glow); semantic colors = state; resource colors = economy only.

### Audit checklist for new UI

1. List every glowing/pulsing element — for each, name its intent. No intent, no glow.
2. Does any informational element out-emphasize an adjacent action? Demote it.
3. Does anything respond to hover without being clickable? Remove the hover response.
4. Is more than one primary CTA visible? Demote all but one.

---

## Typography

### Font Family

**Monospace only** to maintain the terminal aesthetic:

```css
font-family: var(--font-family-mono); /* "Courier New", Courier, monospace */
```

### Font Sizes

| Size | Variable           | Value             | Usage                   |
| ---- | ------------------ | ----------------- | ----------------------- |
| XS   | `--font-size-xs`   | `0.75rem` (12px)  | Small labels, footnotes |
| SM   | `--font-size-sm`   | `0.875rem` (14px) | Secondary text          |
| Base | `--font-size-base` | `1rem` (16px)     | Body text (default)     |
| LG   | `--font-size-lg`   | `1.125rem` (18px) | Emphasized text         |
| XL   | `--font-size-xl`   | `1.25rem` (20px)  | Subheadings             |
| 2XL  | `--font-size-2xl`  | `1.5rem` (24px)   | Section headings        |
| 3XL  | `--font-size-3xl`  | `1.875rem` (30px) | Page titles             |
| 4XL  | `--font-size-4xl`  | `2.25rem` (36px)  | Hero text               |

**Usage Example:**

```vue
<h1 class="text-4xl font-bold">Vault 111</h1>
<p class="text-base">Dwellers: 42</p>
<span class="text-xs text-gray-500">Last updated: 2 min ago</span>
```

### Font Weights

| Weight | Variable               | Value | Usage          |
| ------ | ---------------------- | ----- | -------------- |
| Normal | `--font-weight-normal` | `400` | Body text      |
| Medium | `--font-weight-medium` | `500` | Emphasis       |
| Bold   | `--font-weight-bold`   | `700` | Headings, CTAs |

### Line Heights

| Height  | Variable                | Value  | Usage             |
| ------- | ----------------------- | ------ | ----------------- |
| Tight   | `--line-height-tight`   | `1.25` | Headings          |
| Normal  | `--line-height-normal`  | `1.5`  | Body text         |
| Relaxed | `--line-height-relaxed` | `1.75` | Long-form content |

---

## Spacing & Layout

### Spacing Scale

Consistent spacing using 4px base unit:

| Size | Variable       | Value     | Pixels |
| ---- | -------------- | --------- | ------ |
| 0    | `--spacing-0`  | `0`       | 0px    |
| 1    | `--spacing-1`  | `0.25rem` | 4px    |
| 2    | `--spacing-2`  | `0.5rem`  | 8px    |
| 3    | `--spacing-3`  | `0.75rem` | 12px   |
| 4    | `--spacing-4`  | `1rem`    | 16px   |
| 5    | `--spacing-5`  | `1.25rem` | 20px   |
| 6    | `--spacing-6`  | `1.5rem`  | 24px   |
| 8    | `--spacing-8`  | `2rem`    | 32px   |
| 10   | `--spacing-10` | `2.5rem`  | 40px   |
| 12   | `--spacing-12` | `3rem`    | 48px   |
| 16   | `--spacing-16` | `4rem`    | 64px   |

**Usage Guidelines:**

- **4px (1)**: Tight spacing between related elements
- **8px (2)**: Small gaps, icon padding
- **16px (4)**: Standard component padding
- **24px (6)**: Section spacing
- **32px (8)**: Large gaps between sections

### Borders

| Width  | Variable                | Value |
| ------ | ----------------------- | ----- |
| Thin   | `--border-width-thin`   | `1px` |
| Medium | `--border-width-medium` | `2px` |
| Thick  | `--border-width-thick`  | `4px` |

### Border Radius

| Size | Variable               | Value      | Usage                   |
| ---- | ---------------------- | ---------- | ----------------------- |
| None | `--border-radius-none` | `0`        | Sharp corners (default) |
| SM   | `--border-radius-sm`   | `0.125rem` | Subtle rounding         |
| Base | `--border-radius-base` | `0.25rem`  | Buttons, inputs         |
| MD   | `--border-radius-md`   | `0.375rem` | Cards                   |
| LG   | `--border-radius-lg`   | `0.5rem`   | Large elements          |
| XL   | `--border-radius-xl`   | `0.75rem`  | Modals                  |
| Full | `--border-radius-full` | `9999px`   | Pills, avatars          |

---

## UI Consistency Baseline

This section records the current visual decisions for vault-management screens. It is a reference point for future refinement, not a claim that every screen is finished.

### Page structure

- Standard management pages use one shared content rail: `mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8`.
- A page header has a clear title, icon, and a short muted-primary description. Do not use white or gray subtitles that visually detach from the terminal theme.
- The Operations Overview (`Vault 44 // Operations Overview`) is intentionally a special layout and is not normalized with this rail without a dedicated redesign.
- Rich detail content may use a narrower, centered inner column. Exploration details use `max-w-[1200px]` inside the shared outer rail so the reading flow stays centered.
- Keep distinct sections visibly separate; timeline/event-log blocks need top spacing from the content above them.

### Information hierarchy

- Keep operational summaries compact: move a metric's trend beside its value instead of spending a separate row when space is limited.
- Put feature-specific controls inside their own compact container. For example, explorer previous/next controls form one bordered navigation box rather than a full-width divider.
- Avoid decorative glow outside a component's boundary. Glow supports focus and hierarchy; it must not alter the page silhouette or make a detail view appear misaligned.
- Put room-specific operational tools in the relevant room UI. The Overseer briefing belongs with the Overseer room
  rather than competing for space in the overview; it always exposes operational, staffing, capacity, and morale
  context, while alerts supply the response queue.

### Exploration detail language

- Use the dweller portrait already shown by exploration cards, falling back to the thumbnail or account icon when needed.
- Health history is a compact, framed trend: damage remains red; healing is theme green. The sparkline is wide enough to show the journey and sits in its own subtle frame.
- Health and exploration progress use the same meter treatment: a dark, bordered, pill-shaped track; a pill-shaped theme-primary fill; a restrained internal glow; and evenly spaced terminal tick divisions. Do not introduce a separate rounded gradient style for these bars.
- Prefer semantic labels and `progressbar` ARIA values for meters instead of relying on color or icon alone.

### Relationships & family language

- Relationship stages communicate gameplay state; do not encode couple orientation with colors, icons, labels, or mechanics.
- The relationship list defaults to the compact roster-style List view. The paired-identity Grid view is optional for users who need more context per relationship.
- Do not add decorative relationship animation by default. Revisit a restrained, motion-reduced List/Grid transition only after the relationship workflow needs it.
- CRT scanlines belong to intentional terminal components, never as a page-wide overlay on the Relationships & Family screen.

---

## Components

### Buttons

```vue
<!-- Primary Button -->
<button
  class="bg-terminalGreen text-black px-4 py-2 rounded hover:bg-terminalGreenLight transition-colors"
>
  Primary Action
</button>

<!-- Secondary Button -->
<button
  class="border-2 border-terminalGreen text-terminalGreen px-4 py-2 rounded hover:bg-terminalGreenGlow transition-colors"
>
  Secondary Action
</button>

<!-- Danger Button -->
<button
  class="bg-danger text-white px-4 py-2 rounded hover:opacity-80 transition-opacity"
>
  Delete
</button>
```

### Input Fields

```vue
<input
  type="text"
  class="w-full bg-gray-700 text-terminalGreen border-2 border-gray-600 rounded px-4 py-2 focus:border-terminalGreen focus:outline-none"
  placeholder="Enter vault number..."
/>
```

### Cards

```vue
<div class="bg-surface border-2 border-gray-800 rounded-lg p-6 shadow-glow-md">
  <h3 class="text-xl font-bold mb-2 terminal-glow">Card Title</h3>
  <p class="text-gray-400">Card content goes here...</p>
</div>
```

### Resource Bars

```vue
<div class="relative flex items-center space-x-4">
  <!-- Icon -->
  <BoltIcon class="h-8 w-8 text-power" />

  <!-- Progress Bar -->
  <div class="relative h-6 w-40 rounded-full border-2 border-gray-600 bg-gray-800">
    <div class="h-full rounded-full bg-power" :style="{ width: `${percentage}%` }"></div>
    <div class="absolute inset-0 flex items-center justify-center text-xs font-bold text-black">
      <span>{{ current }}/{{ max }}</span>
    </div>
  </div>
</div>
```

### Modals

```vue
<div class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-modal">
  <div class="bg-surface border-2 border-terminalGreen rounded-lg p-8 max-w-md w-full crt-screen">
    <h2 class="text-2xl font-bold mb-4 terminal-glow">Modal Title</h2>
    <p class="mb-6">Modal content...</p>
    <div class="flex justify-end space-x-4">
      <button class="px-4 py-2 border-2 border-gray-600 rounded">Cancel</button>
      <button class="px-4 py-2 bg-terminalGreen text-black rounded">Confirm</button>
    </div>
  </div>
</div>
```

---

## Animations & Effects

### Transitions

Use CSS variables for consistent timing:

```css
transition-duration: var(--transition-fast); /* 150ms - quick feedback */
transition-duration: var(--transition-base); /* 200ms - standard */
transition-duration: var(--transition-slow); /* 300ms - deliberate */
```

### Flicker Effect

Apply to elements for CRT monitor authenticity:

```vue
<div class="flicker">
  Content with flickering effect
</div>
```

**How it works:**

```css
@keyframes flicker {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.95;
  }
  75% {
    opacity: 0.98;
  }
}
```

### Terminal Glow

Text-glow utilities for the CRT aesthetic. These are **ambient emphasis (`--glow-1`)** — decorative flavor for
headings and titles. They are not a substitute for the intent tiers: interactive elements use `--glow-2`, live
status uses `--glow-3` (see [Intent & Emphasis Semantics](#intent--emphasis-semantics)).

```vue
<!-- Interactive element: button styling carries the emphasis, glow on hover -->
<button class="terminal-glow">Glowing Button</button>

<!-- Ambient flavor on a heading: fine, it is a title, not a chip -->
<h1 class="terminal-glow-subtle">Vault Title</h1>
```

> The old `.glow-pulse` / `.glow-pulse-subtle` / `.text-glow-pulse` animation utilities were removed — pulsing is
> reserved for live status (`.badge-live`), and no usages remained.

### Scanlines

Applied globally via `.scanlines` div in layout:

```vue
<div class="scanlines"></div>
```

### CRT Screen Effect

For modal dialogs and important containers:

```vue
<div class="crt-screen bg-surface p-8">
  <!-- Content -->
</div>
```

---

## Accessibility

### Focus States

Always provide visible focus indicators:

```vue
<button
  class="focus:outline-none focus:ring-2 focus:ring-terminalGreen focus:ring-offset-2 focus:ring-offset-black"
>
  Accessible Button
</button>
```

### ARIA Labels

```vue
<button aria-label="Build new room">
  <PlusIcon class="h-6 w-6" />
</button>

<input aria-label="Search dwellers" placeholder="Search..." />
```

### Keyboard Navigation

- All interactive elements must be keyboard accessible
- Use `tabindex="0"` for custom interactive elements
- Respect focus order (logical tab sequence)

### Color Contrast

All text must meet WCAG AA standards:

- **Normal text:** 4.5:1 contrast ratio
- **Large text (18px+):** 3:1 contrast ratio

Our terminal green (`#00ff00`) on black (`#000000`) provides **excellent** contrast (21:1 ratio).

### Screen Readers

```vue
<!-- Hide decorative elements -->
<div aria-hidden="true" class="scanlines"></div>

<!-- Provide descriptive text -->
<img src="vault.png" alt="Vault 111 overview showing 42 dwellers" />
```

---

## Best Practices

### CSS Class Organization

Order classes consistently:

1. **Layout**: `flex`, `grid`, `block`
2. **Positioning**: `relative`, `absolute`, `fixed`
3. **Box Model**: `w-`, `h-`, `p-`, `m-`
4. **Typography**: `text-`, `font-`
5. **Visual**: `bg-`, `border-`, `shadow-`
6. **Interactive**: `hover:`, `focus:`, `active:`
7. **Responsive**: `sm:`, `md:`, `lg:`

```vue
<!-- Good -->
<div class="flex items-center justify-between w-full px-4 py-2 bg-surface border-2 border-gray-800 rounded hover:bg-surfaceLight">

<!-- Avoid -->
<div class="hover:bg-surfaceLight px-4 flex border-2 rounded w-full bg-surface items-center border-gray-800 justify-between py-2">
```

### Avoid Inline Styles

Use Tailwind utilities or design tokens instead:

```vue
<!-- ❌ Bad -->
<div style="color: #00ff00; margin: 16px;">

<!-- ✅ Good -->
<div class="text-terminalGreen m-4">
```

### Component Composition

Break down complex UIs into reusable components:

```
src/components/
├── ui/              # Base UI components (buttons, inputs, etc.)
├── common/          # Shared application components
├── layout/          # Layout components
└── [feature]/       # Feature-specific components
```

### Responsive Design

Mobile-first approach using breakpoints:

```vue
<div class="flex flex-col md:flex-row lg:space-x-8">
  <!-- Stacks vertically on mobile, horizontal on tablet+ -->
</div>
```

### Performance

- Use `will-change` sparingly for animated elements
- Prefer CSS transforms over layout properties
- Use `contain` for isolated components

```css
.optimized-animation {
  will-change: transform;
  transform: translateZ(0); /* Force GPU acceleration */
}
```

### Testing

- Verify color contrast with browser DevTools
- Test keyboard navigation (Tab, Enter, Escape)
- Test with screen reader (NVDA, JAWS, VoiceOver)
- Verify responsive breakpoints

---

## Examples

### Complete Login Form

```vue
<template>
  <div class="flex min-h-screen items-center justify-center bg-terminalBackground">
    <div
      class="w-full max-w-sm rounded-lg bg-surface border-2 border-gray-800 p-8 shadow-glow-lg crt-screen"
    >
      <h2 class="mb-6 text-center text-2xl font-bold text-terminalGreen terminal-glow">
        Login
      </h2>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="email" class="block text-sm font-medium text-gray-300 mb-1">
            Email
          </label>
          <input
            type="email"
            id="email"
            v-model="email"
            required
            class="w-full rounded bg-gray-700 text-terminalGreen border-2 border-gray-600 p-2 focus:outline-none focus:border-terminalGreen transition-colors"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-300 mb-1">
            Password
          </label>
          <input
            type="password"
            id="password"
            v-model="password"
            required
            class="w-full rounded bg-gray-700 text-terminalGreen border-2 border-gray-600 p-2 focus:outline-none focus:border-terminalGreen transition-colors"
          />
        </div>
        <button
          type="submit"
          class="w-full rounded bg-terminalGreen px-4 py-2 font-bold text-black hover:bg-terminalGreenLight transition-colors focus:outline-none focus:ring-2 focus:ring-terminalGreen focus:ring-offset-2 focus:ring-offset-black"
        >
          Login
        </button>
      </form>
      <p v-if="error" class="mt-4 text-danger text-sm">{{ error }}</p>
    </div>
  </div>
</template>
```

---

## Resources

- [TailwindCSS v4 Documentation](https://tailwindcss.com/docs/v4-beta)
- [Vue 3 Style Guide](https://vuejs.org/style-guide/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Fallout Wiki](https://fallout.fandom.com/wiki/Pip-Boy) - Inspiration

---

**Questions or suggestions?** Open an issue or submit a pull request!
