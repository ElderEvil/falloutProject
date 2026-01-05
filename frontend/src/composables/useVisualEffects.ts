import { computed } from 'vue';
import { useLocalStorage } from '@vueuse/core';

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
  // Persist settings in localStorage with sensible defaults
  const flickering = useLocalStorage('visual-effects:flickering', true);
  const scanlines = useLocalStorage('visual-effects:scanlines', true);
  const glowIntensity = useLocalStorage<EffectIntensity>('visual-effects:glow', 'normal');

  // Computed for easy binding
  const isFlickeringEnabled = computed(() => flickering.value);
  const areScanlinesEnabled = computed(() => scanlines.value);
  const isGlowEnabled = computed(() => glowIntensity.value !== 'off');

  /**
   * Toggle flickering effect on/off
   */
  function toggleFlickering() {
    flickering.value = !flickering.value;
  }

  /**
   * Toggle scanlines overlay on/off
   */
  function toggleScanlines() {
    scanlines.value = !scanlines.value;
  }

  /**
   * Set glow effect intensity
   * @param intensity - 'off', 'subtle', 'normal', or 'strong'
   */
  function setGlowIntensity(intensity: EffectIntensity) {
    glowIntensity.value = intensity;
  }

  /**
   * Toggle glow effect (cycles through intensities)
   */
  function toggleGlow() {
    const intensities: EffectIntensity[] = ['off', 'subtle', 'normal', 'strong'];
    const currentIndex = intensities.indexOf(glowIntensity.value);
    const nextIndex = (currentIndex + 1) % intensities.length;
    glowIntensity.value = intensities[nextIndex];
  }

  /**
   * Enable all effects with normal intensity
   */
  function enableAllEffects() {
    flickering.value = true;
    scanlines.value = true;
    glowIntensity.value = 'normal';
  }

  /**
   * Disable all effects (accessibility mode)
   */
  function disableAllEffects() {
    flickering.value = false;
    scanlines.value = false;
    glowIntensity.value = 'off';
  }

  /**
   * Reset to default settings
   */
  function resetToDefaults() {
    flickering.value = true;
    scanlines.value = true;
    glowIntensity.value = 'normal';
  }

  /**
   * Get current configuration as object
   */
  const currentConfig = computed<VisualEffectsConfig>(() => ({
    flickering: flickering.value,
    scanlines: scanlines.value,
    glow: glowIntensity.value
  }));

  /**
   * Get CSS class for glow intensity
   */
  const glowClass = computed(() => {
    if (glowIntensity.value === 'off') return '';
    if (glowIntensity.value === 'subtle') return 'terminal-glow-subtle';
    if (glowIntensity.value === 'strong') return 'terminal-glow-strong';
    return 'terminal-glow';
  });

  return {
    // State
    flickering: isFlickeringEnabled,
    scanlines: areScanlinesEnabled,
    glowIntensity: computed(() => glowIntensity.value),
    isGlowEnabled,
    currentConfig,
    glowClass,

    // Actions
    toggleFlickering,
    toggleScanlines,
    setGlowIntensity,
    toggleGlow,
    enableAllEffects,
    disableAllEffects,
    resetToDefaults
  };
}
