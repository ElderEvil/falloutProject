import { computed, ref, watch, onScopeDispose } from 'vue'
import { useLocalStorage } from '@vueuse/core'

export type EffectIntensity = 'off' | 'subtle' | 'normal' | 'strong'

export interface VisualEffectsConfig {
  flickering: boolean
  scanlines: boolean
  glow: EffectIntensity
}

/**
 * Composable for managing visual effects (CRT/terminal aesthetics)
 *
 * Provides configuration for:
 * - Flickering animation (screen flicker effect)
 * - Scanlines overlay (horizontal line pattern)
 * - Glow effects (text/element glow intensity)
 *
 * All settings are persisted to localStorage and can be disabled
 * for accessibility or performance reasons.
 *
 * @example
 * ```ts
 * const { flickering, scanlines, glow, toggleFlickering, setGlowIntensity } = useVisualEffects()
 *
 * // Toggle effects
 * toggleFlickering()
 * toggleScanlines()
 *
 * // Set glow intensity
 * setGlowIntensity('subtle')
 * ```
 */
export function useVisualEffects() {
  // Persist settings in localStorage - flickering OFF by default (was too distracting)
  const flickering = useLocalStorage('visual-effects:flickering', false)
  const scanlines = useLocalStorage('visual-effects:scanlines', true)
  const glowIntensity = useLocalStorage<EffectIntensity>('visual-effects:glow', 'normal')

  // Computed for easy binding
  const isFlickeringEnabled = computed(() => flickering.value)
  const areScanlinesEnabled = computed(() => scanlines.value)
  const isGlowEnabled = computed(() => glowIntensity.value !== 'off')

  /**
   * Toggle flickering effect on/off
   */
  function toggleFlickering() {
    flickering.value = !flickering.value
  }

  /**
   * Toggle scanlines overlay on/off
   */
  function toggleScanlines() {
    scanlines.value = !scanlines.value
  }

  /**
   * Set glow effect intensity
   * @param intensity - 'off', 'subtle', 'normal', or 'strong'
   */
  function setGlowIntensity(intensity: EffectIntensity) {
    glowIntensity.value = intensity
  }

  /**
   * Toggle glow effect (cycles through intensities)
   */
  function toggleGlow() {
    const intensities: EffectIntensity[] = ['off', 'subtle', 'normal', 'strong']
    const currentIndex = intensities.indexOf(glowIntensity.value)
    const nextIndex = (currentIndex + 1) % intensities.length
    glowIntensity.value = intensities[nextIndex]
  }

  /**
   * Enable all effects with normal intensity
   */
  function enableAllEffects() {
    flickering.value = true
    scanlines.value = true
    glowIntensity.value = 'normal'
  }

  /**
   * Disable all effects (accessibility mode)
   */
  function disableAllEffects() {
    flickering.value = false
    scanlines.value = false
    glowIntensity.value = 'off'
  }

  /**
   * Reset to default settings
   */
  function resetToDefaults() {
    flickering.value = false
    scanlines.value = true
    glowIntensity.value = 'normal'
  }

  /**
   * Get current configuration as object
   */
  const currentConfig = computed<VisualEffectsConfig>(() => ({
    flickering: flickering.value,
    scanlines: scanlines.value,
    glow: glowIntensity.value,
  }))

  /**
   * Get CSS class for glow intensity
   */
  const glowClass = computed(() => {
    if (glowIntensity.value === 'off') return ''
    if (glowIntensity.value === 'subtle') return 'terminal-glow-subtle'
    if (glowIntensity.value === 'strong') return 'terminal-glow-strong'
    return 'terminal-glow'
  })

  /**
   * Random flicker effect using JavaScript for more unpredictability
   * This creates truly random opacity changes that CSS animations can't achieve
   */
  const flickerOpacity = ref(1)
  let flickerTimeout: ReturnType<typeof setTimeout> | null = null

  function startRandomFlicker() {
    if (flickerTimeout) {
      clearTimeout(flickerTimeout)
      flickerTimeout = null
    }
    const runFlicker = () => {
      const random = Math.random()
      if (random > 0.97) {
        flickerOpacity.value = 0.93 + Math.random() * 0.04
      } else if (random > 0.92) {
        flickerOpacity.value = 0.9 + Math.random() * 0.05
      } else {
        flickerOpacity.value = 0.97 + Math.random() * 0.03
      }
      // Schedule next flicker with new random delay
      flickerTimeout = setTimeout(runFlicker, 1500 + Math.random() * 2000)
    }
    flickerTimeout = setTimeout(runFlicker, 1500 + Math.random() * 2000)
  }

  function stopRandomFlicker() {
    if (flickerTimeout) {
      clearTimeout(flickerTimeout)
      flickerTimeout = null
    }
    flickerOpacity.value = 1
  }

  // Watch flickering state and start/stop accordingly
  watch(
    flickering,
    (enabled) => {
      if (enabled) {
        startRandomFlicker()
      } else {
        stopRandomFlicker()
      }
    },
    { immediate: true }
  )

  // Cleanup on scope dispose
  onScopeDispose(() => {
    stopRandomFlicker()
  })

  return {
    // State
    flickering: isFlickeringEnabled,
    scanlines: areScanlinesEnabled,
    glowIntensity: computed(() => glowIntensity.value),
    isGlowEnabled,
    currentConfig,
    glowClass,
    flickerOpacity,

    // Actions
    toggleFlickering,
    toggleScanlines,
    setGlowIntensity,
    toggleGlow,
    enableAllEffects,
    disableAllEffects,
    resetToDefaults,
  }
}
