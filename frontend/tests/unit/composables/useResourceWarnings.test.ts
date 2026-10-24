import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { createToastMock } from '../helpers/mocks'
import { useResourceWarnings } from '@/modules/vault/composables/useResourceWarnings'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

const mockToast = createToastMock()

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
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
    },
  }
})()

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  configurable: true,
  writable: true,
})

describe('useResourceWarnings', () => {
  let vaultStore: any

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    useVaultBoyFeedback().clear()
    mockToast.error.mockClear()
    mockToast.warning.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows warnings when activeVault has resource_warnings', async () => {
    vaultStore = (await import('@/modules/vault/stores/vault')).useVaultStore()
    useResourceWarnings()

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }],
        },
      },
      activeVaultId: 'test-id',
    })

    await nextTick()

    expect(mockToast.warning).toHaveBeenCalledWith('Power low', 5000)
  })

  it('rate limits warnings (30s cooldown)', async () => {
    vaultStore = (await import('@/modules/vault/stores/vault')).useVaultStore()
    useResourceWarnings()

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }],
        },
      },
      activeVaultId: 'test-id',
    })
    await nextTick()
    expect(mockToast.warning).toHaveBeenCalledTimes(1)

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }],
        },
      },
      activeVaultId: 'test-id',
    })
    await nextTick()
    expect(mockToast.warning).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(31000)

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'low_power', message: 'Power low' }],
        },
      },
      activeVaultId: 'test-id',
    })
    await nextTick()

    expect(mockToast.warning).toHaveBeenCalledTimes(2)
  })

  it('shows critical warnings as error', async () => {
    vaultStore = (await import('@/modules/vault/stores/vault')).useVaultStore()
    useResourceWarnings()

    vaultStore.$patch({
      loadedVaults: {
        'test-id': {
          resource_warnings: [{ type: 'critical_power', message: 'Power Critical' }],
        },
      },
      activeVaultId: 'test-id',
    })
    await nextTick()

    expect(mockToast.error).toHaveBeenCalledWith('Power Critical', 0)
  })
})

it.each([
  ['low_food', 'food-low'],
  ['critical_food', 'food-low'],
  ['low_water', 'water-low'],
  ['critical_dehydration', 'water-low'],
  ['critical_power', 'power-low'],
])('animates %s alongside its resource warning', async (type, expected) => {
  setActivePinia(createPinia())
  useVaultBoyFeedback().clear()
  const store = (await import('@/modules/vault/stores/vault')).useVaultStore()
  useResourceWarnings()
  store.$patch({
    activeVaultId: 'v1',
    loadedVaults: { v1: { resource_warnings: [{ type, message: 'Resource warning' }] } },
  })
  await nextTick()
  expect(useVaultBoyFeedback().current.value).toMatchObject({
    animation: expected,
    vaultId: 'v1',
    message: 'Resource warning',
  })
})

it('shows a warning again when switching to a different vault', async () => {
  setActivePinia(createPinia())
  mockToast.warning.mockClear()
  const store = (await import('@/modules/vault/stores/vault')).useVaultStore()
  useResourceWarnings()
  const vault = { resource_warnings: [{ type: 'low_food', message: 'Food low' }] }
  store.$patch({ activeVaultId: 'v1', loadedVaults: { v1: vault, v2: vault } })
  await nextTick()
  store.activeVaultId = 'v2'
  await nextTick()
  expect(mockToast.warning).toHaveBeenCalledTimes(2)
})
