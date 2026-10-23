import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { audioManager, parseSoundSettings } from '@/core/audio/audioManager'
import { SOUND_MANIFEST, MUSIC_MANIFEST, AMBIENCE_MANIFEST, ROOM_AMBIENCE_MANIFEST } from '@/core/audio/soundManifest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

it('ships every manifest audio file in the public directory', () => {
  const sources = [
    ...Object.values(SOUND_MANIFEST),
    ...Object.values(AMBIENCE_MANIFEST),
    ...Object.values(ROOM_AMBIENCE_MANIFEST),
    ...Object.values(MUSIC_MANIFEST).flat(),
  ]
  for (const src of sources) {
    expect(existsSync(resolve('public', src.slice(1))), `Missing audio asset: ${src}`).toBe(true)
  }
})

class MockAudio {
  static instances: MockAudio[] = []
  volume = 1
  currentTime = 0
  duration = 0
  loop = false
  preload = 'none'
  paused = true
  src = ''
  private listeners = new Map<string, Set<() => void>>()
  play = vi.fn(() => {
    this.paused = false
    return Promise.resolve()
  })

  pause = vi.fn(() => {
    this.paused = true
  })

  addEventListener = (type: string, listener: () => void) => {
    const set = this.listeners.get(type) ?? new Set()
    set.add(listener)
    this.listeners.set(type, set)
  }

  emit(type: 'timeupdate' | 'ended') {
    if (type === 'ended') this.paused = true
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener()
  }

  constructor(src?: string) {
    this.src = src ?? ''
    MockAudio.instances.push(this)
  }
}

async function freshManager() {
  vi.resetModules()
  const { audioManager } = await import('@/core/audio/audioManager')
  return audioManager
}

const alarmElement = () => MockAudio.instances.find((audio) => audio.loop)

const DEFAULTS = { muted: true, volumes: { ui: 0.6, sfx: 0.8, music: 0.4, ambience: 0.4 } }

describe('audioManager', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    audioManager.setChangeHandler(null)
    audioManager.applySettings(DEFAULTS)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('hydrates from a partial payload, merging per bus', () => {
    audioManager.applySettings({ muted: false, volumes: { music: 0.9 } })
    expect(audioManager.muted).toBe(false)
    expect(audioManager.volumes.music).toBe(0.9)
    expect(audioManager.volumes.ui).toBe(0.6)
    expect(audioManager.volumes.sfx).toBe(0.8)
  })

  it('clamps out-of-range volumes', () => {
    audioManager.applySettings({ volumes: { ui: 1.5, sfx: -0.2, music: 0.5 } })
    expect(audioManager.volumes.ui).toBe(1)
    expect(audioManager.volumes.sfx).toBe(0)
    expect(audioManager.volumes.music).toBe(0.5)
  })

  it('ignores malformed payloads', () => {
    for (const raw of [null, undefined, 'nope', [1, 2], 42]) {
      audioManager.applySettings(raw)
    }
    expect(audioManager.muted).toBe(true)
    expect(audioManager.volumes).toEqual({ ui: 0.6, sfx: 0.8, music: 0.4, ambience: 0.4 })
  })

  it('ignores unknown keys and unknown buses', () => {
    audioManager.applySettings({ muted: false, volumes: { ui: 0.3, bass: 0.9 }, extra: 'x' })
    expect(audioManager.volumes).toEqual({ ui: 0.3, sfx: 0.8, music: 0.4, ambience: 0.4 })
  })

  it('notifies the change handler for local edits only, never for hydration', () => {
    const handler = vi.fn()
    audioManager.setChangeHandler(handler)

    audioManager.setMuted(false)
    audioManager.setVolume('music', 0.7)
    expect(handler).toHaveBeenCalledTimes(2)

    audioManager.applySettings({ muted: true, volumes: { music: 0.1 } })
    expect(handler).toHaveBeenCalledTimes(2)
  })

  it('persists to localStorage', () => {
    audioManager.setVolume('music', 0.9)
    const stored = JSON.parse(localStorage.getItem('audioSettings') ?? '{}')
    expect(stored.volumes.music).toBe(0.9)
  })

  describe('parseSoundSettings', () => {
    it('returns null for non-objects', () => {
      for (const raw of [null, undefined, [], 'x', 42]) {
        expect(parseSoundSettings(raw)).toBeNull()
      }
    })

    it('keeps only booleans and finite clamped volumes', () => {
      expect(parseSoundSettings({ muted: 'yes', volumes: { ui: 'loud' } })).toEqual({ volumes: {} })
      expect(
        parseSoundSettings({ muted: true, volumes: { ui: 2, sfx: Infinity, music: 0.4 } })
      ).toEqual({ muted: true, volumes: { ui: 1, music: 0.4 } })
    })
  })
})

