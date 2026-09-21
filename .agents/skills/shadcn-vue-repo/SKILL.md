---
name: shadcn-vue-repo
description: Repo overlay for shadcn-vue — the Fallout CRT token bridge, alias layout, Vite+/pnpm constraints, cn()/tailwind-merge config, and the migration rules for replacing the U* primitives. Complements the upstream `shadcn-vue` skill (generic CLI/registry/component knowledge). Use when adding a shadcn-vue component, migrating a U* primitive, wiring cn()/tailwind-merge, or touching the shadcn variable layer in tailwind.css.
---

# shadcn-vue — repo overlay

> Generic shadcn-vue knowledge (CLI surface, registries, presets, component docs, MCP) lives in the upstream
> **`shadcn-vue`** skill. This skill holds only what is specific to *this* repo.

shadcn-vue is **not a dependency** — components are copied into the repo and owned by us. Built on
[Reka UI](https://reka-ui.com) (headless primitives, successor to radix-vue), Tailwind CSS v4, and
`class-variance-authority`. Canonical repo: `unovue/shadcn-vue` (MIT).

Declared deps of the registry base style: `reka-ui`, `class-variance-authority`, `clsx`, `tailwind-merge`,
`tw-animate-css`, `@lucide/vue`.

## Repo constraints — read first

- **Vite+ (VoidZero) owns the toolchain.** Import JS modules from `vite-plus`, never `vite`. Never install
  `vitest`, `oxlint`, or `oxfmt` directly — Vite+ wraps them.
- **Never let `shadcn-vue init` edit `vite.config.ts` or `package.json` scripts.** It writes `from 'vite'`,
  which breaks the Vite+ build. Hand-apply all alias/config edits. A legacy `vite` → `vite-plus` override
  exists in `frontend/pnpm-workspace.yaml` and the CLI's framework detection may not understand it.
- **pnpm is supply-chain hardened** (`frontend/pnpm-workspace.yaml`): `minimumReleaseAge: 10080` (7-day
  quarantine), `blockExoticSubdeps: true`, `saveExact: true`, and an explicit `allowBuilds` allowlist. Prefer
  editing `frontend/package.json` and running `pnpm install` over letting the CLI `pnpm add`. If a new dep
  carries a build/postinstall script, add it to `allowBuilds`.
- **Alias layout:** primitives live in `frontend/src/core/components/ui/`. `tsconfig.app.json` already maps
  `@/*`, `@/core/*`, `@/modules/*`. `components.json` must set `aliases.ui: "@/core/components/ui"` and
  `aliases.utils: "@/core/utils"`. Note the shadcn CLI may need `baseUrl` added to the tsconfig it reads.
- **Never globally register shadcn primitives.** Generic names (`Button`, `Card`, `Input`) collide and hurt
  tree-shaking — import per file. The legacy `U*` global loop in `main.ts` and `global.d.ts` is deleted as
  primitives migrate; do not add to it.
- **shadcn's `style` / `baseColor` / `cssVariables` are locked at init.** Pick them once; changing later means
  deleting and re-adding components.

## Adding a component

```bash
# from frontend/
pnpm dlx shadcn-vue@latest add <name>
node scripts/shadcn-post-add.mjs   # required — see "Known integration traps"
```

If the CLI fails under pnpm 11 / Vite+ (upstream issues **#1952** devEngines range, **#1933** registry
`target` ignoring `src/`), vendor manually: fetch the component JSON from the shadcn-vue registry, place it
under `src/core/components/ui/<name>/`, and add its declared deps by hand. shadcn is copy-paste by design, so
this loses only dep auto-add and path resolution.

## `cn()` + tailwind-merge (mandatory extension)

`cn()` lives in `src/core/utils/` and **must** extend tailwind-merge with the repo's custom utilities, or
merged classes silently fail to override:

```ts
import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'text-color': [{ text: ['theme-primary', 'theme-secondary', 'theme-accent'] }],
      'bg-color': [{ bg: ['theme-primary', 'theme-secondary', 'theme-accent'] }],
    },
  },
})

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))
```

Without this, a caller's `class="text-theme-primary"` will **not** override a component's internal
`text-foreground` — both classes render and the cascade decides. This is the single most common silent bug in
this migration.

## Token bridge — shadcn vars alias the existing tokens

The app is single-dark CRT with **glow-as-elevation**. shadcn expects semantic OKLCH vars under `:root` +
`.dark`. **Alias; never hard-code** — the runtime palette swap (`core/composables/useTheme.ts`) writes inline
CSS vars on `<html>`, and an alias chain re-resolves automatically on every swap.

| shadcn var | Alias to |
|---|---|
| `--background` | `--color-surface-canvas` |
| `--foreground` | body text token |
| `--card` / `--card-foreground` | `--color-surface` / foreground |
| `--popover` / `--popover-foreground` | `--color-surface-raised` / foreground |
| `--primary` / `--primary-foreground` | `--color-theme-primary` / constant on-primary contrast |
| `--ring` | `--color-theme-primary` |
| `--secondary` / `--muted` | `--color-surface-sunken` |
| `--muted-foreground` | dim text token |
| `--accent` | `--color-surface-hover` ⚠️ **not** `--color-theme-accent` |
| `--destructive` | existing danger token |
| `--border` / `--input` | existing border token |

Guarded traps:

- **`--accent` is a hover *surface*, not the brand accent.** Mapping it to `--color-theme-accent` is a real
  bug. Keep the brand accent as a separate custom var.
- **`useTheme` writes legacy `--color-primary/secondary/accent` inline on `<html>`.** These **collide** with
  shadcn's `@theme inline` names (`bg-primary` / `bg-secondary` would resolve to brand hexes, not semantic
  vars). Delete those three writes; `applyTheme` stays the *only* palette writer.
