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
        500: '#00cc00',
        950: '#004400'
      },
      // Success maps to terminal green (already primary)
      success: {
        50: '#f0fff4',
        500: '#00ff00'
      },
      // Warning uses amber
      warning: {
        50: '#fffbeb',
        500: '#ffaa00'
      },
      // Error uses red
      error: {
        50: '#fef2f2',
        500: '#ff0000'
      },
      // Info uses blue
      info: {
        50: '#eff6ff',
        500: '#00aaff'
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
        'terminal-btn': 'px-4 py-2 border border-[color:--color-theme-primary] text-[color:--color-theme-primary] bg-transparent hover:bg-[color:--color-theme-primary]/10 transition-all cursor-pointer rounded',
        'terminal-input': 'px-4 py-2 border border-[color:--color-theme-primary] bg-black text-[color:--color-theme-primary] rounded focus:outline-none focus:ring-2 focus:ring-[color:--color-theme-primary]/50',
        'terminal-card': 'border border-[color:--color-theme-primary] bg-black/90 rounded shadow-[0_0_10px_var(--color-theme-glow)]'
      })
    }
  }
}
