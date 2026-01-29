import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useGaryMode } from '@/core/composables/useGaryMode'

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

describe('useGaryMode', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with Gary mode off', () => {
    const { isGaryMode } = useGaryMode()
    expect(isGaryMode.value).toBe(false)
  })

  it('triggers Gary mode and auto-disables after 10s', () => {
    const { isGaryMode, triggerGaryMode } = useGaryMode()

    triggerGaryMode()
    expect(isGaryMode.value).toBe(true)

    vi.advanceTimersByTime(9999)
    expect(isGaryMode.value).toBe(true)

    vi.advanceTimersByTime(1)
    expect(isGaryMode.value).toBe(false)
  })

  it('persists garyUnlocked to localStorage', () => {
    const { garyUnlocked, triggerGaryMode, resetGaryUnlocked } = useGaryMode()

    resetGaryUnlocked()
    expect(garyUnlocked.value).toBe(false)

    triggerGaryMode()
    expect(garyUnlocked.value).toBe(true)
    expect(localStorage.getItem('fallout_gary_unlocked')).toBe('true')
  })

  it('does not re-trigger if already active', () => {
    const { isGaryMode, triggerGaryMode } = useGaryMode()

    triggerGaryMode()
    expect(isGaryMode.value).toBe(true)

    triggerGaryMode()
    expect(isGaryMode.value).toBe(true)

    vi.advanceTimersByTime(10000)
    expect(isGaryMode.value).toBe(false)
  })

  it('resets garyUnlocked via resetGaryUnlocked', () => {
    const { garyUnlocked, triggerGaryMode, resetGaryUnlocked } = useGaryMode()

    triggerGaryMode()
    expect(garyUnlocked.value).toBe(true)

    resetGaryUnlocked()
    expect(garyUnlocked.value).toBe(false)
  })
})
