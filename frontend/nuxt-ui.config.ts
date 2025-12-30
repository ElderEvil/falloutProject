/**
 * Nuxt UI Configuration for Standalone Vue 3
 *
 * This configuration allows using Nuxt UI components in a Vue 3 app
 * without Nuxt.js. Custom theming is handled via Tailwind v4 @theme
 * in src/assets/tailwind.css
 *
 * Note: We've created custom wrapper components in src/components/ui/
 * that provide a terminal-themed interface while maintaining flexibility
 * to use Nuxt UI components directly if needed.
 */

export default {
  // Nuxt UI components configuration
  theme: {
    // Terminal green as primary color
    colors: {
      primary: {
        50: '#f0fff4',
        100: '#c6f6d5',
        200: '#9ae6b4',
        300: '#68d391',
        400: '#48bb78',
        500: '#00ff00', // Terminal green
        600: '#00cc00',
        700: '#00aa00',
        800: '#008800',
        900: '#006600'
      }
    }
  },

  // Component defaults (optional)
  components: {
    button: {
      default: {
        color: 'primary',
        variant: 'solid'
      }
    },
    input: {
      default: {
        color: 'primary',
        variant: 'outline'
      }
    }
  }
}
