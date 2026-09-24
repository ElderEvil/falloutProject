import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// The repo's design tokens are custom utilities (`text-theme-primary`, `bg-theme-primary`,
// `border-theme-primary`, `shadow-glow-*`). tailwind-merge only knows its default config, so
// without these registrations a caller's token class would NOT override a component's internal
// class (e.g. `text-foreground`) — both would render and the cascade would decide.
// See `.agents/skills/shadcn-vue-repo/SKILL.md` (§cn + tailwind-merge).
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'text-color': [{ text: ['theme-primary', 'theme-secondary', 'theme-accent'] }],
      'bg-color': [{ bg: ['theme-primary', 'theme-secondary', 'theme-accent'] }],
      'border-color': [{ border: ['theme-primary', 'theme-secondary', 'theme-accent'] }],
      shadow: [{ shadow: ['glow-sm', 'glow-md', 'glow-lg'] }],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
