import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'

let mockThemeValue: string = 'fo4'
vi.mock('@vueuse/core', () => ({
  useLocalStorage: <T>(_key: string, defaultValue: T) => {
    const r = ref<T>(mockThemeValue as any || defaultValue)
    return r
  },
}))

import { useTheme } from '@/core/composables/useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockThemeValue = 'fo4'
    // Reset CSS custom properties
    document.documentElement.style.removeProperty('--theme-primary')
    document.documentElement.style.removeProperty('--theme-secondary')
    document.documentElement.style.removeProperty('--theme-accent')
    document.documentElement.style.removeProperty('--theme-glow')
    document.documentElement.style.removeProperty('--color-theme-primary')
    document.documentElement.style.removeProperty('--color-theme-primary-rgb')
  })

  it('should initialize with fo4 theme', () => {
    const { selectedTheme } = useTheme()

    expect(selectedTheme.value).toBe('fo4')
  })

  it('setTheme changes the active theme', () => {
    const { selectedTheme, setTheme } = useTheme()

    setTheme('fnv')

    expect(selectedTheme.value).toBe('fnv')
  })

  it('setTheme applies CSS custom properties to document root', () => {
    const { setTheme } = useTheme()

    setTheme('fo4')

    const primary = document.documentElement.style.getPropertyValue('--theme-primary')
    expect(primary).toBeTruthy()
    expect(primary).toMatch(/^#[0-9a-fA-F]{6}$/)

    const rgb = document.documentElement.style.getPropertyValue('--color-theme-primary-rgb')
    expect(rgb).toMatch(/^\d{1,3},\s*\d{1,3},\s*\d{1,3}$/)
  })

  it('availableThemes returns all theme objects', () => {
    const { availableThemes } = useTheme()

    expect(availableThemes.value.length).toBeGreaterThanOrEqual(3)
    const themeNames = availableThemes.value.map((t: any) => t.name)
    expect(themeNames).toContain('fo4')
    expect(themeNames).toContain('fnv')
  })

  it('currentTheme returns the active theme object', () => {
    const { currentTheme, setTheme } = useTheme()

    expect(currentTheme.value.name).toBe('fo4')

    setTheme('fnv')
    expect(currentTheme.value.name).toBe('fnv')
  })

  it('loadUserTheme with valid theme sets it', () => {
    const { selectedTheme, loadUserTheme } = useTheme()

    loadUserTheme('fnv')

    expect(selectedTheme.value).toBe('fnv')
  })

  it('loadUserTheme with undefined does not change theme', () => {
    const { selectedTheme, loadUserTheme } = useTheme()

    loadUserTheme(undefined)

    expect(selectedTheme.value).toBe('fo4')
  })

  it('applyTheme sets all CSS custom properties', () => {
    const { setTheme } = useTheme()

    setTheme('fnv')

    const root = document.documentElement
    expect(root.style.getPropertyValue('--theme-primary')).toBeTruthy()
    expect(root.style.getPropertyValue('--theme-secondary')).toBeTruthy()
    expect(root.style.getPropertyValue('--theme-accent')).toBeTruthy()
    expect(root.style.getPropertyValue('--theme-glow')).toBeTruthy()
    expect(root.style.getPropertyValue('--color-theme-primary')).toBeTruthy()
    expect(root.style.getPropertyValue('--color-theme-secondary')).toBeTruthy()
    expect(root.style.getPropertyValue('--color-theme-accent')).toBeTruthy()
    expect(root.style.getPropertyValue('--color-theme-glow')).toBeTruthy()
    expect(root.style.getPropertyValue('--color-theme-primary-rgb')).toBeTruthy()
  })
})