describe('audioManager alarm', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it.each(['ui', 'sfx', 'music', 'ambience'] as const)(
    'maps %s volume perceptually while storing a linear preference',
    async (bus) => {
      const manager = await freshManager()
      manager.setMuted(false)
      window.dispatchEvent(new Event('pointerdown'))
      manager.setVolume(bus, 0.1)
      manager.play('objectiveClaim', bus)
      expect(MockAudio.instances.at(-1)!.volume).toBeCloseTo(0.01)
      expect(manager.volumes[bus]).toBe(0.1)
      expect(JSON.parse(localStorage.getItem('audioSettings')!).volumes[bus]).toBe(0.1)
    }
  )

  it('starts an alarm requested before audio unlocks', async () => {
    const manager = await freshManager()
    manager.setMuted(false)

    manager.startAlarmLoop()
    expect(alarmElement()).toBeUndefined()

    window.dispatchEvent(new Event('pointerdown'))

    expect(alarmElement()).toBeDefined()
    expect(alarmElement()?.play).toHaveBeenCalled()
  })

  it('keeps the alarm silent after muting during an incident', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.startAlarmLoop()
    const alarm = alarmElement()!

    manager.setMuted(true)
    expect(alarm.paused).toBe(true)

    manager.startAlarmLoop()
    expect(alarm.paused).toBe(true)
    expect(alarm.play).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(10000)
    expect(alarm.paused).toBe(true)
  })

  it('cancels a running stop fade when the alarm restarts', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.startAlarmLoop()
    const alarm = alarmElement()!

    manager.stopAlarmLoop(500)
    manager.startAlarmLoop()
    vi.advanceTimersByTime(600)

    expect(alarm.pause).not.toHaveBeenCalled()
    expect(alarm.volume).toBeCloseTo(0.8 ** 2)
  })

  it('keeps a loop request deferred until audio unlocks', async () => {
    const manager = await freshManager()
    manager.playLoop('vaultAmbient')
    manager.setMuted(false)

    window.dispatchEvent(new Event('pointerdown'))

    const music = MockAudio.instances.find((audio) => audio.src.includes('vault-ambient'))
    expect(music?.play).toHaveBeenCalled()
  })

  it('keeps ducked music paused when playback is reconciled', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.playLoop('vaultAmbient')

    const music = MockAudio.instances.at(-1)!
    music.play.mockClear()

    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    expect(music.pause).toHaveBeenCalled()

    manager.setMuted(false)
    expect(music.play).not.toHaveBeenCalled()
  })

  it('keeps duck state without audio so a pending loop waits for restore', async () => {
    const manager = await freshManager()
    manager.playLoop('vaultAmbient')
    manager.duckMusic(500)
    manager.setMuted(false)

    window.dispatchEvent(new Event('pointerdown'))
    expect(MockAudio.instances.find((audio) => audio.src.includes('vault-ambient'))).toBeUndefined()

    manager.restoreMusic(1000, 500)
    vi.advanceTimersByTime(1000)

    const music = MockAudio.instances.find((audio) => audio.src.includes('vault-ambient'))
    expect(music?.play).toHaveBeenCalled()
  })
})

describe('audioManager ambience', () => {
  const ambienceElement = () =>
    MockAudio.instances.find((audio) => audio.src.includes('/audio/ambience/'))

  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('starts a room-category ambience loop at the music volume', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.playAmbience('production')

    const ambience = ambienceElement()
    expect(ambience?.loop).toBe(true)
    expect(ambience?.volume).toBeCloseTo(0.4 ** 2)
    expect(ambience?.play).toHaveBeenCalled()
  })

  it('defers ambience until audio unlocks', async () => {
    const manager = await freshManager()
    manager.setMuted(false)

    manager.playAmbience('training')
    expect(ambienceElement()).toBeUndefined()

    window.dispatchEvent(new Event('pointerdown'))
    expect(ambienceElement()?.play).toHaveBeenCalled()
  })

  it('does not recreate the loop when the same key is re-requested', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.playAmbience('capacity')
    const first = ambienceElement()!
    manager.playAmbience('capacity')

    expect(ambienceElement()).toBe(first)
    expect(
      MockAudio.instances.filter((audio) => audio.src.includes('/audio/ambience/'))
    ).toHaveLength(1)
  })

  it('stops ambience on request', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.playAmbience('crafting')
    const ambience = ambienceElement()!
    manager.stopAmbience()

    expect(ambience.pause).toHaveBeenCalled()
  })

  it('resumes a muted ambience loop when unmuted', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.playAmbience('production')
    const ambience = ambienceElement()!
    ambience.play.mockClear()

    manager.setMuted(true)
    expect(ambience.pause).toHaveBeenCalled()

    manager.setMuted(false)
    expect(ambience.play).toHaveBeenCalled()
  })

  it('defers ambience while music is ducked and starts the wanted key on restore', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.playLoop('vaultAmbient')
    manager.playAmbience('production')
    const paused = ambienceElement()!

    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    expect(paused.pause).toHaveBeenCalled()

    // A different key requested mid-incident must not start over the alarm.
    manager.playAmbience('training')
    expect(ambienceElement()).toBe(paused)
    expect(paused.play).toHaveBeenCalledTimes(1)

    manager.restoreMusic(1000, 500)
    vi.advanceTimersByTime(1000)

    const training = MockAudio.instances.find((audio) => audio.src.includes('training'))
    expect(training).toBeDefined()
    expect(training?.play).toHaveBeenCalled()
    expect(paused.pause).toHaveBeenCalledTimes(2)
  })
})

