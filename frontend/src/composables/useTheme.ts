import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

export type ThemeName = 'classic' | 'fo3' | 'fnv' | 'fo4'

export interface Theme {
  name: ThemeName
  displayName: string
  colors: {
    primary: string
    secondary: string
    background: string
    text: string
    accent: string
  }
}

/**
 * Theme definitions for different Fallout games
 */
export const themes: Record<ThemeName, Theme> = {
  classic: {
    name: 'classic',
    displayName: 'Classic Terminal',
    colors: {
      primary: '#00ff00', // Terminal green
      secondary: '#003300',
      background: '#000000',
      text: '#00ff00',
      accent: '#00cc00'
    }
  },
  fo3: {
    name: 'fo3',
    displayName: 'Fallout 3 (Metro)',
    colors: {
      primary: '#ffb700', // Amber/yellow
      secondary: '#332200',
      background: '#0a0a0a',
      text: '#ffb700',
      accent: '#ff9900'
    }
  },
  fnv: {
    name: 'fnv',
    displayName: 'Fallout: New Vegas',
    colors: {
      primary: '#ff6600', // Orange/desert
      secondary: '#331100',
      background: '#0a0a0a',
      text: '#ff6600',
      accent: '#ff8800'
    }
  },
  fo4: {
    name: 'fo4',
    displayName: 'Fallout 4 (Pip-Boy)',
    colors: {
      primary: '#00ff9f', // Blue-green
      secondary: '#003322',
      background: '#000000',
      text: '#00ff9f',
      accent: '#00cc88'
    }
  }
}

/**
 * Composable for managing application theme
 *
 * Provides theme switching functionality with localStorage persistence.
 * Currently only 'classic' theme is implemented, but the infrastructure
 * supports FO3, FNV, and FO4 themes for future development.
 *
 * @example
 * ```ts
 * const { currentTheme, setTheme, availableThemes } = useTheme()
 *
 * // Switch to Fallout 3 theme (when implemented)
 * setTheme('fo3')
 *
 * // Get current theme colors
 * const primaryColor = currentTheme.value.colors.primary
 * ```
 */
export function useTheme() {
  // Persist theme selection in localStorage
  const selectedTheme = useLocalStorage<ThemeName>('theme', 'classic')

  // Current theme object
  const currentTheme = computed(() => themes[selectedTheme.value])

  // List of available themes
  const availableThemes = computed(() => Object.values(themes))

  /**
   * Switch to a different theme
   */
  function setTheme(themeName: ThemeName) {
    selectedTheme.value = themeName
    applyTheme(themes[themeName])
  }

  /**
   * Apply theme colors to CSS variables
   */
  function applyTheme(theme: Theme) {
    if (typeof document === 'undefined') return

    const root = document.documentElement
    root.style.setProperty('--color-primary', theme.colors.primary)
    root.style.setProperty('--color-secondary', theme.colors.secondary)
    root.style.setProperty('--color-background', theme.colors.background)
    root.style.setProperty('--color-text', theme.colors.text)
    root.style.setProperty('--color-accent', theme.colors.accent)
  }

  // Apply theme on initialization
  applyTheme(currentTheme.value)

  return {
    currentTheme,
    availableThemes,
    selectedTheme: computed(() => selectedTheme.value),
    setTheme
  }
}
