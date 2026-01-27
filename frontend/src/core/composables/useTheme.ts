import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

export type ThemeName = 'fo3' | 'fnv' | 'fo4'

export interface Theme {
  name: ThemeName
  displayName: string
  description: string
  colors: {
    primary: string
    secondary: string
    accent: string
    glow: string
  }
}

/**
 * Theme definitions based on THEMES.md
 * - Fallout 3: Classic Teal Terminal (clean, minimal)
 * - Fallout: New Vegas: Amber Terminal (warm, dusty, analog)
 * - Fallout 4: Modern Green Terminal (high-contrast, institutional, modern)
 */
export const themes: Record<ThemeName, Theme> = {
  fo3: {
    name: 'fo3',
    displayName: 'Fallout 3 — Classic Teal Terminal',
    description: 'Cool teal palette. Cold, utilitarian, institutional.',
    colors: {
      primary: '#00ff9f',
      secondary: '#003322',
      accent: '#00cc88',
      glow: 'rgba(0, 255, 159, 0.3)',
    },
  },
  fnv: {
    name: 'fnv',
    displayName: 'Fallout: New Vegas — Amber Terminal',
    description: 'Warm amber tones. Dusty, analog, worn. Evokes Mojave-era terminals.',
    colors: {
      primary: '#ffb700',
      secondary: '#332200',
      accent: '#ff9900',
      glow: 'rgba(255, 183, 0, 0.3)',
    },
  },
  fo4: {
    name: 'fo4',
    displayName: 'Fallout 4 — Modern Green Terminal',
    description:
      'High-contrast green on black. Clean, modern, rebuilt. Comfortable for long sessions.',
    colors: {
      primary: '#00ff00',
      secondary: '#003300',
      accent: '#00cc00',
      glow: 'rgba(0, 255, 0, 0.3)',
    },
  },
}

/**
 * Composable for managing application theme
 *
 * Provides theme switching functionality with localStorage persistence.
 * Supports 3 themes from THEMES.md: FO3 (teal), FNV (amber), FO4 (green).
 *
 * Themes are purely cosmetic and do not impact gameplay.
 * Theme preference is saved to user profile preferences when available.
 *
 * @example
 * ```ts
 * const { currentTheme, setTheme, availableThemes, loadUserTheme } = useTheme()
 *
 * // Switch to Fallout: New Vegas theme
 * setTheme('fnv')
 *
 * // Load theme from user profile
 * loadUserTheme('fo3')
 *
 * // Get current theme colors
 * const primaryColor = currentTheme.value.colors.primary
 * ```
 */
export function useTheme() {
  // Persist theme selection in localStorage (default: FO4 green for backward compatibility)
  const selectedTheme = useLocalStorage<ThemeName>('theme', 'fo4')

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
   * Load theme from user profile preferences
   * This should be called after user login with their preferred theme
   */
  function loadUserTheme(themeName: ThemeName | undefined) {
    if (themeName && themes[themeName]) {
      setTheme(themeName)
    }
  }

  /**
   * Apply theme colors to CSS custom properties
   * Updates --theme-* variables that control all theme-aware components
   */
  function applyTheme(theme: Theme) {
    if (typeof document === 'undefined') return

    const root = document.documentElement

    // Helper to extract RGB values from hex color
    const hexToRgb = (hex: string): string => {
      const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
      if (!result) return '0, 0, 0'
      return `${parseInt(result[1]!, 16)}, ${parseInt(result[2]!, 16)}, ${parseInt(result[3]!, 16)}`
    }

    // Primary theme variables
    root.style.setProperty('--theme-primary', theme.colors.primary)
    root.style.setProperty('--theme-secondary', theme.colors.secondary)
    root.style.setProperty('--theme-accent', theme.colors.accent)
    root.style.setProperty('--theme-glow', theme.colors.glow)

    // Standard color-theme-* variables (used by most components)
    root.style.setProperty('--color-theme-primary', theme.colors.primary)
    root.style.setProperty('--color-theme-secondary', theme.colors.secondary)
    root.style.setProperty('--color-theme-accent', theme.colors.accent)
    root.style.setProperty('--color-theme-glow', theme.colors.glow)

    // RGB variants for rgba() usage
    root.style.setProperty('--color-theme-primary-rgb', hexToRgb(theme.colors.primary))
    root.style.setProperty('--color-theme-secondary-rgb', hexToRgb(theme.colors.secondary))
    root.style.setProperty('--color-theme-accent-rgb', hexToRgb(theme.colors.accent))

    // Legacy support (some components may still use these)
    root.style.setProperty('--color-primary', theme.colors.primary)
    root.style.setProperty('--color-secondary', theme.colors.secondary)
    root.style.setProperty('--color-accent', theme.colors.accent)
  }

  // Apply theme on initialization
  applyTheme(currentTheme.value)

  return {
    currentTheme,
    availableThemes,
    selectedTheme: computed(() => selectedTheme.value),
    themes,
    setTheme,
    loadUserTheme,
  }
}
