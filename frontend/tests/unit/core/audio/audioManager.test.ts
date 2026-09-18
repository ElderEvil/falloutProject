import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { audioManager, parseSoundSettings } from '@/core/audio/audioManager'

class MockAudio {
  volume = 1
  currentTime = 0
  loop = false
  preload = 'none'
  paused = true
  src = ''

  constructor(src?: string) {
    this.src = src ?? ''
  }

  play() {
    this.paused = false
    return Promise.resolve()
  }

  pause() {
    this.paused = true
  }
}

const DEFAULTS = { muted: true, volumes: { ui: 0.6, sfx: 0.8, music: 0.4 } }

describe('audioManager', () => {
  beforeEach(() => {
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
    expect(audioManager.volumes).toEqual({ ui: 0.6, sfx: 0.8, music: 0.4 })
  })

  it('ignores unknown keys and unknown buses', () => {
    audioManager.applySettings({ muted: false, volumes: { ui: 0.3, bass: 0.9 }, extra: 'x' })
    expect(audioManager.volumes).toEqual({ ui: 0.3, sfx: 0.8, music: 0.4 })
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