describe('audioManager navigation regression', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  const playing = () =>
    MockAudio.instances.filter((a) => a.src.includes('/audio/music/') && !a.paused)

  it('keeps one music loop across vault->exploration->vault (unmuted)', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.playLoop('vaultAmbient')
    manager.playLoop('exploration')
    manager.playLoop('vaultAmbient')
    manager.playLoop('vaultAmbient')

    expect(playing()).toHaveLength(1)
  })

  it('keeps one music loop when starting muted, then unmuting + hydrating', async () => {
    const manager = await freshManager()
    manager.playLoop('vaultAmbient')
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.applySettings({ muted: false })

    manager.playLoop('exploration')
    manager.playLoop('vaultAmbient')

    expect(playing()).toHaveLength(1)
  })
})

describe('audioManager preview overlap', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('stops the music preview when a loop starts', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.previewMusic()
    const preview = MockAudio.instances.at(-1)!
    expect(preview.src).toContain('vault-ambient')
    expect(preview.play).toHaveBeenCalled()

    manager.playLoop('vaultAmbient')

    expect(preview.pause).toHaveBeenCalled()
    expect(MockAudio.instances.filter((a) => !a.paused)).toHaveLength(1)
  })
})

describe('audioManager ambience bus', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('routes the ambience slider to the ambience element, not the music loop', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.playLoop('vaultAmbient')
    manager.playAmbience('production')

    const loop = MockAudio.instances.find((a) => a.src.includes('/audio/music/'))!
    const ambience = MockAudio.instances.find((a) => a.loop && a.src.includes('/audio/ambience/'))!

    manager.setVolume('ambience', 0.2)

    expect(ambience.volume).toBeCloseTo(0.2 ** 2)
    expect(loop.volume).toBeCloseTo(0.4 ** 2)
  })

  it('stops the ambience preview when a room ambience loop starts', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.previewAmbience()
    const preview = MockAudio.instances.find((a) => a.src.includes('/audio/ambience/') && !a.loop)!
    expect(preview.play).toHaveBeenCalled()

    manager.playAmbience('production')

    expect(preview.pause).toHaveBeenCalled()
  })
})

