import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useResourceWarnings } from '@/composables/useResourceWarnings'
import { ref, nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

const mockToastAdd = vi.fn()
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    add: mockToastAdd
  })
}))

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
  value: localStorageMock
})

describe('useResourceWarnings', () => {
  let vaultStore: any

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    mockToastAdd.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows warnings when activeVault has resource_warnings', async () => {
    vaultStore = (await import('@/stores/vault')).useVaultStore()
    useResourceWarnings()

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }]
        }
      },
      activeVaultId: 'test-id'
    })

    await nextTick()

    expect(mockToastAdd).toHaveBeenCalledWith({
      message: 'Power low',
      variant: 'warning',
      duration: 5000
    })
  })

  it('rate limits warnings (30s cooldown)', async () => {
    vaultStore = (await import('@/stores/vault')).useVaultStore()
    useResourceWarnings()

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }]
        }
      },
      activeVaultId: 'test-id'
    })
    await nextTick()
    expect(mockToastAdd).toHaveBeenCalledTimes(1)

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }]
        }
      },
      activeVaultId: 'test-id'
    })
    await nextTick()
    expect(mockToastAdd).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(31000)

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }]
        }
      },
      activeVaultId: 'test-id'
    })
    await nextTick()

    expect(mockToastAdd).toHaveBeenCalledTimes(2)
  })

  it('shows critical warnings as error', async () => {
    vaultStore = (await import('@/stores/vault')).useVaultStore()
    useResourceWarnings()

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'critical_power', message: 'Power Critical' }]
        }
      },
      activeVaultId: 'test-id'
    })
    await nextTick()

    expect(mockToastAdd).toHaveBeenCalledWith({
      message: 'Power Critical',
      variant: 'error',
      duration: 0
    })
  })
})
