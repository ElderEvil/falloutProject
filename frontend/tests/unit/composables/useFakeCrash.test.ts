import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, watch, nextTick } from 'vue'

vi.mock('@vueuse/core', () => {
  return {
    useLocalStorage: (key: string, defaultValue: any) => {
      const storedValue = localStorage.getItem(key)
      const value = ref(storedValue ? JSON.parse(storedValue) : defaultValue)

      watch(value, (newVal) => {
        localStorage.setItem(key, JSON.stringify(newVal))
      }, { immediate: false, flush: 'sync' })

      return value
    },
    useIntervalFn: vi.fn(() => ({
      pause: vi.fn(),
      resume: vi.fn(),
      isActive: ref(false)
    }))
  }
})

import { useFakeCrash } from '@/core/composables/useFakeCrash'

describe('useFakeCrash', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    const { resetCrash, resetCrashUnlocked } = useFakeCrash()
    resetCrash()
    resetCrashUnlocked()
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

  it('persists crashUnlocked to localStorage', async () => {
    const { crashUnlocked, handleVersionClick, resetCrashUnlocked } = useFakeCrash()

    resetCrashUnlocked()
    await nextTick()
    expect(crashUnlocked.value).toBe(false)

    for (let i = 0; i < 7; i++) {
      handleVersionClick()
    }

    await nextTick()
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
