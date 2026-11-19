import { reactive } from 'vue'
import {
  AMBIENCE_MANIFEST,
  MUSIC_MANIFEST,
  SOUND_MANIFEST,
  getAmbienceSrc,
  type AmbienceKey,
  type MusicKey,
  type SoundKey,
} from './soundManifest'

/**
 * Bus names group sounds so players can tune them independently.
 * `ui` covers interface feedback, `sfx` gameplay effects, `music` loops.
 */
export type AudioBus = 'ui' | 'sfx' | 'music' | 'ambience'

const STORAGE_KEY = 'audioSettings'

/** Overlap between consecutive playlist tracks, so ambient music never gaps. */
const MUSIC_CROSSFADE_MS = 1500

const AUDIO_BUSES: readonly AudioBus[] = ['ui', 'sfx', 'music', 'ambience']

export interface AudioSettings {
  muted: boolean
  /** Dedicated switch for the looping incident siren; independent of master mute. */
  alarmEnabled: boolean
  volumes: Record<AudioBus, number>
}

export interface SoundSettingsInput {
  muted?: boolean
  alarmEnabled?: boolean
  volumes?: Partial<Record<AudioBus, number>>
}

const DEFAULT_SETTINGS: AudioSettings = {
  muted: true,
  alarmEnabled: true,
  volumes: { ui: 0.6, sfx: 0.8, music: 0.4, ambience: 0.4 },
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
  if (typeof record.alarmEnabled === 'boolean') {
    input.alarmEnabled = record.alarmEnabled
  }
  const volumes = record.volumes
  if (
    volumes !== null &&
    volumes !== undefined &&
    typeof volumes === 'object' &&
    !Array.isArray(volumes)
  ) {
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
    const cached = parseSoundSettings(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null'))
    if (!cached) return { ...DEFAULT_SETTINGS }
    return {
      muted: cached.muted ?? DEFAULT_SETTINGS.muted,
      alarmEnabled: cached.alarmEnabled ?? DEFAULT_SETTINGS.alarmEnabled,
      volumes: { ...DEFAULT_SETTINGS.volumes, ...cached.volumes },
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
  private ambiencePreview: HTMLAudioElement | null = null
  private currentLoop: { audio: HTMLAudioElement; key: MusicKey; index: number } | null = null
  private pendingLoop: MusicKey | null = null
  private outgoingLoop: HTMLAudioElement | null = null
  private ambienceAudio: HTMLAudioElement | null = null
  private ambienceKey: AmbienceKey | null = null
  private ambienceWanted: AmbienceKey | null = null
  private changeHandler: ((settings: AudioSettings) => void) | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      const unlock = () => {
        this.unlocked = true
        window.removeEventListener('pointerdown', unlock)
        window.removeEventListener('keydown', unlock)
        if (this.themedRoomWanted && !this.musicDucked) {
          this.playThemedRoomMusic(this.themedRoomWanted)
        }
        if (this.pendingLoop && !this.musicDucked && !this.themedRoomWanted) {
          this.playLoop(this.pendingLoop)
          this.pendingLoop = null
        }
        if (this.alarmWanted) this.startAlarmLoop()
        if (this.ambienceWanted && !this.musicDucked) this.playAmbience(this.ambienceWanted)
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

  /** Stored slider values stay linear; playback uses a gentler low-volume curve. */
  private playbackVolume(bus: AudioBus): number {
    return this.settings.volumes[bus] ** 2
  }

  get muted(): boolean {
    return this.settings.muted
  }

  get alarmEnabled(): boolean {
    return this.settings.alarmEnabled
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
    this.reconcilePlayback()
    this.persist()
    this.notifyChange()
  }

  /** Toggle the incident siren without touching the master mute or other buses. */
  setAlarmEnabled(enabled: boolean): void {
    this.settings.alarmEnabled = enabled
    this.reconcilePlayback()
    this.persist()
    this.notifyChange()
  }

  setVolume(bus: AudioBus, volume: number): void {
    this.settings.volumes[bus] = Math.min(1, Math.max(0, volume))
    if (bus === 'music' && this.themedRoomAudio) {
      this.applySliderVolume(this.themedRoomAudio, 'music')
    } else if (bus === 'music' && this.currentLoop) {
      this.applySliderVolume(this.currentLoop.audio, 'music')
    }
    if (bus === 'ambience' && this.ambienceAudio) {
      this.applySliderVolume(this.ambienceAudio, 'ambience')
    }
    if (bus === 'sfx' && this.alarmAudio) {
      this.applySliderVolume(this.alarmAudio, 'sfx')
    }
    this.persist()
    this.notifyChange()
  }

  /**
   * Apply a slider change to a live element. An active fade-in is retargeted
   * so it glides to — and finishes at — the new slider value instead of the
   * one captured when the fade started. Fades that pause their element on
   * completion (ducking, alarm stop, crossfade-out) keep their original
   * course so they still finish silent and pause the loop.
   */
  private applySliderVolume(audio: HTMLAudioElement, bus: AudioBus): void {
    const target = this.playbackVolume(bus)
    const fade = this.fadeStates.get(audio)
    const remaining = fade ? fade.steps - fade.n : 0
    if (fade && !fade.pausesOnDone && remaining > 0) {
      fade.start = audio.volume
      fade.steps = remaining
      fade.n = 0
      fade.target = target
      return
    }
    audio.volume = target
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
    if (parsed.alarmEnabled !== undefined) {
      this.settings.alarmEnabled = parsed.alarmEnabled
    }
    if (parsed.volumes) {
      for (const bus of AUDIO_BUSES) {
        const volume = parsed.volumes[bus]
        if (volume !== undefined) {
          this.settings.volumes[bus] = volume
        }
      }
    }
    this.reconcilePlayback()
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
    audio.volume = this.playbackVolume(bus)
    audio.play().catch(() => {
      // Missing file or interrupted play — stay silent by design.
    })
  }

  stop(key: SoundKey): void {
    const audio = this.sfxBuffers.get(key)
    if (!audio) return
    audio.pause()
    audio.currentTime = 0
  }

  /**
   * One-shot sample of the music bus at its current volume (volume sliders).
   * An audible loop already reflects the volume the slider just set; previewing
   * over it would layer a second copy of the track from the top. A paused loop
   * (alarm ducking) is silent, so the preview still gives slider feedback.
   */
  previewMusic(): void {
    if (this.currentLoop && !this.currentLoop.audio.paused) return
    if (this.themedRoomAudio && !this.themedRoomAudio.paused) return
    if (this.settings.muted || !this.unlocked) return
    const src = MUSIC_MANIFEST.vaultAmbient[0]
    if (!src) return

    if (!this.musicPreview) {
      this.musicPreview = new Audio(src)
      this.musicPreview.preload = 'auto'
    }
    this.musicPreview.currentTime = 0
    this.musicPreview.volume = this.playbackVolume('music')
    this.musicPreview.play().catch(() => {})
  }

  /**
   * One-shot sample of the ambience bus at its current volume (volume sliders).
   * A live room ambience loop already reflects the volume the slider just set;
   * previewing over it would layer a second copy of the sample from the top.
   */
  previewAmbience(): void {
    if (this.ambienceAudio && !this.ambienceAudio.paused) return
    if (this.settings.muted || !this.unlocked) return
    const src = AMBIENCE_MANIFEST.production
    if (!src) return

    if (!this.ambiencePreview) {
      this.ambiencePreview = new Audio(src)
      this.ambiencePreview.preload = 'auto'
    }
    this.ambiencePreview.currentTime = 0
    this.ambiencePreview.volume = this.playbackVolume('ambience')
    this.ambiencePreview.play().catch(() => {})
  }

  /**
   * Start a music playlist (one playlist at a time). Requesting the key that is
   * already playing keeps the playlist where it is instead of restarting it.
   */
  playLoop(key: MusicKey): void {
    this.stopThemedRoomMusic()
    this.stopPreview()
    if (this.currentLoop?.key === key) return
    this.stopLoop()
    if (this.settings.muted || !this.unlocked) {
      // Remember the intent so unmuting/unlock starts the loop.
      this.pendingLoop = key
      return
    }

    this.startLoopTrack(key, 0)
  }

  /**
   * Play one playlist entry. The next entry is queued from `timeupdate` just
   * before this one ends and crossfaded over it; when the duration is unknown
   * the `ended` event advances instead, so rotation works either way.
   */
  private startLoopTrack(key: MusicKey, index: number, crossfadeFrom?: HTMLAudioElement): void {
    const audio = this.createLoopAudio(key, index)
    audio.volume = crossfadeFrom ? 0 : this.playbackVolume('music')
    audio.play().catch(() => {
      // Missing file or interrupted play — stay silent by design.
    })
    this.currentLoop = { audio, key, index }

    if (crossfadeFrom) {
      this.outgoingLoop = crossfadeFrom
      this.fadeElement(audio, this.playbackVolume('music'), MUSIC_CROSSFADE_MS)
      this.fadeElement(crossfadeFrom, 0, MUSIC_CROSSFADE_MS, () => {
        crossfadeFrom.pause()
        if (this.outgoingLoop === crossfadeFrom) this.outgoingLoop = null
      })
    }
  }

  private createLoopAudio(key: MusicKey, index: number): HTMLAudioElement {
    const audio = new Audio(MUSIC_MANIFEST[key][index])
    audio.loop = false
    audio.addEventListener('timeupdate', () => this.crossfadeBeforeEnd(audio))
    audio.addEventListener('ended', () => this.advanceLoop(audio, false))
    return audio
  }

  /**
   * Advance the playlist without starting audible playback, so a track that
   * ends while ducked or muted hands over silently and restore/unmute resumes it.
   */
  private queueLoopTrack(key: MusicKey, index: number): void {
    const audio = this.createLoopAudio(key, index)
    audio.volume = 0
    this.currentLoop = { audio, key, index }
  }

  /** Start the crossfade once a playing track is within its final fade window. */
  private crossfadeBeforeEnd(audio: HTMLAudioElement): void {
    const { duration, currentTime } = audio
    if (!Number.isFinite(duration) || duration <= 0) return
    if (duration - currentTime > MUSIC_CROSSFADE_MS / 1000) return
    this.advanceLoop(audio, true)
  }

  /** Move to the next playlist entry, wrapping around after the last one. */
  private advanceLoop(from: HTMLAudioElement, crossfade: boolean): void {
    const loop = this.currentLoop
    // A late event from a track that already handed over must not advance twice.
    if (!loop || loop.audio !== from) return
    const nextIndex = (loop.index + 1) % MUSIC_MANIFEST[loop.key].length
    if (this.musicDucked || this.settings.muted) {
      if (crossfade) return
      this.queueLoopTrack(loop.key, nextIndex)
      return
    }
    this.startLoopTrack(loop.key, nextIndex, crossfade ? from : undefined)
  }

  stopLoop(): void {
    this.stopPreview()
    this.pendingLoop = null
    this.musicDucked = false
    this.cancelMusicRestore()
    this.stopLoopPlayback(this.outgoingLoop)
    this.outgoingLoop = null
    this.stopLoopPlayback(this.currentLoop?.audio ?? null)
    this.currentLoop = null
  }

  private stopLoopPlayback(audio: HTMLAudioElement | null): void {
    if (!audio) return
    this.cancelFade(audio)
    audio.pause()
    audio.currentTime = 0
  }

  /** Start a looping room ambience track (one at a time). */
  playAmbience(key: AmbienceKey): void {
    this.stopPreview()
    this.ambienceWanted = key
    if (this.settings.muted || !this.unlocked || this.musicDucked) return
    if (this.ambienceKey === key && this.ambienceAudio) {
      if (!this.ambienceAudio.paused) return
      this.ambienceAudio.volume = this.playbackVolume('ambience')
      void this.ambienceAudio.play().catch(() => {})
      return
    }
    this.stopAmbiencePlayback()
    const src = getAmbienceSrc(key)
    if (!src) return
    const audio = new Audio(src)
    audio.loop = true
    audio.volume = this.playbackVolume('ambience')
    audio.play().catch(() => {})
    this.ambienceAudio = audio
    this.ambienceKey = key
  }

  stopAmbience(): void {
    this.ambienceWanted = null
    this.stopAmbiencePlayback()
  }

  private stopAmbiencePlayback(): void {
    if (this.ambienceAudio) {
      this.ambienceAudio.pause()
      this.ambienceAudio.currentTime = 0
    }
    this.ambienceAudio = null
    this.ambienceKey = null
  }

  /** Themed room music: the room's theme track takes the music bus. */

  private themedRoomAudio: HTMLAudioElement | null = null
  private themedRoomKey: AmbienceKey | null = null
  private themedRoomWanted: AmbienceKey | null = null
  private playlistSuspended = false

  /**
   * Play a themed room's theme track on the music bus. The vault playlist
   * yields: it is paused in place and resumes from there when the themed
   * track stops, so a themed visit never restarts the playlist.
   */
  playThemedRoomMusic(key: AmbienceKey): HTMLAudioElement | null {
    this.themedRoomWanted = key
    this.stopPreview()
    if (this.settings.muted || !this.unlocked || this.musicDucked) return null
    if (this.themedRoomKey === key && this.themedRoomAudio) {
      if (!this.themedRoomAudio.paused) return this.themedRoomAudio
      this.themedRoomAudio.volume = this.playbackVolume('music')
      void this.themedRoomAudio.play().catch(() => {})
      return this.themedRoomAudio
    }
    this.stopThemedRoomPlayback()
    const src = getAmbienceSrc(key)
    if (!src) return null
    if (this.currentLoop && !this.playlistSuspended) {
      this.playlistSuspended = true
      this.currentLoop.audio.pause()
    } else if (!this.currentLoop && this.pendingLoop) {
      // A playlist requested before the unlock waits behind the themed track.
      this.playlistSuspended = true
    }
    const audio = new Audio(src)
    audio.loop = true
    audio.volume = 0
    audio.play().catch(() => {})
    this.themedRoomAudio = audio
    this.themedRoomKey = key
    this.fadeElement(audio, this.playbackVolume('music'), 600)
    return audio
  }

  /** Stop the themed track and hand the music bus back to the playlist. */
  stopThemedRoomMusic(): void {
    this.themedRoomWanted = null
    this.stopThemedRoomPlayback()
    this.resumeSuspendedPlaylist()
  }

  private stopThemedRoomPlayback(): void {
    if (this.themedRoomAudio) {
      this.cancelFade(this.themedRoomAudio)
      this.themedRoomAudio.pause()
    }
    this.themedRoomAudio = null
    this.themedRoomKey = null
  }

  private resumeSuspendedPlaylist(): void {
    if (!this.playlistSuspended) return
    this.playlistSuspended = false
    if (this.settings.muted || this.musicDucked || !this.unlocked) return
    const loop = this.currentLoop
    if (loop) {
      loop.audio.volume = 0
      void loop.audio.play().catch(() => {})
      this.fadeElement(loop.audio, this.playbackVolume('music'), 600)
    } else if (this.pendingLoop) {
      const pending = this.pendingLoop
      this.pendingLoop = null
      this.playLoop(pending)
    }
  }

  private stopPreview(): void {
    this.musicPreview?.pause()
    this.ambiencePreview?.pause()
  }

  /** Incident alarm loop + music ducking. All entry points are idempotent. */

  private alarmAudio: HTMLAudioElement | null = null
  private alarmWanted = false
  private musicDucked = false
  private resumeTimer: ReturnType<typeof setTimeout> | null = null
  private fadeTimers = new Map<HTMLAudioElement, ReturnType<typeof setInterval>>()
  private fadeStates = new Map<
    HTMLAudioElement,
    { start: number; target: number; steps: number; n: number; pausesOnDone: boolean }
  >()

  private fadeElement(
    audio: HTMLAudioElement,
    target: number,
    durationMs: number,
    onDone?: () => void
  ): void {
    const previous = this.fadeTimers.get(audio)
    if (previous) window.clearInterval(previous)
    const steps = Math.max(1, Math.round(durationMs / 50))
    // Mutable state so a slider change can retarget the fade mid-flight.
    const state = { start: audio.volume, target, steps, n: 0, pausesOnDone: onDone !== undefined }
    this.fadeStates.set(audio, state)
    const timer = window.setInterval(() => {
      state.n += 1
      const delta = (state.target - state.start) / state.steps
      audio.volume = Math.min(1, Math.max(0, state.start + delta * state.n))
      if (state.n >= state.steps) {
        window.clearInterval(timer)
        this.fadeTimers.delete(audio)
        this.fadeStates.delete(audio)
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
    this.fadeStates.delete(audio)
  }

  /** Start the looping incident alarm. Stays on until stopAlarmLoop. */
  startAlarmLoop(): void {
    this.alarmWanted = true
    if (this.settings.muted || !this.settings.alarmEnabled || !this.unlocked) return
    const src = SOUND_MANIFEST.alarm
    if (!src) return
    if (!this.alarmAudio) {
      this.alarmAudio = new Audio(src)
      this.alarmAudio.loop = true
      this.alarmAudio.preload = 'auto'
    }
    this.cancelFade(this.alarmAudio)
    this.alarmAudio.volume = this.playbackVolume('sfx')
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
    if (this.musicDucked) return
    this.musicDucked = true
    const loop = this.currentLoop
    const ambience = this.ambienceAudio
    const themed = this.themedRoomAudio
    if (loop) this.fadeElement(loop.audio, 0, fadeMs, () => loop.audio.pause())
    if (ambience) this.fadeElement(ambience, 0, fadeMs, () => ambience.pause())
    if (themed) this.fadeElement(themed, 0, fadeMs, () => themed.pause())
  }

  /** Resume a ducked music loop after a delay (5s — mid-range of the 2–8s window). */
  restoreMusic(delayMs = 5000, fadeMs = 2000): void {
    this.cancelMusicRestore()
    if (!this.musicDucked) return
    this.resumeTimer = window.setTimeout(() => {
      this.resumeTimer = null
      this.musicDucked = false
      if (this.settings.muted || !this.unlocked) return
      // A preview started while ducked would otherwise keep playing on top of
      // the resumed loop — two tracks on one bus.
      this.stopPreview()
      if (this.pendingLoop) {
        const pending = this.pendingLoop
        this.pendingLoop = null
        this.playLoop(pending)
      } else if (this.themedRoomWanted) {
        const themed = this.playThemedRoomMusic(this.themedRoomWanted)
        if (themed) {
          themed.volume = 0
          void themed.play().catch(() => {})
          this.fadeElement(themed, this.playbackVolume('music'), fadeMs)
        }
      } else {
        const loop = this.currentLoop
        if (loop) {
          loop.audio.volume = 0
          void loop.audio.play().catch(() => {})
          this.fadeElement(loop.audio, this.playbackVolume('music'), fadeMs)
        }
      }
      const ambience = this.ambienceAudio
      if (ambience && this.ambienceKey === this.ambienceWanted) {
        ambience.volume = 0
        void ambience.play().catch(() => {})
        this.fadeElement(ambience, this.playbackVolume('ambience'), fadeMs)
      } else if (this.ambienceWanted) {
        this.playAmbience(this.ambienceWanted)
        const started = this.ambienceAudio
        if (started) {
          started.volume = 0
          this.fadeElement(started, this.playbackVolume('ambience'), fadeMs)
        }
      }
    }, delayMs)
  }

  cancelMusicRestore(): void {
    if (this.resumeTimer) {
      window.clearTimeout(this.resumeTimer)
      this.resumeTimer = null
    }
  }

  private reconcilePlayback(): void {
    if (this.settings.muted) {
      this.currentLoop?.audio.pause()
      this.musicPreview?.pause()
      this.ambiencePreview?.pause()
      this.alarmAudio?.pause()
      this.ambienceAudio?.pause()
      this.themedRoomAudio?.pause()
      return
    }
    if (!this.settings.alarmEnabled) this.alarmAudio?.pause()
    if (this.themedRoomWanted && !this.musicDucked) {
      this.playThemedRoomMusic(this.themedRoomWanted)
    } else if (this.pendingLoop && !this.musicDucked) {
      const pending = this.pendingLoop
      this.pendingLoop = null
      this.playLoop(pending)
    } else if (this.currentLoop && !this.musicDucked) {
      this.currentLoop.audio.volume = this.playbackVolume('music')
      void this.currentLoop.audio.play().catch(() => {})
    }
    if (this.alarmWanted) this.startAlarmLoop()
    if (this.ambienceWanted && !this.musicDucked) this.playAmbience(this.ambienceWanted)
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
      alarmEnabled: this.settings.alarmEnabled,
      volumes: { ...this.settings.volumes },
    })
  }
}

export const audioManager = new AudioManager()
