import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
    const audioManager = await freshManager()
    audioManager.setMuted(false)

    audioManager.startAlarmLoop()
    expect(alarmElement()).toBeUndefined()

    window.dispatchEvent(new Event('pointerdown'))

    expect(alarmElement()).toBeDefined()
    expect(alarmElement()?.play).toHaveBeenCalled()
  })

  it('cancels a running stop fade when the alarm restarts', async () => {
    const audioManager = await freshManager()
    audioManager.setMuted(false)
    window.dispatchEvent(new Event('pointerdown'))

    audioManager.startAlarmLoop()
    const alarm = alarmElement()!

    audioManager.stopAlarmLoop(500)
    audioManager.startAlarmLoop()
    vi.advanceTimersByTime(600)

    expect(alarm.pause).not.toHaveBeenCalled()
    expect(alarm.volume).toBeCloseTo(0.8)
  })
})
