# UI Component Library

shadcn-vue primitives (Reka UI + Tailwind v4, copy-paste ownership) restyled onto the Fallout terminal CRT theme.

## Overview

Each component lives in its own folder and is imported per file — primitives are **never** globally
registered (generic names like `Button`/`Card` would collide and defeat tree-shaking). The runtime
palette is owned by `core/composables/useTheme.ts`; shadcn's semantic CSS vars alias the repo tokens in
`assets/tailwind.css`, so palette swaps propagate automatically.

## Components

| Folder | Exports |
|---|---|
| `alert/` | `Alert`, `AlertTitle`, `AlertDescription`, `AlertAction`, `alertVariants` |
| `badge/` | `Badge`, `badgeVariants` |
| `button/` | `Button`, `buttonVariants` |
| `card/` | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`, `CardAction` |
| `dialog/` | `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter`, `DialogClose`, `DialogOverlay`, `DialogScrollContent` |
| `input/` | `Input` |
| `label/` | `Label` |
| `progress/` | `Progress` |
| `select/` | `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`, `SelectLabel`, `SelectGroup`, `SelectSeparator`, plus scroll buttons |
| `skeleton/` | `Skeleton` |
| `slider/` | `Slider` |
| `tabs/` | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`, `tabsListVariants` |
| `toast/` | `Toast`, `Toaster` (the repo's bespoke terminal toast, driven by `useToast`) |
| `tooltip/` | `Tooltip`, `TooltipProvider`, `TooltipTrigger`, `TooltipContent` |

`SettingItem.vue` is a small bespoke display composite that lives here alongside the primitives.

Usage:

```vue
<script setup lang="ts">
import { Button } from '@/core/components/ui/button'
import { Card, CardContent } from '@/core/components/ui/card'
</script>
```

## Repo conventions

- **Tooltips** need a `TooltipProvider` ancestor. Wrap a component trigger with
  `TooltipTrigger as-child`; import `Tooltip`, `TooltipContent`, `TooltipProvider`, `TooltipTrigger`
  together.
- **`Progress` owns its fill.** Pass `size` (`xs`/`sm`/`md`), `tone`
  (`default`/`info`/`warning`/`danger`/`success`), an explicit `fill` colour for a dynamic/domain value
  (precedence over `tone`), and `segmented` for decorative terminal divisions. Name the meter with `label`
  (or a fallthrough `aria-label`) and add `value-text` wherever fill length or colour alone would be
  ambiguous. Do **not** reach into `[data-slot='progress-indicator']` or set `--bar-fill` from callers —
  that pattern is retired as callers migrate.
- **Two-segment health bars** use the shared `core/components/common/HealthRadiationBar.vue`.
- **Overlays** (`Dialog`) render through a `Teleport`; tests stub `Teleport` and assert opening via
  `Dialog.props('open')`.
- Design tokens live in `assets/tailwind.css` and `docs/frontend/STYLEGUIDE.md`.

## Adding a component

See the repo overlay skill `.agents/skills/shadcn-vue-repo/SKILL.md` — it covers the CLI invocation, the
mandatory `scripts/shadcn-post-add.mjs` transform (`data-slot` vs `strictTemplates`), the `cn()` /
tailwind-merge extension, and the token bridge.
