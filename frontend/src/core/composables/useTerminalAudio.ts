import { ref, computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

export type AudioType = 'key-click' | 'button-hover' | 'button-click' | 'menu-open' | 'success' | 'error'

interface AudioConfig {
  enabled: boolean
  volume: number
  ambientEnabled: boolean
}

// Web Audio API context
let audioContext: AudioContext | null = null

/**
 * Composable for Fallout-style terminal audio effects
 * 
 * Uses Web Audio API to synthesize authentic CRT/terminal sounds
 * No external audio files needed - everything generated programmatically
 * 
 * Sound palette:
 * - key-click: Mechanical keyboard tap
 * - button-hover: Soft electronic hum
 * - button-click: Terminal confirmation beep
 * - menu-open: Servo-style slide
 * - success: Positive chime
 * - error: Warning buzz
 */
export function useTerminalAudio() {
  // User preferences
  const enabled = useLocalStorage('terminal-audio:enabled', false)
  const volume = useLocalStorage('terminal-audio:volume', 0.3)
  const ambientEnabled = useLocalStorage('terminal-audio:ambient', false)

  // Track if audio context is initialized (needed for browser autoplay policies)
  const isInitialized = ref(false)

  /**
   * Initialize audio context on first user interaction
   * Browsers require user gesture before playing audio
   */
  function initAudioContext() {
    if (!audioContext && typeof window !== 'undefined') {
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
      isInitialized.value = true
    }
    if (audioContext?.state === 'suspended') {
      audioContext.resume()
    }
  }

  /**
   * Play a synthesized terminal sound
   */
  function play(type: AudioType) {
    if (!enabled.value || !audioContext) return

    const now = audioContext.currentTime
    const masterGain = audioContext.createGain()
    masterGain.connect(audioContext.destination)
    masterGain.gain.value = volume.value

    switch (type) {
      case 'key-click':
        playKeyClick(now, masterGain)
        break
      case 'button-hover':
        playButtonHover(now, masterGain)
        break
      case 'button-click':
        playButtonClick(now, masterGain)
        break
      case 'menu-open':
        playMenuOpen(now, masterGain)
        break
      case 'success':
        playSuccess(now, masterGain)
        break
      case 'error':
        playError(now, masterGain)
        break
    }
  }

  /**
   * Mechanical keyboard click sound
   * Short noise burst filtered to sound like a keycap
   */
  function playKeyClick(time: number, destination: AudioNode) {
    if (!audioContext) return

    const osc = audioContext.createOscillator()
    const gain = audioContext.createGain()
    const filter = audioContext.createBiquadFilter()

    osc.type = 'square'
    osc.frequency.setValueAtTime(800, time)
    osc.frequency.exponentialRampToValueAtTime(400, time + 0.02)

    filter.type = 'lowpass'
    filter.frequency.value = 2000

    gain.gain.setValueAtTime(0.3, time)
    gain.gain.exponentialRampToValueAtTime(0.01, time + 0.02)

    osc.connect(filter)
    filter.connect(gain)
    gain.connect(destination)

    osc.start(time)
    osc.stop(time + 0.02)
  }

  /**
   * Soft hover sound
   * Very subtle high-frequency sine wave
   */
  function playButtonHover(time: number, destination: AudioNode) {
    if (!audioContext) return

    const osc = audioContext.createOscillator()
    const gain = audioContext.createGain()

    osc.type = 'sine'
    osc.frequency.setValueAtTime(1200, time)

    gain.gain.setValueAtTime(0, time)
    gain.gain.linearRampToValueAtTime(0.05, time + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.001, time + 0.08)

    osc.connect(gain)
    gain.connect(destination)

    osc.start(time)
    osc.stop(time + 0.08)
  }

  /**
   * Terminal button confirmation beep
   * Classic 1kHz tone with slight decay
   */
  function playButtonClick(time: number, destination: AudioNode) {
    if (!audioContext) return

    const osc = audioContext.createOscillator()
    const gain = audioContext.createGain()

    osc.type = 'square'
    osc.frequency.setValueAtTime(1000, time)
    osc.frequency.exponentialRampToValueAtTime(800, time + 0.1)

    gain.gain.setValueAtTime(0.2, time)
    gain.gain.exponentialRampToValueAtTime(0.01, time + 0.1)

    osc.connect(gain)
    gain.connect(destination)

    osc.start(time)
    osc.stop(time + 0.1)
  }

  /**
   * Menu open slide sound
   * Frequency slide from low to high
   */
  function playMenuOpen(time: number, destination: AudioNode) {
    if (!audioContext) return

    const osc = audioContext.createOscillator()
    const gain = audioContext.createGain()

    osc.type = 'sawtooth'
    osc.frequency.setValueAtTime(200, time)
    osc.frequency.exponentialRampToValueAtTime(600, time + 0.15)

    gain.gain.setValueAtTime(0.1, time)
    gain.gain.linearRampToValueAtTime(0.15, time + 0.05)
    gain.gain.exponentialRampToValueAtTime(0.01, time + 0.15)

    osc.connect(gain)
    gain.connect(destination)

    osc.start(time)
    osc.stop(time + 0.15)
  }

  /**
   * Success chime
   * Two-tone positive confirmation
   */
  function playSuccess(time: number, destination: AudioNode) {
    if (!audioContext) return

    // First note
    const osc1 = audioContext.createOscillator()
    const gain1 = audioContext.createGain()
    osc1.type = 'sine'
    osc1.frequency.value = 880
    gain1.gain.setValueAtTime(0.2, time)
    gain1.gain.exponentialRampToValueAtTime(0.01, time + 0.15)
    osc1.connect(gain1)
    gain1.connect(destination)
    osc1.start(time)
    osc1.stop(time + 0.15)

    // Second note (harmony)
    const osc2 = audioContext.createOscillator()
    const gain2 = audioContext.createGain()
    osc2.type = 'sine'
    osc2.frequency.value = 1100
    gain2.gain.setValueAtTime(0, time)
    gain2.gain.linearRampToValueAtTime(0.15, time + 0.05)
    gain2.gain.exponentialRampToValueAtTime(0.01, time + 0.2)
    osc2.connect(gain2)
    gain2.connect(destination)
    osc2.start(time + 0.05)
    osc2.stop(time + 0.2)
  }

  /**
   * Error buzz
   * Low frequency warning tone
   */
  function playError(time: number, destination: AudioNode) {
    if (!audioContext) return

    const osc = audioContext.createOscillator()
    const gain = audioContext.createGain()

    osc.type = 'sawtooth'
    osc.frequency.setValueAtTime(150, time)
    osc.frequency.linearRampToValueAtTime(100, time + 0.2)

    gain.gain.setValueAtTime(0.2, time)
    gain.gain.exponentialRampToValueAtTime(0.01, time + 0.2)

    osc.connect(gain)
    gain.connect(destination)

    osc.start(time)
    osc.stop(time + 0.2)
  }

  /**
   * Toggle audio on/off
   */
  function toggleEnabled() {
    enabled.value = !enabled.value
    if (enabled.value) {
      initAudioContext()
    }
  }

  /**
   * Set volume (0-1)
   */
  function setVolume(value: number) {
    volume.value = Math.max(0, Math.min(1, value))
  }

  /**
   * Toggle ambient hum
   */
  function toggleAmbient() {
    ambientEnabled.value = !ambientEnabled.value
  }

  return {
    // State
    enabled: computed(() => enabled.value),
    volume: computed(() => volume.value),
    ambientEnabled: computed(() => ambientEnabled.value),
    isInitialized: computed(() => isInitialized.value),

    // Actions
    initAudioContext,
    play,
    toggleEnabled,
    setVolume,
    toggleAmbient,
  }
}
