# Frontend Accessibility Policy

## Commitment and scope

The frontend targets **WCAG 2.2 Level AA**. WCAG 2.2 AA includes the WCAG 2.1 AA success criteria and adds useful
requirements for focus visibility, pointer target size, dragging alternatives, and accessible authentication.

This is an engineering target, not a blanket conformance claim. A release or the application may be described as
conformant only after every supported route, state, and user journey has been manually assessed and the results are
recorded. See the [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) and
[what changed in 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/).

Accessibility applies to authenticated and unauthenticated UI, including loading, empty, error, disabled, modal,
and mobile states. It is a feature-quality requirement, not a visual-polish follow-up.

## Implementation rules

- Start with native semantics: use `<button>` for actions, `<a>`/`RouterLink` for navigation, and actual form
  controls for input. Do not make a `div`, `span`, `li`, or generic `UCard` interactive with `@click`.
- Do not use `tabindex="0"`, a role, and keyboard-event handlers to recreate a native control unless no semantic
  element can represent the interaction. Document the reason when that exceptional pattern is necessary.
- Every control needs a visible label or an accessible name. Icon-only controls always need an accessible name.
  Labels, hints, and errors must remain programmatically associated with their controls.
- Keep a visible, high-contrast focus indicator and a logical tab order. Modals, menus, and popovers must support
  Escape where appropriate, retain focus while open, and return focus to the invoking control when closed. Prefer
  the shared `UModal` primitive over a one-off dialog.
- Information required to play must not rely only on color, iconography, hover, sound, flicker, or motion. Tooltips
  elaborate on visible information; they do not supply the only way to learn it.
- Test contrast against the *computed* foreground and background for every supported theme and surface. Normal text
  needs 4.5:1; large text and meaningful control boundaries/focus indicators need 3:1. `#00ff00` on black is about
  15.3:1, not 21:1; opacity-based muted text needs separate verification.
- Respect `prefers-reduced-motion`. CRT flicker, pulsing, spinning, transitions, and scanline effects must stop or
  become non-essential under that preference. Do not introduce flashing that could trigger a seizure.
- Meet the WCAG 2.2 AA 24 by 24 CSS-pixel pointer-target minimum, or its spacing exception, for controls that are
  not inline text. Larger targets are preferable for consequential actions.

The [style guide](./STYLEGUIDE.md#accessibility) defines the terminal-theme implementation details, including
tooltips and visual tokens. This document defines the acceptance policy.

## Verification layers

No single tool can certify WCAG AA. Use all of these layers for every user-facing change.

| Layer | Required use | What it catches |
| ----- | ------------ | --------------- |
| Vue template lint | Add and run a dedicated ESLint `lint:a11y` command using `eslint-plugin-vuejs-accessibility`. Keep Vite+/Oxlint as the existing general lint command. | Template-level labels, alternate text, ARIA validity, positive tabindex, and static elements made interactive. |
| Rendered-DOM tests | Add `@axe-core/playwright` checks to representative unauthenticated and authenticated critical journeys. Run WCAG 2.1/2.2 A and AA tags in CI. | Rendered names, roles, contrast, duplicate IDs, and many invalid ARIA combinations. |
| Keyboard tests | Use Playwright to exercise Tab/Shift+Tab, Enter, Space, Escape, focus trapping, and focus return for every new composite interaction. | Broken keyboard paths and modal/menu behavior that static checks miss. |
| Manual review | For touched UI, check keyboard-only use, 200% zoom and 320 CSS-pixel reflow, reduced motion, all themes, and a screen-reader pass for significant journeys. | Reading order, meaningful labels, motion, zoom/reflow, and interaction quality that automation cannot decide. |

Automated tests should not use broad `axe` exclusions. A narrow, documented exception needs an owner, rationale, and
removal issue. New violations fail CI; existing baseline issues are tracked and reduced deliberately.

## Tooling decision

Do **not** add an Oxc/Oxlint JSX accessibility plugin for this Vue application. Oxlint's `jsx-a11y` rules target JSX,
and Oxlint does not parse Vue template syntax sufficiently for template-aware accessibility analysis. A custom Oxc
plugin would inherit that limitation and create an unnecessary maintenance surface. See the
[Oxlint plugin list](https://oxc.rs/docs/guide/usage/linter/plugins) and its
[Vue-template limitation](https://oxc.rs/docs/guide/usage/linter/rules/typescript/consistent-type-imports.html).

Instead, retain `pnpm run lint` for fast general linting and introduce a focused, separately configured ESLint
command for `.vue` accessibility rules. `eslint-plugin-vuejs-accessibility` is designed for Vue templates and has a
[recommended flat configuration](https://vue-a11y.github.io/eslint-plugin-vuejs-accessibility/). This addition must
be accompanied by its lockfile update, a `lint:a11y` package script, and CI wiring; this policy does not silently add
those dependencies.

For browser checks, use Playwright's documented `@axe-core/playwright` integration with the tags `wcag2a`,
`wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22a`, and `wcag22aa`. Axe finds important defects, but Playwright explicitly
recommends combining it with manual and inclusive-user assessment.

## Shared-primitives-first rollout

1. Audit and fix shared controls before individual pages: `UButton`, `UInput`, `USelect`, `UModal`, toast/alert,
   tooltip/popover, tabs, navigation, and cards.
2. Establish a baseline by route and state. Prioritize keyboard blockers, missing names/labels, modal behavior,
   contrast, essential information available only by hover/color, and motion.
3. Add axe and keyboard tests for one critical journey at a time. Cover authentication, vault navigation, room/build
   actions, forms, progression/reward modals, and destructive operations first.
4. Make accessibility work part of normal feature delivery: new UI ships with its semantic structure, automated
   coverage, and manual check—not with a deferred accessibility ticket.

## Agent guidance

Create a small local `frontend-accessibility` agent skill when this policy is put into enforcement. It should link
here and to the style guide, require the implementation and verification rules above, and tell agents to reuse shared
primitives. It must not be treated as a conformance certificate or duplicate the complete WCAG standard.

## Current known follow-ups

- Replace clickable static elements and clickable `UCard` usage with semantic controls.
- Apply reduced-motion handling consistently to CRT effects, not only selected animation utilities.
- Replace native `title` hints as components are touched; they are not a reliable accessible tooltip mechanism.
- Recheck all dynamic theme colors, alpha-muted text, borders, and focus rings using their actual composited
  backgrounds.
- Audit custom dialogs and overlays; migrate them to `UModal` or match its focus, Escape, and return-focus behavior.
