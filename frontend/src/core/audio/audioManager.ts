import { reactive } from 'vue'
import { MUSIC_MANIFEST, SOUND_MANIFEST, type MusicKey, type SoundKey } from './soundManifest'

/**
 * Bus names group sounds so players can tune them independently.
 * `ui` covers interface feedback, `sfx` gameplay effects, `music` loops.
 */
export type AudioBus = 'ui' | 'sfx' | 'music'

const STORAGE_KEY = 'audioSettings'

const AUDIO_BUSES: readonly AudioBus[] = ['ui', 'sfx', 'music']

export interface AudioSettings {
  muted: boolean
  volumes: Record<AudioBus, number>
}

export interface SoundSettingsInput {
  muted?: boolean
  volumes?: Partial<Record<AudioBus, number>>
}

const DEFAULT_SETTINGS: AudioSettings = {
  muted: true,
  volumes: { ui: 0.6, sfx: 0.8, music: 0.4 },
}

/**
 * Validate an unknown payload (e.g. `profile.preferences.sound`) into sound
 * settings. Returns `null` for anything that is not a plain object; unknown
 * keys and unknown buses are ignored, volumes are clamped to [0, 1].
 */
export function parseSoundSettings(raw: unknown): SoundSettingsInput | null {
  if (raw === null || raw === undefined || typeof raw !== 'object' || Array.isArray(raw)) {
    return null
  }
  const record = raw as Record<string, unknown>
  const input: SoundSettingsInput = {}
  if (typeof record.muted === 'boolean') {
    input.muted = record.muted
  }
  const volumes = record.volumes
  if (volumes !== null && volumes !== undefined && typeof volumes === 'object' && !Array.isArray(volumes)) {
    const parsedVolumes: Partial<Record<AudioBus, number>> = {}
    const volumeRecord = volumes as Record<string, unknown>
    for (const bus of AUDIO_BUSES) {
      const value = volumeRecord[bus]
      if (typeof value === 'number' && Number.isFinite(value)) {
        parsedVolumes[bus] = Math.min(1, Math.max(0, value))
      }
    }
    input.volumes = parsedVolumes
  }
  return input
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
  private settings: AudioSettings = reactive(loadSettings())
  private unlocked = false
  private sfxBuffers = new Map<SoundKey, HTMLAudioElement>()
  private musicPreview: HTMLAudioElement | null = null
  private currentLoop: { audio: HTMLAudioElement; key: MusicKey } | null = null
  private pendingLoop: MusicKey | null = null
  private changeHandler: ((settings: AudioSettings) => void) | null = null

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
        if (this.alarmWanted) this.startAlarmLoop()
      }
      window.addEventListener('pointerdown', unlock)
      window.addEventListener('keydown', unlock)

      // Global click feedback: any button-like element plays the select sound.
      // Delegated here so components need no per-button wiring.
      document.addEventListener('click', (event) => {
        const target = event.target as HTMLElement | null
        if (target?.closest('button, [role="button"], a')) this.play('select')
      })
    }
  }

  get muted(): boolean {
    return this.settings.muted
  }

  get volumes(): Readonly<Record<AudioBus, number>> {
    return this.settings.volumes
  }

  /** Register the persistence hook fired after local mute/volume edits. */
  setChangeHandler(handler: ((settings: AudioSettings) => void) | null): void {
    this.changeHandler = handler
  }

  setMuted(muted: boolean): void {
    this.settings.muted = muted
    if (muted) {
      this.currentLoop?.audio.pause()
      this.musicPreview?.pause()
      this.alarmAudio?.pause()
    } else if (this.pendingLoop) {
      this.playLoop(this.pendingLoop)
      this.pendingLoop = null
    } else if (this.currentLoop) {
      void this.currentLoop.audio.play().catch(() => {})
    }
    if (!muted && this.alarmWanted) this.startAlarmLoop()
    this.persist()
    this.notifyChange()
  }

  setVolume(bus: AudioBus, volume: number): void {
    this.settings.volumes[bus] = Math.min(1, Math.max(0, volume))
    if (bus === 'music' && this.currentLoop) {
      this.currentLoop.audio.volume = this.settings.volumes.music
    }
    this.persist()
    this.notifyChange()
  }

  /**
   * Hydrate settings from an external payload (e.g. profile preferences).
   * Invalid payloads are ignored; valid values merge into the current
   * settings, apply live audio side effects, and persist. Never notifies the
   * change handler, so hydration cannot echo back a save.
   */
  applySettings(raw: unknown): void {
    const parsed = parseSoundSettings(raw)
    if (!parsed) return
    if (parsed.muted !== undefined) {
      this.settings.muted = parsed.muted
    }
    if (parsed.volumes) {
      for (const bus of AUDIO_BUSES) {
        const volume = parsed.volumes[bus]
        if (volume !== undefined) {
          this.settings.volumes[bus] = volume
        }
      }
    }
    if (this.settings.muted) {
      this.currentLoop?.audio.pause()
      this.musicPreview?.pause()
      this.alarmAudio?.pause()
    } else {
      if (this.pendingLoop) {
        this.playLoop(this.pendingLoop)
        this.pendingLoop = null
      } else if (this.currentLoop) {
        this.currentLoop.audio.volume = this.settings.volumes.music
        void this.currentLoop.audio.play().catch(() => {})
      }
      if (this.alarmWanted) this.startAlarmLoop()
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

  /** One-shot sample of the music bus at its current volume (volume sliders). */
  previewMusic(): void {
    if (this.settings.muted || !this.unlocked) return
    const src = MUSIC_MANIFEST.vaultAmbient
    if (!src) return

    if (!this.musicPreview) {
      this.musicPreview = new Audio(src)
      this.musicPreview.preload = 'auto'
    }
    this.musicPreview.currentTime = 0
    this.musicPreview.volume = this.settings.volumes.music
    this.musicPreview.play().catch(() => {})
  }

  /** Start a looping music track (one loop at a time; restarts if same key). */
  playLoop(key: MusicKey): void {
    if (this.currentLoop?.key === key) return
    this.stopLoop()
    if (this.settings.muted || !this.unlocked) {
      // Remember the intent so unmuting/unlock starts the loop.
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
    this.pendingLoop = null
    this.musicDucked = false
    this.cancelMusicRestore()
    if (!this.currentLoop) return
    this.currentLoop.audio.pause()
    this.currentLoop.audio.currentTime = 0
    this.currentLoop = null
  }

  /** Incident alarm loop + music ducking. All entry points are idempotent. */

  private alarmAudio: HTMLAudioElement | null = null
  private alarmWanted = false
  private musicDucked = false
  private resumeTimer: ReturnType<typeof setTimeout> | null = null
  private fadeTimers = new Map<HTMLAudioElement, ReturnType<typeof setInterval>>()

  private fadeElement(
    audio: HTMLAudioElement,
    target: number,
    durationMs: number,
    onDone?: () => void
  ): void {
    const previous = this.fadeTimers.get(audio)
    if (previous) window.clearInterval(previous)
    const steps = Math.max(1, Math.round(durationMs / 50))
    const start = audio.volume
    const delta = (target - start) / steps
    let n = 0
    const timer = window.setInterval(() => {
      n += 1
      audio.volume = Math.min(1, Math.max(0, start + delta * n))
      if (n >= steps) {
        window.clearInterval(timer)
        this.fadeTimers.delete(audio)
        onDone?.()
      }
    }, 50)
    this.fadeTimers.set(audio, timer)
  }

  private cancelFade(audio: HTMLAudioElement): void {
    const timer = this.fadeTimers.get(audio)
    if (!timer) return
    window.clearInterval(timer)
    this.fadeTimers.delete(audio)
  }

  /** Start the looping incident alarm. Stays on until stopAlarmLoop. */
  startAlarmLoop(): void {
    this.alarmWanted = true
    if (this.settings.muted || !this.unlocked) return
    const src = SOUND_MANIFEST.alarm
    if (!src) return
    if (!this.alarmAudio) {
      this.alarmAudio = new Audio(src)
      this.alarmAudio.loop = true
      this.alarmAudio.preload = 'auto'
    }
    this.cancelFade(this.alarmAudio)
    this.alarmAudio.volume = this.settings.volumes.sfx
    if (!this.alarmAudio.paused) return
    this.alarmAudio.play().catch(() => {})
  }

  stopAlarmLoop(fadeMs = 500): void {
    this.alarmWanted = false
    const audio = this.alarmAudio
    if (!audio || audio.paused) return
    this.fadeElement(audio, 0, fadeMs, () => audio.pause())
  }

  /** Fade the music loop out over 2s so the alarm takes over. */
  duckMusic(fadeMs = 2000): void {
    this.cancelMusicRestore()
    const loop = this.currentLoop
    if (!loop || this.musicDucked) return
    this.musicDucked = true
    this.fadeElement(loop.audio, 0, fadeMs, () => loop.audio.pause())
  }

  /** Resume a ducked music loop after a delay (5s — mid-range of the 2–8s window). */
  restoreMusic(delayMs = 5000, fadeMs = 2000): void {
    this.cancelMusicRestore()
    if (!this.musicDucked) return
    this.resumeTimer = window.setTimeout(() => {
      this.resumeTimer = null
      this.musicDucked = false
      const loop = this.currentLoop
      if (!loop || this.settings.muted || !this.unlocked) return
      loop.audio.volume = 0
      loop.audio.play().catch(() => {})
      this.fadeElement(loop.audio, this.settings.volumes.music, fadeMs)
    }, delayMs)
  }

  cancelMusicRestore(): void {
    if (this.resumeTimer) {
      window.clearTimeout(this.resumeTimer)
      this.resumeTimer = null
    }
  }

  private persist(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings))
    } catch {
      // Storage unavailable (private mode) — settings stay session-only.
    }
  }

  private notifyChange(): void {
    this.changeHandler?.({
      muted: this.settings.muted,
      volumes: { ...this.settings.volumes },
    })
  }
}

export const audioManager = new AudioManager()
