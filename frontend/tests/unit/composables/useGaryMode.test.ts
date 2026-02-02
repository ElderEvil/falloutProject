import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'

// Create a factory that returns a new map each time
function createStorageMapMock() {
  const storageMap = new Map<string, any>()
  return {
    useLocalStorage: (key: string, defaultValue: any) => {
      const value = ref(storageMap.get(key) ?? defaultValue)
      return {
        get value() {
          return value.value
        },
        set value(v) {
          value.value = v
          storageMap.set(key, v)
          // Also write to global localStorage for compatibility
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(key, String(v))
          }
        }
      }
    },
    clear: () => storageMap.clear()
  }
}

var mockInstance: any = null

vi.mock('@vueuse/core', () => {
  if (!mockInstance) {
    mockInstance = createStorageMapMock()
  }
  return {
    useLocalStorage: (key: string, defaultValue: any) => {
      return mockInstance.useLocalStorage(key, defaultValue)
    }
  }
})

import { useGaryMode } from '@/core/composables/useGaryMode'

// Initialize mockInstance after import (it's created in the mock)
if (!mockInstance) {
  mockInstance = createStorageMapMock()
}

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
    vi.useFakeTimers()
    mockInstance.clear()
    localStorage.clear()
    // Reset composable state
    const { isGaryMode, resetGaryUnlocked } = useGaryMode()
    isGaryMode.value = false
    resetGaryUnlocked()
    vi.clearAllTimers()
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
