import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useFakeCrash } from '@/core/composables/useFakeCrash'

const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    }
  }
})()

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  configurable: true,
  writable: true
})

describe('useFakeCrash', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with crash off', () => {
    const { isCrashing } = useFakeCrash()
    expect(isCrashing.value).toBe(false)
  })

  it('triggers crash after 7 clicks', () => {
    const { isCrashing, clickCount, handleVersionClick } = useFakeCrash()

    for (let i = 0; i < 6; i++) {
      handleVersionClick()
      expect(isCrashing.value).toBe(false)
    }

    expect(clickCount.value).toBe(6)

    handleVersionClick()
    expect(isCrashing.value).toBe(true)
    expect(clickCount.value).toBe(0)
  })

  it('resets click count after 2s timeout', () => {
    const { clickCount, handleVersionClick } = useFakeCrash()

    handleVersionClick()
    handleVersionClick()
    expect(clickCount.value).toBe(2)

    vi.advanceTimersByTime(2000)
    expect(clickCount.value).toBe(0)
  })

  it('resets timer on each click within window', () => {
    const { clickCount, handleVersionClick } = useFakeCrash()

    handleVersionClick()
    vi.advanceTimersByTime(1000)
    handleVersionClick()
    vi.advanceTimersByTime(1000)
    handleVersionClick()

    expect(clickCount.value).toBe(3)

    vi.advanceTimersByTime(2000)
    expect(clickCount.value).toBe(0)
  })

  it('persists crashUnlocked to localStorage', () => {
    const { crashUnlocked, handleVersionClick, resetCrashUnlocked } = useFakeCrash()

    resetCrashUnlocked()
    expect(crashUnlocked.value).toBe(false)

    for (let i = 0; i < 7; i++) {
      handleVersionClick()
    }

    expect(crashUnlocked.value).toBe(true)
  })

  it('does not re-trigger if already crashing', () => {
    const { isCrashing, triggerFakeCrash } = useFakeCrash()

    triggerFakeCrash()
    expect(isCrashing.value).toBe(true)

    triggerFakeCrash()
    expect(isCrashing.value).toBe(true)
  })

  it('resets crash state via resetCrash', () => {
    const { isCrashing, triggerFakeCrash, resetCrash } = useFakeCrash()

    triggerFakeCrash()
    expect(isCrashing.value).toBe(true)

    resetCrash()
    expect(isCrashing.value).toBe(false)
  })
})
