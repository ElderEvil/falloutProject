import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'

// Mock @vueuse/core before importing the composable
const storageMap = new Map<string, any>()
const refMap = new Map<string, any>()

vi.mock('@vueuse/core', () => ({
  useLocalStorage: (key: string, defaultValue: any) => {
    // Access the maps from the outer scope
    const maps = { storageMap, refMap }
    if (!maps.refMap.has(key)) {
      const value = ref(maps.storageMap.get(key) ?? defaultValue)
      maps.refMap.set(key, value)
    }
    return maps.refMap.get(key)!
  }
}))

import { useFakeCrash } from '@/core/composables/useFakeCrash'

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