- **Do not ship shadcn's `@layer base` verbatim.** Drop `body { @apply bg-background text-foreground }` (body
  already carries background, glow, and font) and drop the universal `* { @apply border-border }` — Tailwind
  v4's `border` utility already resolves `--color-border`, and the universal rule repaints the entire app.
  Keep `@custom-variant dark (&:is(.dark *))` — it is inert without a `.dark` element.
- **Map `--shadow-sm/md/lg` to the repo's `--shadow-glow-*`** so shadcn components using `shadow-*` stay
  on-theme; keep the `--glow-0..3` intent ladder intact.
- `--radius`: set to the repo base and override shadcn's derived `--radius-sm/md/lg/xl` with the existing
  `--border-radius-*` values so its `calc()` does not drift.

## Migration rules

- **One primitive + its consumers in one module per PR.** The app must ship after every merge.
- **Characterisation tests before rewriting a primitive:** renders / emits expected events / aria role+name /
  keyboard (Enter/Space/Escape/Tab). **Never assert Tailwind classes** — class assertions encode the old
  implementation and fail on a correct rewrite. Do not bulk-rename classes in old tests either.
- **No facade-forever:** delete the corresponding `U*.vue` when its last consumer migrates.
- **Keep the visual net green:** the dev `ui-catalog` route screenshot + aria snapshots.
- Raw native elements in feature code (`<button>`, `<input>`, `<label>`) are migrated at the call site — the
  a11y payoff is per call site, not automatic.

## Known integration traps (from the Phase 0 spike)

- **`data-slot` vs `strictTemplates` — run the transform after every `add`.** Every shadcn-vue component
  passes `data-slot` to Reka UI's `<Primitive>`, whose `PrimitiveProps` does not declare it. Under this repo's
  `strictTemplates: true` that is a hard `TS2353` on **every** generated component. Module augmentation does
  **not** work — the barrel re-exports `PrimitiveProps` from `dist/index4`, and a bare
  `declare module 'reka-ui'` shadows the whole module. Fix: `node scripts/shadcn-post-add.mjs`, which inserts
  `<!-- @vue-ignore -->` before each component element carrying `data-slot`. Idempotent; `data-slot` still
  reaches the DOM as a fallthrough attribute.
- **`components.json` aliases must be corrected after `init`.** Defaults are `@/components`,
  `@/components/ui`, `@/lib/utils`; this repo needs `@/core/components`, `@/core/components/ui`,
  `@/core/utils/cn`, and `tailwind.css: src/assets/tailwind.css`.
- **`init` injects a Google Fonts `@import` and a global `@layer base` reset** into the configured CSS file.
  Delete both — the repo uses local Courier, and the universal reset repaints the app.
- **`--style` values are `vega|nova|maia|lyra|mira`** — there is no `new-york` / `default`.
- **Pin every prompt** for non-interactive use:
  `init -y --base reka --template vite --style vega -b neutral --icon-library lucide`.
- **The root `tsconfig.json` needs `baseUrl` + `paths`** or `init` fails alias validation (upstream #1761).
- **`iconLibrary: lucide` adds a second icon system** alongside the repo's `@iconify/vue`.

## Verify

```bash
cd frontend && pnpm run lint && pnpm run typecheck && pnpm run test:run
```

Plan and phase detail: `.omo/plans/shadcn-vue-component-library-migration.md`.
