import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick, ref } from 'vue'

const motionState = vi.hoisted(() => ({
  value: 'no-preference' as 'no-preference' | 'reduce',
  preference: null as { value: 'no-preference' | 'reduce' } | null,
}))

vi.mock('@vueuse/core', () => ({
  useLocalStorage: <T>(_key: string, defaultValue: T) => ref<T>(defaultValue),
  usePreferredReducedMotion: () => {
    const preference = ref(motionState.value)
    motionState.preference = preference
    return preference
  },
}))

import { useVisualEffects } from '@/core/composables/useVisualEffects'

describe('useVisualEffects', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    motionState.value = 'no-preference'
    motionState.preference = null
  })

  it('should initialize with defaults', () => {
    const { flickering, scanlines, glowIntensity, isGlowEnabled } = useVisualEffects()

    expect(flickering.value).toBe(false)
    expect(scanlines.value).toBe(true)
    expect(glowIntensity.value).toBe('normal')
    expect(isGlowEnabled.value).toBe(true)
  })

  it('toggleFlickering flips the value', () => {
    const { flickering, toggleFlickering } = useVisualEffects()

    toggleFlickering()
    expect(flickering.value).toBe(true)

    toggleFlickering()
    expect(flickering.value).toBe(false)
  })

  it('toggleScanlines flips the value', () => {
    const { scanlines, toggleScanlines } = useVisualEffects()

    toggleScanlines()
    expect(scanlines.value).toBe(false)

    toggleScanlines()
    expect(scanlines.value).toBe(true)
  })

  it('setGlowIntensity changes intensity', () => {
    const { glowIntensity, setGlowIntensity } = useVisualEffects()

    setGlowIntensity('off')
    expect(glowIntensity.value).toBe('off')

    setGlowIntensity('strong')
    expect(glowIntensity.value).toBe('strong')
  })

  it('toggleGlow cycles through intensities', () => {
    const { glowIntensity, toggleGlow } = useVisualEffects()

    expect(glowIntensity.value).toBe('normal')
    toggleGlow()
    expect(glowIntensity.value).toBe('strong')
    toggleGlow()
    expect(glowIntensity.value).toBe('off')
    toggleGlow()
    expect(glowIntensity.value).toBe('subtle')
    toggleGlow()
    expect(glowIntensity.value).toBe('normal')
  })

  it('enableAllEffects sets all to enabled', () => {
    const { flickering, scanlines, glowIntensity, enableAllEffects } = useVisualEffects()

    enableAllEffects()

    expect(flickering.value).toBe(true)
    expect(scanlines.value).toBe(true)
    expect(glowIntensity.value).toBe('normal')
  })

  it('disableAllEffects sets all to disabled', () => {
    const { flickering, scanlines, glowIntensity, isGlowEnabled, disableAllEffects } =
      useVisualEffects()

    disableAllEffects()

    expect(flickering.value).toBe(false)
    expect(scanlines.value).toBe(false)
    expect(glowIntensity.value).toBe('off')
    expect(isGlowEnabled.value).toBe(false)
  })

  it('resetToDefaults reverts to initial defaults', () => {
    const { flickering, scanlines, glowIntensity, resetToDefaults, enableAllEffects } =
      useVisualEffects()

    enableAllEffects()
    resetToDefaults()

    expect(flickering.value).toBe(false)
    expect(scanlines.value).toBe(true)
    expect(glowIntensity.value).toBe('normal')
  })

  it('glowClass returns correct class for each intensity', () => {
    const { glowClass, setGlowIntensity } = useVisualEffects()

    expect(glowClass.value).toBe('terminal-glow')

    setGlowIntensity('subtle')
    expect(glowClass.value).toBe('terminal-glow-subtle')

    setGlowIntensity('strong')
    expect(glowClass.value).toBe('terminal-glow-strong')

    setGlowIntensity('off')
    expect(glowClass.value).toBe('')
  })

  it('currentConfig returns config object matching state', () => {
    const { currentConfig, toggleFlickering, setGlowIntensity } = useVisualEffects()

    toggleFlickering()
    setGlowIntensity('subtle')

    expect(currentConfig.value).toEqual({
      flickering: true,
      scanlines: true,
      glow: 'subtle',
    })
  })

  it('isGlowEnabled is false when glow is off', () => {
    const { isGlowEnabled, setGlowIntensity } = useVisualEffects()

    setGlowIntensity('off')
    expect(isGlowEnabled.value).toBe(false)
  })

  it('stops flickering when reduced motion becomes preferred', async () => {
    vi.useFakeTimers()
    const { flickering, prefersReducedMotion, toggleFlickering } = useVisualEffects()

    try {
      toggleFlickering()
      await nextTick()
      expect(flickering.value).toBe(true)
      expect(vi.getTimerCount()).toBe(1)

      motionState.preference!.value = 'reduce'
      await nextTick()

      expect(prefersReducedMotion.value).toBe(true)
      expect(flickering.value).toBe(false)
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })
})
