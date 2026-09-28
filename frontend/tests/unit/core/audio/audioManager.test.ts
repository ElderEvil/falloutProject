import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { audioManager, parseSoundSettings } from '@/core/audio/audioManager'

class MockAudio {
  static instances: MockAudio[] = []
  volume = 1
  currentTime = 0
  loop = false
  preload = 'none'
  paused = true
  src = ''
  play = vi.fn(() => {
    this.paused = false
    return Promise.resolve()
  })

  pause = vi.fn(() => {
    this.paused = true
  })

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

  it('starts an alarm requested before audio unlocks', async () => {
    const manager = await freshManager()
    manager.setMuted(false)

    manager.startAlarmLoop()
    expect(alarmElement()).toBeUndefined()

    window.dispatchEvent(new Event('pointerdown'))

    expect(alarmElement()).toBeDefined()
    expect(alarmElement()?.play).toHaveBeenCalled()
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
    expect(alarm.volume).toBeCloseTo(0.8)
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
    expect(ambience?.volume).toBeCloseTo(0.4)
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
    expect(MockAudio.instances.filter((audio) => audio.src.includes('/audio/ambience/'))).toHaveLength(1)
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

  const playing = () => MockAudio.instances.filter((a) => a.loop && !a.paused)

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
    const preview = MockAudio.instances.find((a) => a.src.includes('vault-ambient') && !a.loop)!
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

    const loop = MockAudio.instances.find((a) => a.loop && a.src.includes('vault-ambient'))!
    const ambience = MockAudio.instances.find((a) => a.loop && a.src.includes('/audio/ambience/'))!

    manager.setVolume('ambience', 0.2)

    expect(ambience.volume).toBeCloseTo(0.2)
    expect(loop.volume).toBeCloseTo(0.4)
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
