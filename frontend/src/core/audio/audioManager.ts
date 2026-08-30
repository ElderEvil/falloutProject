import { MUSIC_MANIFEST, SOUND_MANIFEST, type MusicKey, type SoundKey } from './soundManifest'

/**
 * Bus names group sounds so players can tune them independently.
 * `ui` covers interface feedback, `sfx` gameplay effects, `music` loops.
 */
export type AudioBus = 'ui' | 'sfx' | 'music'

const STORAGE_KEY = 'audioSettings'

interface AudioSettings {
  muted: boolean
  volumes: Record<AudioBus, number>
}

const DEFAULT_SETTINGS: AudioSettings = {
  muted: false,
  volumes: { ui: 0.6, sfx: 0.8, music: 0.4 },
}

function loadSettings(): AudioSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    const parsed = JSON.parse(raw) as Partial<AudioSettings>
    return {
      muted: parsed.muted ?? DEFAULT_SETTINGS.muted,
      volumes: { ...DEFAULT_SETTINGS.volumes, ...parsed.volumes },
    }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

/**
 * Singleton audio manager for the sound system.
 *
 * Browsers block audio before a user gesture, so playback stays locked until
 * the first pointer/keyboard interaction unlocks it; loops requested before
 * that start automatically on unlock. Missing assets fail silently — the
 * manifests may list sounds before their files exist.
 */
class AudioManager {
  private settings: AudioSettings = loadSettings()
  private unlocked = false
  private sfxBuffers = new Map<SoundKey, HTMLAudioElement>()
  private currentLoop: { audio: HTMLAudioElement; key: MusicKey } | null = null
  private pendingLoop: MusicKey | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      const unlock = () => {
        this.unlocked = true
        window.removeEventListener('pointerdown', unlock)
        window.removeEventListener('keydown', unlock)
        if (this.pendingLoop) {
          this.playLoop(this.pendingLoop)
          this.pendingLoop = null
        }
      }
      window.addEventListener('pointerdown', unlock)
      window.addEventListener('keydown', unlock)
    }
  }

  get muted(): boolean {
    return this.settings.muted
  }

  get volumes(): Readonly<Record<AudioBus, number>> {
    return this.settings.volumes
  }

  setMuted(muted: boolean): void {
    this.settings.muted = muted
    if (muted) this.currentLoop?.audio.pause()
    else if (this.currentLoop) void this.currentLoop.audio.play().catch(() => {})
    this.persist()
  }

  setVolume(bus: AudioBus, volume: number): void {
    this.settings.volumes[bus] = Math.min(1, Math.max(0, volume))
    if (bus === 'music' && this.currentLoop) {
      this.currentLoop.audio.volume = this.settings.volumes.music
    }
    this.persist()
  }

  /** Play a manifest sound on its bus. No-op when muted, locked, or missing. */
  play(key: SoundKey, bus: AudioBus = 'ui'): void {
    if (this.settings.muted || !this.unlocked) return
    const src = SOUND_MANIFEST[key]
    if (!src) return

    let audio = this.sfxBuffers.get(key)
    if (!audio) {
      audio = new Audio(src)
      audio.preload = 'auto'
      this.sfxBuffers.set(key, audio)
    }

    // Restart from the top so rapid re-triggers overlap-free.
    audio.currentTime = 0
    audio.volume = this.settings.volumes[bus]
    audio.play().catch(() => {
      // Missing file or interrupted play — stay silent by design.
    })
  }

  /** Start a looping music track (one loop at a time; restarts if same key). */
  playLoop(key: MusicKey): void {
    if (this.currentLoop?.key === key) return
    this.stopLoop()
    if (this.settings.muted) return
    if (!this.unlocked) {
      this.pendingLoop = key
      return
    }

    const src = MUSIC_MANIFEST[key]
    if (!src) return

    const audio = new Audio(src)
    audio.loop = true
    audio.volume = this.settings.volumes.music
    audio.play().catch(() => {})
    this.currentLoop = { audio, key }
  }

  stopLoop(): void {
    if (!this.currentLoop) return
    this.currentLoop.audio.pause()
    this.currentLoop.audio.currentTime = 0
    this.currentLoop = null
  }

  private persist(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings))
    } catch {
      // Storage unavailable (private mode) — settings stay session-only.
    }
  }
}

export const audioManager = new AudioManager()
