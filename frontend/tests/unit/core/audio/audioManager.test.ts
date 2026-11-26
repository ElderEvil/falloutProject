import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { audioManager, parseSoundSettings } from '@/core/audio/audioManager'
import {
  SOUND_MANIFEST,
  MUSIC_MANIFEST,
  AMBIENCE_MANIFEST,
  ROOM_AMBIENCE_MANIFEST,
  THEMED_ROOM_AMBIENCE,
} from '@/core/audio/soundManifest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

it('ships every manifest audio file in the public directory', () => {
  const sources = [
    ...Object.values(SOUND_MANIFEST),
    ...Object.values(AMBIENCE_MANIFEST),
    ...Object.values(ROOM_AMBIENCE_MANIFEST),
    ...Object.values(MUSIC_MANIFEST).flat(),
    ...Object.values(THEMED_ROOM_AMBIENCE),
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

const DEFAULTS = { muted: true, volumes: { ui: 0.6, sfx: 0.8, music: 0.4, ambience: 0.4 } }

/** A fresh module instance per test, so cross-test audio state can't leak. */
async function freshManager() {
  vi.resetModules()
  const { audioManager } = await import('@/core/audio/audioManager')
  return audioManager
}

/** Unmuted manager whose audio has been unlocked by a user gesture. */
async function unlocked() {
  const manager = await freshManager()
  manager.setMuted(false)
  window.dispatchEvent(new Event('pointerdown'))
  return manager
}

/** Unlocked manager with a music playlist already playing. */
async function playingLoop(key: 'vaultAmbient' | 'exploration' = 'vaultAmbient') {
  const manager = await unlocked()
  manager.playLoop(key)
  return manager
}

const findAudio = (fragment: string) =>
  MockAudio.instances.find((audio) => audio.src.includes(fragment))
const alarmElement = () => MockAudio.instances.find((audio) => audio.loop)
const ambienceElement = () => findAudio('/audio/ambience/')
const tracks = () => MockAudio.instances.filter((audio) => audio.src.includes('/audio/music/'))
const currentTrack = () => tracks().at(-1)!
const playingTracks = () => tracks().filter((track) => !track.paused)

beforeEach(() => {
  MockAudio.instances = []
  localStorage.clear()
  vi.stubGlobal('Audio', MockAudio)
  vi.useFakeTimers()
  audioManager.setChangeHandler(null)
  audioManager.applySettings(DEFAULTS)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('audioManager settings', () => {
  it('hydrates from a partial payload, merging per bus', () => {
    audioManager.applySettings({ muted: false, volumes: { music: 0.9 } })

    expect(audioManager.muted).toBe(false)
    expect(audioManager.volumes).toMatchObject({ music: 0.9, ui: 0.6, sfx: 0.8, ambience: 0.4 })
  })

  it('clamps out-of-range volumes', () => {
    audioManager.applySettings({ volumes: { ui: 1.5, sfx: -0.2, music: 0.5 } })

    const { ui, sfx, music } = audioManager.volumes
    expect([ui, sfx, music]).toEqual([1, 0, 0.5])
  })

  it('ignores malformed payloads', () => {
    for (const raw of [null, undefined, 'nope', [1, 2], 42]) audioManager.applySettings(raw)

    expect(audioManager.muted).toBe(true)
    expect(audioManager.volumes).toEqual(DEFAULTS.volumes)
  })

  it('ignores unknown keys and unknown buses', () => {
    audioManager.applySettings({ muted: false, volumes: { ui: 0.3, bass: 0.9 }, extra: 'x' })

    expect(audioManager.volumes).toEqual({ ...DEFAULTS.volumes, ui: 0.3 })
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

    expect(JSON.parse(localStorage.getItem('audioSettings') ?? '{}').volumes.music).toBe(0.9)
  })

  it('parses only objects', () => {
    for (const raw of [null, undefined, [], 'x', 42]) expect(parseSoundSettings(raw)).toBeNull()
  })

  it('keeps only booleans and finite clamped volumes', () => {
    expect(parseSoundSettings({ muted: 'yes', volumes: { ui: 'loud' } })).toEqual({ volumes: {} })
    expect(
      parseSoundSettings({ muted: true, volumes: { ui: 2, sfx: Infinity, music: 0.4 } })
    ).toEqual({ muted: true, volumes: { ui: 1, music: 0.4 } })
  })
})

describe('audioManager alarm', () => {
  it.each(['ui', 'sfx', 'music', 'ambience'] as const)(
    'maps %s volume perceptually while storing a linear preference',
    async (bus) => {
      const manager = await unlocked()
      manager.setVolume(bus, 0.1)
      manager.play('objectiveClaim', bus)

      expect(MockAudio.instances.at(-1)!.volume).toBeCloseTo(0.01)
      expect(manager.volumes[bus]).toBe(0.1)
      expect(JSON.parse(localStorage.getItem('audioSettings')!).volumes[bus]).toBe(0.1)
    }
  )

  it('stops and rewinds a one-shot cue', async () => {
    const manager = await unlocked()
    manager.play('rushGo', 'sfx')
    const audio = MockAudio.instances.at(-1)!
    audio.currentTime = 2

    manager.stop('rushGo')

    expect(audio.pause).toHaveBeenCalled()
    expect(audio.currentTime).toBe(0)
  })

  it('starts an alarm requested before audio unlocks', async () => {
    const manager = await freshManager()
    manager.setMuted(false)

    manager.startAlarmLoop()
    expect(alarmElement()).toBeUndefined()

    window.dispatchEvent(new Event('pointerdown'))

    expect(alarmElement()?.play).toHaveBeenCalled()
  })

  it('keeps the alarm silent after muting during an incident', async () => {
    const manager = await unlocked()
    manager.startAlarmLoop()
    const alarm = alarmElement()!

    manager.setMuted(true)
    expect(alarm.paused).toBe(true)
    manager.startAlarmLoop()
    expect(alarm.play).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(10000)
    expect(alarm.paused).toBe(true)
  })

  it('cancels a running stop fade when the alarm restarts', async () => {
    const manager = await unlocked()
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

    expect(findAudio('vault-ambient')?.play).toHaveBeenCalled()
  })

  it('keeps ducked music paused when playback is reconciled', async () => {
    const manager = await playingLoop()
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
    expect(findAudio('vault-ambient')).toBeUndefined()

    manager.restoreMusic(1000, 500)
    vi.advanceTimersByTime(1000)

    expect(findAudio('vault-ambient')?.play).toHaveBeenCalled()
  })
})

describe('audioManager ambience', () => {
  it('starts a room-category ambience loop at the music volume', async () => {
    const manager = await unlocked()
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
    const manager = await unlocked()
    manager.playAmbience('capacity')
    const first = ambienceElement()!

    manager.playAmbience('capacity')

    expect(ambienceElement()).toBe(first)
    expect(MockAudio.instances.filter((a) => a.src.includes('/audio/ambience/'))).toHaveLength(1)
  })

  it('stops ambience on request', async () => {
    const manager = await unlocked()
    manager.playAmbience('crafting')
    const ambience = ambienceElement()!

    manager.stopAmbience()

    expect(ambience.pause).toHaveBeenCalled()
  })

  it('resumes a muted ambience loop when unmuted', async () => {
    const manager = await unlocked()
    manager.playAmbience('production')
    const ambience = ambienceElement()!
    ambience.play.mockClear()

    manager.setMuted(true)
    expect(ambience.pause).toHaveBeenCalled()

    manager.setMuted(false)
    expect(ambience.play).toHaveBeenCalled()
  })

  it('defers ambience while music is ducked and starts the wanted key on restore', async () => {
    const manager = await playingLoop()
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

    expect(findAudio('training')?.play).toHaveBeenCalled()
    expect(paused.pause).toHaveBeenCalledTimes(2)
  })
})

describe('audioManager navigation regression', () => {
  it('keeps one music loop across vault->exploration->vault (unmuted)', async () => {
    const manager = await unlocked()

    manager.playLoop('vaultAmbient')
    manager.playLoop('exploration')
    manager.playLoop('vaultAmbient')
    manager.playLoop('vaultAmbient')

    expect(playingTracks()).toHaveLength(1)
  })

  it('keeps one music loop when starting muted, then unmuting + hydrating', async () => {
    const manager = await freshManager()
    manager.playLoop('vaultAmbient')
    manager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))
    manager.applySettings({ muted: false })

    manager.playLoop('exploration')
    manager.playLoop('vaultAmbient')

    expect(playingTracks()).toHaveLength(1)
  })
})

describe('audioManager preview overlap', () => {
  it('stops the music preview when a loop starts', async () => {
    const manager = await unlocked()
    manager.previewMusic()
    const preview = MockAudio.instances.at(-1)!
    expect(preview.src).toContain('vault-ambient')
    expect(preview.play).toHaveBeenCalled()

    manager.playLoop('vaultAmbient')

    expect(preview.pause).toHaveBeenCalled()
    expect(MockAudio.instances.filter((a) => !a.paused)).toHaveLength(1)
  })

  it('keeps a playing loop untouched when previewing the music bus', async () => {
    const manager = await playingLoop()
    const loop = MockAudio.instances.filter((a) => a.src.includes('vault-ambient')).at(-1)!
    loop.currentTime = 42
    loop.play.mockClear()

    manager.setVolume('music', 0.8)
    manager.previewMusic()

    expect(MockAudio.instances.filter((a) => a.src.includes('vault-ambient'))).toHaveLength(1)
    expect(loop.play).not.toHaveBeenCalled()
    expect(loop.currentTime).toBe(42)
    expect(loop.volume).toBeCloseTo(0.8 ** 2)
  })

  it('previews the music bus over a ducked (silent) loop for slider feedback', async () => {
    const manager = await playingLoop()
    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    const loop = MockAudio.instances.filter((a) => a.src.includes('vault-ambient')).at(-1)!
    expect(loop.paused).toBe(true)

    manager.previewMusic()

    const previews = MockAudio.instances.filter(
      (a) => a.src.includes('vault-ambient') && a !== loop
    )
    expect(previews).toHaveLength(1)
    expect(previews[0].play).toHaveBeenCalled()
  })

  it('stops a preview started while ducked when the loop is restored', async () => {
    const manager = await playingLoop()
    const loop = MockAudio.instances.filter((a) => a.src.includes('vault-ambient')).at(-1)!
    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    manager.previewMusic()
    const preview = MockAudio.instances.filter((a) => a.src.includes('vault-ambient')).at(-1)!
    expect(preview).not.toBe(loop)

    manager.restoreMusic(0)
    vi.advanceTimersByTime(1)

    expect(preview.paused).toBe(true)
    expect(
      MockAudio.instances.filter((a) => a.src.includes('vault-ambient') && !a.paused)
    ).toHaveLength(1)
  })

  it('stops an ambience preview started while ducked when ambience is restored', async () => {
    const manager = await unlocked()
    manager.playAmbience('production')

    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    manager.previewAmbience()
    const previews = MockAudio.instances.filter(
      (a) => a.src.includes('/audio/ambience/') && !a.loop
    )
    expect(previews).toHaveLength(1)

    manager.restoreMusic(0)
    vi.advanceTimersByTime(1)

    expect(previews[0].paused).toBe(true)
    expect(
      MockAudio.instances.filter((a) => a.src.includes('/audio/ambience/') && !a.paused)
    ).toHaveLength(1)
  })

  it('still previews the music bus when no loop is playing', async () => {
    const manager = await unlocked()

    manager.previewMusic()

    expect(
      MockAudio.instances.filter((a) => a.src.includes('vault-ambient')).at(-1)!.play
    ).toHaveBeenCalled()
  })

  it('keeps a live ambience loop untouched when previewing the ambience bus', async () => {
    const manager = await unlocked()
    manager.playAmbience('production')
    const ambience = MockAudio.instances.filter((a) => a.src.includes('/audio/ambience/')).at(-1)!
    ambience.currentTime = 30
    ambience.play.mockClear()

    manager.previewAmbience()

    expect(MockAudio.instances.filter((a) => a.src.includes('/audio/ambience/'))).toHaveLength(1)
    expect(ambience.play).not.toHaveBeenCalled()
    expect(ambience.currentTime).toBe(30)
  })
})

describe('audioManager ambience bus', () => {
  it('routes the ambience slider to the ambience element, not the music loop', async () => {
    const manager = await playingLoop()
    manager.playAmbience('production')
    const loop = findAudio('/audio/music/')!
    const ambience = MockAudio.instances.find((a) => a.loop && a.src.includes('/audio/ambience/'))!

    manager.setVolume('ambience', 0.2)

    expect(ambience.volume).toBeCloseTo(0.2 ** 2)
    expect(loop.volume).toBeCloseTo(0.4 ** 2)
  })

  it('stops the ambience preview when a room ambience loop starts', async () => {
    const manager = await unlocked()
    manager.previewAmbience()
    const preview = MockAudio.instances.find((a) => a.src.includes('/audio/ambience/') && !a.loop)!
    expect(preview.play).toHaveBeenCalled()

    manager.playAmbience('production')

    expect(preview.pause).toHaveBeenCalled()
  })
})

describe('audioManager music rotation', () => {
  it('plays the first entry of the playlist', async () => {
    await playingLoop()

    expect(currentTrack().src).toContain('vault-ambient-1.mp3')
    expect(currentTrack().play).toHaveBeenCalled()
  })

  it('crossfades into the next entry as the playing track nears its end', async () => {
    await playingLoop()
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 59

    first.emit('timeupdate')

    expect(currentTrack().src).toContain('vault-ambient-2.mp3')
    expect(currentTrack().play).toHaveBeenCalled()
  })

  it('ignores late events from the track that already handed over', async () => {
    await playingLoop()
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 60
    first.emit('timeupdate')

    first.emit('ended')
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(2)
  })

  it('advances on ended when the duration is unknown', async () => {
    await playingLoop('exploration')
    const first = currentTrack()
    expect(first.duration).toBe(0)

    first.emit('ended')

    expect(currentTrack().src).toContain('exploration-2.mp3')
  })

  it('wraps back to the first entry after the last one', async () => {
    await playingLoop('exploration')

    for (let i = 0; i < 4; i += 1) currentTrack().emit('ended')

    expect(currentTrack().src).toContain('exploration-1.mp3')
    expect(tracks()).toHaveLength(5)
  })

  it('silences the fading track when the loop stops mid-crossfade', async () => {
    const manager = await playingLoop()
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
    const manager = await playingLoop()
    const first = currentTrack()
    first.duration = 60
    first.currentTime = 30

    manager.playLoop('vaultAmbient')
    manager.playLoop('vaultAmbient')

    expect(tracks()).toHaveLength(1)
    expect(currentTrack()).toBe(first)
  })

  it('does not advance while the duration is unknown', async () => {
    await playingLoop()
    const first = currentTrack()

    first.duration = 0
    first.emit('timeupdate')
    first.duration = Number.NaN
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(1)
  })

  it('does not restart itself after the loop stops', async () => {
    const manager = await playingLoop()
    const first = currentTrack()

    manager.stopLoop()
    first.emit('ended')
    first.emit('timeupdate')

    expect(tracks()).toHaveLength(1)
    expect(first.pause).toHaveBeenCalled()
  })

  it('never starts a ducked advance audibly', async () => {
    const manager = await playingLoop()
    manager.duckMusic()
    vi.advanceTimersByTime(2000)
    const first = currentTrack()

    // A near-end tick while ducked must not crossfade.
    first.duration = 60
    first.currentTime = 59
    first.emit('timeupdate')
    expect(tracks()).toHaveLength(1)
    expect(playingTracks()).toHaveLength(0)

    // An ended track still queues the next entry, silently.
    first.emit('ended')
    expect(playingTracks()).toHaveLength(0)
    expect(currentTrack().src).toContain('vault-ambient-2.mp3')
  })

  it('resumes the queued entry when the duck ends', async () => {
    const manager = await playingLoop()
    manager.duckMusic()
    currentTrack().emit('ended')

    const queued = currentTrack()
    manager.restoreMusic(0)
    vi.advanceTimersByTime(0)

    expect(queued.play).toHaveBeenCalled()
  })

  it('silences the previous track once the crossfade completes', async () => {
    await playingLoop()
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
  it('leaves the alarm enabled by default', async () => {
    expect((await freshManager()).alarmEnabled).toBe(true)
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
    const manager = await unlocked()
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

    expect(JSON.parse(localStorage.getItem('audioSettings')!).alarmEnabled).toBe(false)
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

describe('audioManager restore fade slider', () => {
  it('retargets the music restore fade when the slider moves between ticks', async () => {
    const manager = await playingLoop()
    const loop = findAudio('/audio/music/')!
    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    expect(loop.paused).toBe(true)

    manager.restoreMusic(0, 1000)
    vi.advanceTimersByTime(1) // restore fires; fade-in starts (20 ticks of 50ms)
    vi.advanceTimersByTime(200) // 4 ticks toward the original 0.4 slider target
    const midFade = loop.volume
    expect(midFade).toBeGreaterThan(0)
    expect(midFade).toBeLessThan(0.4 ** 2)

    manager.setVolume('music', 0.9)
    vi.advanceTimersByTime(50) // next tick must not snap back to the old target
    expect(loop.volume).toBeGreaterThanOrEqual(midFade)
    vi.advanceTimersByTime(800) // fade completes at the latest slider value

    expect(loop.volume).toBeCloseTo(0.9 ** 2)
    expect(loop.paused).toBe(false)
  })

  it('retargets the ambience restore fade when the slider moves between ticks', async () => {
    const manager = await unlocked()
    manager.playAmbience('production')
    const ambience = ambienceElement()!
    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    expect(ambience.paused).toBe(true)

    manager.restoreMusic(0, 1000)
    vi.advanceTimersByTime(201) // restore fires, then 4 fade ticks
    manager.setVolume('ambience', 0.7)
    vi.advanceTimersByTime(850)

    expect(ambience.volume).toBeCloseTo(0.7 ** 2)
    expect(ambience.paused).toBe(false)
  })

  it('lets a duck fade finish at zero and pause even if the slider moves', async () => {
    const manager = await playingLoop()
    const loop = findAudio('/audio/music/')!

    manager.duckMusic(1000)
    vi.advanceTimersByTime(200)
    manager.setVolume('music', 0.9)
    vi.advanceTimersByTime(850)

    expect(loop.pause).toHaveBeenCalled()
    expect(loop.paused).toBe(true)
    expect(loop.volume).toBeCloseTo(0)
  })
})

describe('audioManager themed room music', () => {
  const themedTrack = (file: string) =>
    MockAudio.instances.find(
      (a) => a.src.includes('/audio/ambience/themed/') && a.src.includes(file)
    )!
  const playlistLoop = () => findAudio('/audio/music/vault-ambient')!

  async function themedManager() {
    const manager = await playingLoop()
    manager.playThemedRoomMusic('diner:xmas')
    return manager
  }

  it('suspends the playlist for the themed track and restores it in place', async () => {
    const manager = await playingLoop()
    const loop = playlistLoop()
    loop.currentTime = 10
    loop.play.mockClear()

    manager.playThemedRoomMusic('diner:xmas')

    const themed = themedTrack('diner-xmas')
    expect(themed.loop).toBe(true)
    expect(themed.paused).toBe(false)
    expect([loop.paused, loop.currentTime]).toEqual([true, 10])

    manager.setVolume('music', 0.9)
    // The themed track fades in; the slider retargets the fade to the new value.
    vi.advanceTimersByTime(700)
    expect(themed.volume).toBeCloseTo(0.9 ** 2)

    manager.stopThemedRoomMusic()

    expect(themed.paused).toBe(true)
    expect(loop.paused).toBe(false)
    expect(loop.currentTime).toBe(10)
    expect(loop.play).toHaveBeenCalled()
  })

  it('swaps themed rooms while the playlist stays suspended', async () => {
    const manager = await themedManager()

    manager.playThemedRoomMusic('diner:brotherhood')

    expect(themedTrack('diner-xmas').paused).toBe(true)
    expect(themedTrack('diner-brotherhood').paused).toBe(false)
    expect(playlistLoop().paused).toBe(true)

    manager.stopThemedRoomMusic()
    expect(playlistLoop().paused).toBe(false)
  })

  it('resumes the themed track after mute instead of the suspended playlist', async () => {
    const manager = await themedManager()

    manager.setMuted(true)
    manager.setMuted(false)

    expect(themedTrack('diner-xmas').paused).toBe(false)
    expect(playlistLoop().paused).toBe(true)

    manager.stopThemedRoomMusic()
    expect(playlistLoop().paused).toBe(false)
  })

  it('ducks and restores themed room music while the playlist stays suspended', async () => {
    const manager = await themedManager()

    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    const themed = themedTrack('diner-xmas')
    expect(themed.paused).toBe(true)

    manager.restoreMusic(0)
    vi.advanceTimersByTime(1)

    expect(themed.paused).toBe(false)
    expect(playlistLoop().paused).toBe(true)

    manager.stopThemedRoomMusic()
    expect(playlistLoop().paused).toBe(false)
  })

  it('starts the suspended playlist when the themed modal closes before the duck restores', async () => {
    const manager = await themedManager()

    manager.duckMusic(500)
    vi.advanceTimersByTime(600)
    manager.stopThemedRoomMusic()
    expect(playlistLoop().paused).toBe(true)

    manager.restoreMusic(0)
    vi.advanceTimersByTime(1)

    expect(playlistLoop().paused).toBe(false)
  })

  it('hands the music bus back when a playlist starts over a themed room', async () => {
    const manager = await themedManager()

    manager.playLoop('exploration')

    expect(findAudio('exploration-1')!.paused).toBe(false)
    expect(themedTrack('diner-xmas').paused).toBe(true)
    expect(playlistLoop().paused).toBe(true)
  })

  it('defers the music preview while the themed track plays', async () => {
    const manager = await themedManager()
    const before = MockAudio.instances.filter((a) => a.src.includes('vault-ambient')).length

    manager.previewMusic()

    expect(MockAudio.instances.filter((a) => a.src.includes('vault-ambient'))).toHaveLength(before)
  })
})
