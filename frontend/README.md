# Fallout Shelter Frontend 🎮

> **Terminal-themed Vue 3 application with modern tooling**

A retro-futuristic frontend for the Fallout Shelter management game, featuring terminal green aesthetics, CRT effects,
and cutting-edge JavaScript tooling.

## ✨ Tech Stack

### Core Framework

- **Vue 3.5.13** - Composition API with `<script setup>`
- **TypeScript 5.7** - Full type safety
- **Vite (rolldown-vite)** - Ultra-fast dev server with Rolldown bundler
- **Pinia 3.0** - State management
- **Vue Router 4.5** - Client-side routing

### Styling & UI

- **TailwindCSS v4** - With custom `@theme` design system
- **@tailwindcss/vite** - Native Vite integration
- **Custom UI Components** - 8 terminal-themed wrapper components
- **Nuxt UI 3.0** - Component library (optional integration)
- **Heroicons** - Icon library

### Development Tools

- **pnpm 10.26** - Fast, disk-efficient package manager
- **Oxlint** - Blazingly fast linting (replaces ESLint + Prettier)
- **Vitest 2.1** - Unit testing framework
- **vue-tsc** - TypeScript type checking for Vue
- **jsdom** - DOM testing environment

### Design System

- **100+ Design Tokens** - Colors, typography, spacing, shadows
- **Terminal Green Theme** - Fallout-inspired monochrome aesthetic
- **CRT Effects** - Scanlines, flicker, phosphor glow
- **Accessibility** - WCAG 2.1 AA compliant

## 📋 Prerequisites

- **Node.js 22+** (required)
- **pnpm 10.26+** (recommended) or npm

## 🚀 Quick Start

### 1. Install pnpm (if not installed)

```bash
npm install -g pnpm
```

### 2. Install Dependencies

```bash
cd frontend
pnpm install
```

### 3. Start Development Server

```bash
pnpm run dev
```

Visit [http://localhost:5173](http://localhost:5173) to see the app!

## 📜 Available Scripts

```bash
# Development
pnpm run dev          # Start dev server with HMR

# Production
pnpm run build        # Type-check and build for production
pnpm run preview      # Preview production build locally

# Testing
pnpm run test         # Run unit tests with Vitest
pnpm run test -- --watch  # Run tests in watch mode

# Linting
pnpm run lint         # Lint with Oxlint (fast!)
```

## 🎨 UI Component Library

We've built 8 custom terminal-themed UI components in `src/components/ui/`:

| Component     | Description                                   |
|---------------|-----------------------------------------------|
| **UButton**   | Button with 4 variants, 5 sizes, icon support |
| **UInput**    | Input field with label, validation, icons     |
| **UCard**     | Card container with header/footer slots       |
| **UModal**    | Modal dialog with keyboard navigation         |
| **UBadge**    | Badge/tag with semantic colors                |
| **UAlert**    | Alert/notification with dismissible option    |
| **UTooltip**  | Tooltip with 4 positioning options            |
| **UDropdown** | Dropdown menu with click-outside support      |

**Usage Example:**

```vue

<script setup lang="ts">
  import { UButton, UInput, UCard } from '@/components/ui'
  import { PlusIcon } from '@heroicons/vue/24/solid'
</script>

<template>
  <UCard title="Create Vault" glow crt>
    <UInput v-model="vaultNumber" label="Vault Number" type="number" />
    <UButton variant="primary" :icon="PlusIcon" @click="createVault">
      Create Vault
    </UButton>
  </UCard>
</template>
```

See [`src/components/ui/README.md`](./src/components/ui/README.md) for complete component documentation.

## 📐 Design System

Our design system is built with TailwindCSS v4's `@theme` feature. All design tokens are defined in [
`src/assets/tailwind.css`](./src/assets/tailwind.css).

**Key Features:**

