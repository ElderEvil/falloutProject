# Fallout Shelter Frontend 🎮

> **Terminal-themed Vue 3 application with modern tooling - v2.11**

A retro-futuristic frontend for the Fallout Shelter management game, featuring terminal aesthetics, CRT effects,
and cutting-edge JavaScript tooling.

## ✨ Tech Stack

### Core Framework

- **Vue 3.5.29** - Composition API with `<script setup>`
- **TypeScript 5.9** - Full type safety
- **Vite+** - Unified toolchain (Vite 8 + Vitest 4.1 + Rolldown bundler)
- **Pinia 3.0** - State management
- **Vue Router 4.6** - Client-side routing

### Styling & UI

- **TailwindCSS v4** - With custom `@theme` design system
- **@tailwindcss/vite** - Native Vite integration
- **Custom UI Components** - 8 terminal-themed wrapper components
- **Nuxt UI 4.5** - Component library (optional integration)
- **Heroicons** - Icon library

### Development Tools

- **pnpm 10.28** - Fast, disk-efficient package manager
- **Vite+** - Unified toolchain for dev, build, test, lint, format (via pnpm scripts)
- **Oxlint/Oxfmt** - Blazingly fast linting and formatting (via Vite+)
- **vue-tsc** - TypeScript type checking for Vue
- **jsdom** - DOM testing environment

### Design System

- **100+ Design Tokens** - Colors, typography, spacing, shadows
- **Terminal Green/Amber/Tile Themes** - Fallout-inspired monochrome aesthetic
- **CRT Effects** - Scanlines, flicker, phosphor glow
- **Accessibility** - WCAG 2.1 AA compliant

## 📋 Prerequisites

- **Node.js 22+** (required)
- **pnpm 10.28+** (required)

## 🔧 Vite+ Toolchain

