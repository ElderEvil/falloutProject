/**
 * Nuxt UI Configuration for Standalone Vue 3
 *
 * This configuration integrates Nuxt UI with the Fallout Shelter terminal theme.
 * Custom theming is handled via Tailwind v4 @theme in src/assets/tailwind.css
 *
 * Key Nuxt UI v4 patterns:
 * - <UApp> wrapper required for Toast, Tooltip, overlays
 * - @import '@nuxt/ui' in tailwind.css for UI styles
 * - Semantic colors: primary, secondary, success, error, warning, info, neutral
 * - Tailwind Variants for type-safe component styling
 */

export default {
  // Nuxt UI theme configuration
  theme: {
    // Terminal green as primary color - integrates with CSS vars
    colors: {
      primary: {
        50: '#f0fff4',
        100: '#c6f6d5',
        200: '#9ae6b4',
        300: '#68d391',
        400: '#48bb78',
        500: '#00ff00', // Terminal green (maps to --color-theme-primary)
        600: '#00cc00',
        700: '#00aa00',
        800: '#008800',
        900: '#006600',
        950: '#004400'
      },
      // Secondary uses theme-accent
      secondary: {
        50: '#f0fff4',
        100: '#c6f6d5',
        200: '#9ae6b4',
        300: '#68d391',
        400: '#48bb78',
        500: '#00cc00',
        600: '#00aa00',
        700: '#008800',
        800: '#006600',
        900: '#004400',
        950: '#003300'
      },
      // Success maps to terminal green (already primary)
      success: {
        50: '#f0fff4',
        100: '#dcfce7',
        200: '#bbf7d0',
        300: '#86efac',
        400: '#4ade80',
        500: '#22c55e',
        600: '#16a34a',
        700: '#15803d',
        800: '#166534',
        900: '#14532d',
        950: '#052e16'
      },
      // Warning uses amber
      warning: {
        50: '#fffbeb',
        100: '#fef3c7',
        200: '#fde68a',
        300: '#fcd34d',
        400: '#fbbf24',
        500: '#f59e0b',
        600: '#d97706',
        700: '#b45309',
        800: '#92400e',
        900: '#78350f',
        950: '#451a03'
      },
      // Error uses red
      error: {
        50: '#fef2f2',
        100: '#fee2e2',
        200: '#fecaca',
        300: '#fca5a5',
        400: '#f87171',
        500: '#ef4444',
        600: '#dc2626',
        700: '#b91c1c',
        800: '#991b1b',
        900: '#7f1d1d',
        950: '#450a0a'
      },
      // Info uses blue
      info: {
        50: '#eff6ff',
        100: '#dbeafe',
        200: '#bfdbfe',
        300: '#93c5fd',
        400: '#60a5fa',
        500: '#3b82f6',
        600: '#2563eb',
        700: '#1d4ed8',
        800: '#1e40af',
        900: '#1e3a8a',
        950: '#172554'
      }
    },
    // Letter spacing
    letterSpacing: {
      tighter: '-0.05em',
      tight: '-0.025em',
      normal: '0',
      wide: '0.025em',
      wider: '0.05em',
      widest: '0.1em'
    }
  },

  // Component defaults for terminal theme consistency
  components: {
    Button: {
      default: {
        color: 'primary',
        variant: 'solid'
      }
    },
    Input: {
      default: {
        color: 'primary',
        variant: 'outline'
      }
    },
    Card: {
      default: {
        color: 'primary'
      }
    }
  },

  // Hook into Nuxt UI's theming
  hooks: {
    // Register custom shortcuts for terminal theme
    'shortcuts:register'(shortcuts: Record<string, string>) {
      Object.assign(shortcuts, {
        'terminal-btn': 'px-4 py-2 border border-[var(--color-theme-primary)] text-[var(--color-theme-primary)] bg-transparent hover:bg-[var(--color-theme-primary)]/10 transition-all cursor-pointer rounded',
        'terminal-input': 'px-4 py-2 border border-[var(--color-theme-primary)] bg-black text-[var(--color-theme-primary)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)]/50',
        'terminal-card': 'border border-[var(--color-theme-primary)] bg-black/90 rounded shadow-[0_0_10px_var(--color-theme-glow)]'
      })
    }
  }
}