describe('audioManager music rotation', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  const tracks = () => MockAudio.instances.filter((a) => a.src.includes('/audio/music/'))
  const currentTrack = () => tracks().at(-1)!

  async function playingManager() {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    return manager
  }

  it('plays the first entry of the playlist', async () => {
    const manager = await playingManager()

    manager.playLoop('vaultAmbient')

    expect(currentTrack().src).toContain('vault-ambient-1.mp3')
    expect(currentTrack().play).toHaveBeenCalled()
  })

  it('crossfades into the next entry as the playing track nears its end', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 59

    first.emit('timeupdate')

    expect(currentTrack().src).toContain('vault-ambient-2.mp3')
    expect(currentTrack().play).toHaveBeenCalled()
  })

  it('ignores late events from the track that already handed over', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 60
    first.emit('timeupdate')

    first.emit('ended')
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(2)
  })

  it('advances on ended when the duration is unknown', async () => {
    const manager = await playingManager()
    manager.playLoop('exploration')
    const first = currentTrack()
    expect(first.duration).toBe(0)

    first.emit('ended')

    expect(currentTrack().src).toContain('exploration-2.mp3')
  })

  it('wraps back to the first entry after the last one', async () => {
    const manager = await playingManager()
    manager.playLoop('exploration')

    for (let i = 0; i < 4; i += 1) currentTrack().emit('ended')

    expect(currentTrack().src).toContain('exploration-1.mp3')
    expect(tracks()).toHaveLength(5)
  })

  it('silences the fading track when the loop stops mid-crossfade', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 59
    first.emit('timeupdate')
    const second = currentTrack()

    manager.stopLoop()
    vi.advanceTimersByTime(2000)

    expect(first.pause).toHaveBeenCalled()
    expect(second.pause).toHaveBeenCalled()
    expect(first.currentTime).toBe(0)
  })

  it('keeps the playlist position when the playing key is re-requested', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 30

    manager.playLoop('vaultAmbient')
    manager.playLoop('vaultAmbient')

    expect(tracks()).toHaveLength(1)
    expect(currentTrack()).toBe(first)
  })

  it('does not advance while the duration is unknown', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()

    first.duration = 0
    first.emit('timeupdate')
    first.duration = Number.NaN
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(1)
  })

  it('does not restart itself after the loop stops', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()

    manager.stopLoop()
    first.emit('ended')
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(1)
    expect(first.pause).toHaveBeenCalled()
  })

  it('does not start the next entry audibly while the music is ducked', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()

    manager.duckMusic()
    vi.advanceTimersByTime(2000)
    first.duration = 60
    first.currentTime = 59
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(1)
    expect(tracks().some((track) => !track.paused)).toBe(false)
  })

  it('queues the next entry silently when a ducked track ends', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()

    manager.duckMusic()
    first.emit('ended')

    expect(tracks().some((track) => !track.paused)).toBe(false)
    expect(currentTrack().src).toContain('vault-ambient-2.mp3')
  })

  it('resumes the queued entry when the duck ends', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    manager.duckMusic()
    currentTrack().emit('ended')

    const queued = currentTrack()
    manager.restoreMusic(0)
    vi.advanceTimersByTime(0)

    expect(queued.play).toHaveBeenCalled()
  })

  it('silences the previous track once the crossfade completes', async () => {
    const manager = await playingManager()
    manager.playLoop('vaultAmbient')
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 59
    first.emit('timeupdate')

    expect(first.pause).not.toHaveBeenCalled()

    vi.advanceTimersByTime(2000)

    expect(first.pause).toHaveBeenCalled()
    expect(currentTrack().src).toContain('vault-ambient-2.mp3')
  })
})

describe('audioManager alarm toggle', () => {
  beforeEach(() => {
    MockAudio.instances = []
    localStorage.clear()
    vi.stubGlobal('Audio', MockAudio)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('leaves the alarm enabled by default', async () => {
    const manager = await freshManager()
    expect(manager.alarmEnabled).toBe(true)
  })

  it('stays silent when the alarm is disabled even though sound is on', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    manager.setAlarmEnabled(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.startAlarmLoop()

    expect(alarmElement()).toBeUndefined()
  })

  it('pauses a running alarm when the alarm is disabled mid-incident', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.startAlarmLoop()
    const alarm = alarmElement()!
    expect(alarm.paused).toBe(false)

    manager.setAlarmEnabled(false)

    expect(alarm.paused).toBe(true)
  })

  it('resumes a wanted alarm when the alarm is re-enabled', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    manager.setAlarmEnabled(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.startAlarmLoop()
    expect(alarmElement()).toBeUndefined()

    manager.setAlarmEnabled(true)

    const alarm = alarmElement()!
    expect(alarm).toBeDefined()
    expect(alarm.paused).toBe(false)
  })

  it('keeps the alarm silent when master mute is on regardless of the toggle', async () => {
    const manager = await freshManager()
    manager.setAlarmEnabled(true)
    manager.setMuted(true)
    window.dispatchEvent(new Event('pointerdown'))

    manager.startAlarmLoop()

    expect(alarmElement()).toBeUndefined()
  })

  it('leaves other sound buses playing when only the alarm is disabled', async () => {
    const manager = await freshManager()
    manager.setMuted(false)
    manager.setAlarmEnabled(false)
    window.dispatchEvent(new Event('pointerdown'))

    manager.play('objectiveClaim', 'sfx')

    expect(MockAudio.instances.at(-1)!.play).toHaveBeenCalled()
  })

  it('parses and persists the alarm toggle', async () => {
    expect(parseSoundSettings({ alarmEnabled: false })).toEqual({ alarmEnabled: false })
    expect(parseSoundSettings({ alarmEnabled: 'no' })).toEqual({})

    const manager = await freshManager()
    manager.setAlarmEnabled(false)

    const stored = JSON.parse(localStorage.getItem('audioSettings')!)
    expect(stored.alarmEnabled).toBe(false)
  })

  it('notifies the change handler when the alarm toggle changes', async () => {
    const manager = await freshManager()
    const handler = vi.fn()
    manager.setChangeHandler(handler)

    manager.setAlarmEnabled(false)

    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler.mock.calls[0][0].alarmEnabled).toBe(false)
  })
})