This project uses [Vite+](https://viteplus.dev/), a unified toolchain built on Vite, Rolldown, Vitest, Oxlint, Oxfmt, and Vite Task.

### Two Ways to Use Vite+

**Option 1: pnpm scripts (no global installation)**

Works out of the box - Vite+ is included as a project dependency:

```bash
pnpm run dev          # Start development server
pnpm run build        # Build for production
pnpm run test         # Run tests
pnpm run lint         # Lint code
pnpm run format       # Format code
pnpm run typecheck    # TypeScript check
```

**Option 2: Global Vite+ CLI**

Install once, use `vp` commands everywhere:

```bash
# Install globally (one-time setup)
curl -fsSL https://viteplus.dev/install.sh | sh

# Restart your shell or run:
source ~/.bashrc  # or ~/.zshrc, ~/.config/fish/config.fish

# Then use directly:
vp dev              # Start development server
vp build            # Build for production
vp test             # Run tests
vp lint              # Lint code
vp fmt               # Format code
vp check             # Run format, lint, and typecheck
```

### Vite+ Features

| Command | Description |
|---------|-------------|
| `vp dev` | Development server with HMR |
| `vp build` | Production build (uses Rolldown) |
| `vp test` | Run tests with Vitest |
| `vp lint` | Lint with Oxlint |
| `vp fmt` | Format with Oxfmt |
| `vp check` | Run format check, lint, and TypeScript |
| `vp install` | Install dependencies (wraps pnpm/npm/yarn) |
| `vp add <pkg>` | Add package to dependencies |
| `vp run <script>` | Run a package.json script |
| `vp preview` | Preview production build locally |

### Bundled Tools

Vite+ bundles these tools - no separate installation needed:

- **Vite 8** - Next-gen frontend tooling
- **Rolldown** - Ultra-fast bundler (replaces Rollup)
- **Vitest 4.1+** - Unit testing framework
- **Oxlint** - Fast linter (ESLint replacement)
- **Oxfmt** - Code formatter (Prettier replacement)

### Important Notes

- Import from `vite-plus` in config files: `import { defineConfig } from 'vite-plus'`
- Don't install `vitest`, `oxlint`, or `oxfmt` separately
- The npm package `vite-plus` provides the local `vp` wrapper

See [`AGENTS.md`](./AGENTS.md) for Vite+ development guidelines.

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

All commands use the Vite+ unified CLI (`vp`):

```bash
# Development
pnpm run dev          # Start dev server with HMR (vp dev)

# Production
pnpm run build        # Build for production (vp build)
pnpm run preview      # Preview production build locally

# Testing
pnpm run test         # Run tests (vp test)
pnpm run test:run     # Run tests once

# Code Quality
pnpm run lint         # Lint with Oxlint (vp lint)
pnpm run lint:fix     # Fix linting issues
pnpm run format       # Format with Oxfmt (vp fmt)
pnpm run typecheck    # TypeScript check (vue-tsc)
```

## 🎨 UI Component Library

We've built 8 custom terminal-themed UI components in `src/components/ui/`:

| Component     | Description                                   |
| ------------- | --------------------------------------------- |
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
    <UButton variant="primary" :icon="PlusIcon" @click="createVault"> Create Vault </UButton>
  </UCard>
</template>
```

See [`src/components/ui/README.md`](./src/components/ui/README.md) for complete component documentation.

## 📐 Design System

Our design system is built with TailwindCSS v4's `@theme` feature. All design tokens are defined in [
`src/assets/tailwind.css`](./src/assets/tailwind.css).

**Key Features:**

- **Terminal Green/Amber/Teal Palette** - Dynamic theme colors controlled via CSS variables (`--theme-primary`, `--theme-secondary`, `--theme-accent`, `--theme-glow`). Terminal Green (#00ff00), Amber (#ffb000), and Teal (#00d9ff) variants are available. Switch themes by updating these CSS variables or toggling a theme class. See [`STYLEGUIDE.md`](./STYLEGUIDE.md) for complete palette documentation and theme switching examples.
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
│   └── unit/               # Unit tests (843 tests)
├── public/                 # Static files
├── STYLEGUIDE.md          # Design system documentation
├── MIGRATION_GUIDE.md     # Vite+ migration guide
├── TEST_COVERAGE.md       # Test suite documentation
├── FRONTEND_IMPROVEMENTS.md  # Recent improvements summary
├── package.json           # Dependencies
├── pnpm-lock.yaml        # Lockfile
├── vite.config.ts        # Vite+ configuration
├── vitest.config.ts      # Vitest configuration
├── oxlint.json           # Oxlint configuration
├── tsconfig.json         # TypeScript configuration
└── nuxt-ui.config.ts     # Nuxt UI configuration
```

## 🧪 Testing

**Current Status:**

- ✅ **843 tests passing**
- ✅ AuthStore tests (21)
- ✅ VaultStore tests (20)
- ✅ Component tests (17)
- ✅ Service tests (18)
- ✅ Router tests (7)

**Run Tests:**

```bash
# Run all tests (via Vite+)
pnpm run test
# or
vp test

# Run once
pnpm run test:run

# Watch mode
pnpm run test -- --watch

# Specific file
pnpm run test tests/unit/stores/auth.test.ts
```

See [`TEST_COVERAGE.md`](./TEST_COVERAGE.md) for detailed test documentation.

## 🛠️ Development

### Recommended IDE Setup

- **[VSCode](https://code.visualstudio.com/)** + **[Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar)**
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
- Use Oxfmt for formatting (via Vite+)
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
- **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)** - Vite+ migration details
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

**Vite+ not starting:**

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

- ✨ **Vite+ Toolchain** - Unified dev, build, test, lint in one CLI
- 🎨 **Design System** - 100+ tokens, comprehensive styleguide
- 🧩 **Component Library** - 8 custom terminal-themed components
- ♿ **Accessible** - WCAG 2.1 AA compliant
- 🧪 **Tested** - 843 unit tests with high coverage
- ⚡ **Fast** - Rolldown bundler, instant HMR
- 📱 **Responsive** - Mobile-first approach
- 🎮 **Themed** - Authentic Fallout terminal aesthetic

## 📖 Additional Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Vite+ Documentation](https://viteplus.dev/)
- [TailwindCSS v4](https://tailwindcss.com/docs/v4-beta)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Vitest Documentation](https://vitest.dev/)

---

**Built with ❤️ using Vue 3 and terminal aesthetics** 🟢