- **Terminal Green Palette** - 5 variations (#00ff00 primary)
- **Semantic Colors** - Success, warning, danger, info
- **Resource Colors** - Power, food, water, caps
- **Typography Scale** - 8 sizes from 12px to 36px
- **Spacing System** - 4px base unit (consistent spacing)
- **Special Effects** - Scanlines, flicker, terminal glow, CRT screen

See [`STYLEGUIDE.md`](./STYLEGUIDE.md) for the complete design system documentation.

## 📁 Project Structure

```
frontend/
├── src/
│   ├── assets/              # Styles and static assets
│   │   ├── tailwind.css    # TailwindCSS with @theme tokens
│   │   ├── main.css        # Global styles
│   │   └── base.css        # CSS resets
│   ├── components/
│   │   ├── ui/             # Reusable UI components (8 components)
│   │   ├── common/         # Shared app components
│   │   ├── layout/         # Layout components
│   │   ├── auth/           # Authentication components
│   │   ├── vault/          # Vault management components
│   │   ├── rooms/          # Room building components
│   │   └── chat/           # Dweller chat components
│   ├── composables/        # Vue composables (hooks)
│   ├── models/             # TypeScript models
│   ├── plugins/            # Vue plugins (axios)
│   ├── router/             # Vue Router configuration
│   ├── services/           # API services
│   ├── stores/             # Pinia stores (state management)
│   ├── types/              # TypeScript type definitions
│   ├── views/              # Page components
│   ├── App.vue             # Root component
│   └── main.ts             # Application entry point
├── tests/
│   └── unit/               # Unit tests (88 tests)
├── public/                 # Static files
├── STYLEGUIDE.md          # Design system documentation
├── MIGRATION_GUIDE.md     # VoidZero stack migration guide
├── TEST_COVERAGE.md       # Test suite documentation
├── FRONTEND_IMPROVEMENTS.md  # Recent improvements summary
├── package.json           # Dependencies
├── pnpm-lock.yaml        # Lockfile
├── vite.config.ts        # Vite configuration
├── vitest.config.ts      # Vitest configuration
├── oxlint.json           # Oxlint configuration
├── tsconfig.json         # TypeScript configuration
└── nuxt-ui.config.ts     # Nuxt UI configuration
```

## 🧪 Testing

**Current Status:**

- ✅ **88/88 tests passing**
- ✅ AuthStore tests (21)
- ✅ VaultStore tests (20)
- ✅ Component tests (17)
- ✅ Service tests (18)
- ✅ Router tests (7)

**Run Tests:**

```bash
# Run all tests
pnpm run test

# Watch mode
pnpm run test -- --watch

# With coverage
pnpm run test -- --coverage

# Specific file
pnpm run test tests/unit/stores/auth.test.ts
```

See [`TEST_COVERAGE.md`](./TEST_COVERAGE.md) for detailed test documentation.

## 🛠️ Development

### Recommended IDE Setup

- **[VSCode](https://code.visualstudio.com/)** + *
  *[Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar)**
- Disable Vetur if installed
- Install recommended extensions (see `.vscode/extensions.json`)

### Type Support

TypeScript is fully configured with strict mode. Use `vue-tsc` for type checking:

```bash
pnpm run build  # Runs type-check before build
```

### Adding New Components

1. Create component in appropriate directory
2. Use UI components from `@/components/ui`
3. Follow design tokens from `@theme`
4. Add tests in `tests/unit/components/`
5. Document in component file with JSDoc

**Example:**

```vue

<script setup lang="ts">
  /**
   * VaultCard - Displays vault statistics
   * @component
   */
  import { UCard } from '@/components/ui'

  interface Props {
    vaultNumber: number
    population: number
    happiness: number
  }

  const props = defineProps<Props>()
</script>

<template>
  <UCard :title="`Vault ${vaultNumber}`" glow>
    <p>Population: {{ population }}</p>
    <p>Happiness: {{ happiness }}%</p>
  </UCard>
</template>
```

## 🎯 Code Standards

### Style Guide

- Use Composition API with `<script setup>`
- TypeScript for all new code
- Follow Vue 3 style guide
- Use Oxlint for formatting (auto-formats)
- Components use PascalCase
- Composables start with `use`

### CSS/Styling

- Use TailwindCSS utilities
- Use design tokens from `@theme`
- Avoid inline styles
- No scoped CSS unless necessary
- See [`STYLEGUIDE.md`](./STYLEGUIDE.md)

### State Management

- Use Pinia stores for global state
- Use composables for shared logic
- Keep stores focused (single responsibility)
- Type all store actions/getters

## 🚀 Deployment

### Build for Production

```bash
pnpm run build
```

Output goes to `dist/` directory.

### Preview Production Build

```bash
pnpm run preview
```

### Environment Variables

Create `.env` file for environment-specific config:

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

Access in code:

```ts
const apiUrl = import.meta.env.VITE_API_URL
```

## 📚 Documentation

- **[STYLEGUIDE.md](./STYLEGUIDE.md)** - Complete design system guide
- **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)** - VoidZero stack details
- **[TEST_COVERAGE.md](./TEST_COVERAGE.md)** - Test suite documentation
- **[FRONTEND_IMPROVEMENTS.md](./FRONTEND_IMPROVEMENTS.md)** - Recent enhancements
- **[src/components/ui/README.md](./src/components/ui/README.md)** - UI component API

## 🔧 Troubleshooting

### Common Issues

**Module not found errors:**

```bash
# Clear cache and reinstall
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

**Type errors:**

```bash
# Restart TypeScript server in VSCode
# Cmd/Ctrl + Shift + P -> "TypeScript: Restart TS Server"
```

**Vite not starting:**

```bash
# Check port 5173 is not in use
# Or specify different port
pnpm run dev -- --port 3000
```

**Tailwind classes not working:**

- Verify import order in `main.ts` (tailwind.css first)
- Check `@import "tailwindcss"` is present in `tailwind.css`
- Restart dev server

## 🌟 What Makes This Frontend Special

- ✨ **Modern Tooling** - VoidZero stack (Rolldown, Oxlint, Vitest 2)
- 🎨 **Design System** - 100+ tokens, comprehensive styleguide
- 🧩 **Component Library** - 8 custom terminal-themed components
- ♿ **Accessible** - WCAG 2.1 AA compliant
- 🧪 **Tested** - 88 unit tests with high coverage
- ⚡ **Fast** - Rolldown bundler, instant HMR
- 📱 **Responsive** - Mobile-first approach
- 🎮 **Themed** - Authentic Fallout terminal aesthetic

## 📖 Additional Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Vite Documentation](https://vitejs.dev/)
- [TailwindCSS v4 Beta](https://tailwindcss.com/docs/v4-beta)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Vitest Documentation](https://vitest.dev/)
- [VoidZero Announcement](https://voidzero.dev/)

---

**Built with ❤️ using Vue 3 and terminal green aesthetics** 🟢
