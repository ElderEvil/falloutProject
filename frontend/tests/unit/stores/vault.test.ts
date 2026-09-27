import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick, ref, type Ref } from 'vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import axios from '@/core/plugins/axios'
import { useRouter } from 'vue-router'

const sseMock = vi.hoisted(() => ({
  event: null as unknown,
  start: vi.fn().mockResolvedValue(undefined),
  close: vi.fn(),
  stopReconnect: vi.fn(),
}))

vi.mock('@/core/plugins/axios')
vi.mock('vue-router', () => ({
  useRouter: vi.fn(),
}))
vi.mock('@/core/composables/useEventStream', () => ({
  useSse: () => sseMock,
}))

describe('Vault Store', () => {
  let mockRouter: any

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    sseMock.event = ref(null) as Ref<unknown>

    mockRouter = {
      push: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(useRouter).mockReturnValue(mockRouter)
  })

  const mockVault = {
    id: 'vault-1',
    number: 101,
    bottle_caps: 1000,
    happiness: 75,
    power: 50,
    power_max: 100,
    food: 80,
    food_max: 100,
    water: 90,
    water_max: 100,
    population_max: 50,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    room_count: 5,
    dweller_count: 10,
  }

  describe('State Initialization', () => {
    it('should initialize with empty state', () => {
      const store = useVaultStore()
      expect(store.vaults).toEqual([])
      expect(store.selectedVaultId).toBeNull()
      expect(store.loadedVaults).toEqual({})
      expect(store.activeVaultId).toBeNull()
      expect(store.isLoading).toBe(false)
    })

    it('should load selectedVaultId from localStorage', () => {
      localStorage.setItem('selectedVaultId', 'vault-1')
      const store = useVaultStore()
      expect(store.selectedVaultId).toBe('vault-1')
    })
  })

  describe('Getters', () => {
    it('selectedVault should return the selected vault', () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      store.selectedVaultId = 'vault-1'

      expect(store.selectedVault).toEqual(mockVault)
    })

    it('selectedVault should return null when no vault is selected', () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      expect(store.selectedVault).toBeNull()
    })

    it('activeVault should return the active vault', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'
      store.selectedVaultId = 'vault-1'

      expect(store.activeVault).toEqual(mockVault)
    })

    it('activeVault should return null when no vault is active', () => {
      const store = useVaultStore()
      expect(store.activeVault).toBeNull()
    })

    it('loadedVaultIds should return array of loaded vault IDs', () => {
      const store = useVaultStore()
      store.loadedVaults = {
        'vault-1': mockVault,
        'vault-2': { ...mockVault, id: 'vault-2' },
      }

      expect(store.loadedVaultIds).toEqual(['vault-1', 'vault-2'])
    })

    it('currentVaultId falls back to the persisted selection when no vault is active', () => {
      const store = useVaultStore()
      store.selectedVaultId = 'vault-1'

      expect(store.activeVaultId).toBeNull()
      expect(store.currentVaultId).toBe('vault-1')
    })

    it('currentVaultId prefers the active vault over the persisted selection', () => {
      const store = useVaultStore()
      store.selectedVaultId = 'vault-1'
      store.activeVaultId = 'vault-2'

      expect(store.currentVaultId).toBe('vault-2')
    })
  })

  describe('fetchVaults Action', () => {
    it('should fetch vaults successfully', async () => {
      const store = useVaultStore()
      const mockResponse = {
        data: [mockVault, { ...mockVault, id: 'vault-2' }],
      }

      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse)

      await store.fetchVaults('test-token')

      expect(store.vaults).toEqual(mockResponse.data)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/vaults/my', {
        headers: { Authorization: 'Bearer test-token' },
      })
    })

    it('should handle fetch error gracefully', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      await store.fetchVaults('test-token')

      expect(store.vaults).toEqual([])
    })
  })

  describe('createVault Action', () => {
    it('blocks creation when the refreshed vault list is already at the limit', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault, { ...mockVault, id: 'vault-2' }]
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [mockVault, { ...mockVault, id: 'vault-2' }, { ...mockVault, id: 'vault-3' }],
      })

      expect(await store.createVault(104, false, 'test-token')).toBe(false)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('does not create a vault when the current list cannot be checked', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      expect(await store.createVault(104, false, 'test-token')).toBe(false)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('should create vault and refresh list', async () => {
      const store = useVaultStore()
      vi.mocked(axios.post).mockResolvedValueOnce({})
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [mockVault] })

      await store.createVault(101, false, 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/vaults/initiate',
        { number: 101, boosted: false },
        { headers: { Authorization: 'Bearer test-token' } }
      )
      expect(store.vaults).toEqual([mockVault])
    })

    it('reports success when the vault is created even if the refresh fails', async () => {
      const store = useVaultStore()
      vi.mocked(axios.post).mockResolvedValueOnce({})
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: [] })
        .mockRejectedValueOnce(new Error('Fetch failed'))

      expect(await store.createVault(101, false, 'test-token')).toBe(true)
      expect(axios.post).toHaveBeenCalled()
    })

    it('should handle creation error gracefully', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Create failed'))

      await store.createVault(101, false, 'test-token')

      expect(store.vaults).toEqual([])
    })
  })

  describe('deleteVault Action', () => {
    it('should delete vault successfully', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault, { ...mockVault, id: 'vault-2' }]
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'
      store.selectedVaultId = 'vault-1'

      vi.mocked(axios.delete).mockResolvedValueOnce({})

      await store.deleteVault('vault-1', 'test-token')

      expect(store.vaults).toHaveLength(1)
      expect(store.vaults[0].id).toBe('vault-2')
      expect(store.loadedVaults['vault-1']).toBeUndefined()
      expect(store.activeVaultId).toBeNull()
      expect(store.selectedVaultId).toBeNull()
      expect(store.currentVaultId).toBeNull()
    })

    it('should set new active vault when deleting current active vault', async () => {
      const store = useVaultStore()
      const vault2 = { ...mockVault, id: 'vault-2' }
      store.vaults = [mockVault, vault2]
      store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vault2 }
      store.activeVaultId = 'vault-1'
      store.selectedVaultId = 'vault-1'

      vi.mocked(axios.delete).mockResolvedValueOnce({})

      await store.deleteVault('vault-1', 'test-token')

      expect(store.activeVaultId).toBe('vault-2')
      expect(store.selectedVaultId).toBe('vault-2')
    })

    it('should handle delete error gracefully', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Delete failed'))

      await store.deleteVault('vault-1', 'test-token')

      expect(store.vaults).toHaveLength(1)
    })
  })

  describe('ensureVaultLoaded Action', () => {
    it('should load vault and set active vault', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      await store.ensureVaultLoaded('vault-1', 'test-token')

      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-1')
      expect(store.selectedVaultId).toBe('vault-1')
      expect(store.isLoading).toBe(false)
    })

    it('should set loading state correctly', async () => {
      const store = useVaultStore()
      let loadingDuringFetch = false

      vi.mocked(axios.get).mockImplementation(async () => {
        loadingDuringFetch = store.isLoading
        return { data: mockVault }
      })

      await store.ensureVaultLoaded('vault-1', 'test-token')

      expect(loadingDuringFetch).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('should handle load error and rethrow', async () => {
      const store = useVaultStore()
      const error = new Error('Load failed')
      vi.mocked(axios.get).mockRejectedValueOnce(error)

      await expect(store.ensureVaultLoaded('vault-1', 'test-token')).rejects.toThrow('Load failed')
      expect(store.isLoading).toBe(false)
    })

    it('deduplicates concurrent loads for the same vault', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      const first = store.ensureVaultLoaded('vault-1', 'test-token')
      const second = store.ensureVaultLoaded('vault-1', 'test-token')
      await Promise.all([first, second])

      expect(axios.get).toHaveBeenCalledTimes(1)
      expect(sseMock.start).toHaveBeenCalledTimes(1)
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
    })

    it('returns without a GET for an already-loaded vault but re-asserts the stream', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      await store.ensureVaultLoaded('vault-1', 'test-token')
      await store.ensureVaultLoaded('vault-1', 'test-token')

      expect(axios.get).not.toHaveBeenCalled()
      expect(store.activeVaultId).toBe('vault-1')
      expect(store.selectedVaultId).toBe('vault-1')
      // The stream is already for vault-1, so re-asserting it starts no second SSE.
      expect(sseMock.start).toHaveBeenCalledTimes(1)
    })

    it('does not adopt a stale response for a superseded vault', async () => {
      const store = useVaultStore()
      let resolveVaultA: (value: unknown) => void
      vi.mocked(axios.get).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveVaultA = resolve
          })
      )

      const loadA = store.ensureVaultLoaded('vault-1', 'test-token')
      const vaultB = { ...mockVault, id: 'vault-2' }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: vaultB })
      await store.ensureVaultLoaded('vault-2', 'test-token')

      expect(store.activeVaultId).toBe('vault-2')

      resolveVaultA({ data: mockVault })
      await loadA

      // A is still cached, but B remains active and its stream is untouched.
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-2')
      expect(store.selectedVaultId).toBe('vault-2')
      expect(sseMock.start).toHaveBeenCalledTimes(1)
    })

    it('starts the new vault stream when the previous vault was paused', async () => {
      const store = useVaultStore()
      store.loadedVaults = {
        'vault-1': mockVault,
        'vault-2': { ...mockVault, id: 'vault-2' },
      }
      await store.ensureVaultLoaded('vault-1', 'test-token')
      store.gameState = { is_paused: true }
      store.stopResourcePolling()

      await store.ensureVaultLoaded('vault-2', 'test-token')

      expect(store.activeVaultId).toBe('vault-2')
      expect(store.gameState).toBeNull()
      expect(sseMock.start).toHaveBeenCalledTimes(2)
    })

    it('is a no-op without an id or token', async () => {
      const store = useVaultStore()

      await store.ensureVaultLoaded('', 'test-token')
      await store.ensureVaultLoaded('vault-1', '')

      expect(axios.get).not.toHaveBeenCalled()
      expect(store.activeVaultId).toBeNull()
    })
  })

  describe('revalidateVault Action', () => {
    it('fetches fresh data for a cached vault on each route entry', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: { ...mockVault, bottle_caps: 1200 } })
        .mockResolvedValueOnce({ data: { ...mockVault, bottle_caps: 1400 } })

      await store.revalidateVault('vault-1', 'test-token')
      await store.revalidateVault('vault-1', 'test-token')

      expect(axios.get).toHaveBeenCalledTimes(2)
      expect(store.loadedVaults['vault-1'].bottle_caps).toBe(1400)
    })

    it('shares an in-flight header load rather than requesting the same vault twice', async () => {
      const store = useVaultStore()
      let resolveLoad!: (value: unknown) => void
      vi.mocked(axios.get).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveLoad = resolve
          })
      )

      const headerLoad = store.ensureVaultLoaded('vault-1', 'test-token')
      const routeLoad = store.revalidateVault('vault-1', 'test-token')
      resolveLoad({ data: mockVault })
      await Promise.all([headerLoad, routeLoad])

      expect(axios.get).toHaveBeenCalledTimes(1)
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
    })

    it('does not toast when a superseded vault load fails, but still rejects', async () => {
      const store = useVaultStore()
      const { toasts } = useToast()
      toasts.value = []
      let rejectOldLoad!: (reason: Error) => void
      vi.mocked(axios.get).mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectOldLoad = reject
          })
      )

      const oldLoad = store.ensureVaultLoaded('vault-1', 'test-token')
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { ...mockVault, id: 'vault-2' } })
      await store.ensureVaultLoaded('vault-2', 'test-token')
      rejectOldLoad(new Error('Old vault failed'))

      await expect(oldLoad).rejects.toThrow('Old vault failed')
      expect(toasts.value.some((toast) => toast.message.includes('Old vault failed'))).toBe(false)
    })
  })

  describe('refreshVault Action', () => {
    it('persists the vault as the selected vault so navigation survives a reload', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      await store.refreshVault('vault-1', 'test-token')

      expect(store.activeVaultId).toBe('vault-1')
      expect(store.selectedVaultId).toBe('vault-1')

      // A fresh store instance (as after a page reload) still knows the selection.
      setActivePinia(createPinia())
      expect(useVaultStore().selectedVaultId).toBe('vault-1')
    })

    it('only caches a late refresh after another vault becomes active', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      await store.ensureVaultLoaded('vault-1', 'test-token')
      let resolveRefresh!: (value: unknown) => void
      vi.mocked(axios.get).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRefresh = resolve
          })
      )
      const refresh = store.refreshVault('vault-1', 'test-token')

      store.loadedVaults['vault-2'] = { ...mockVault, id: 'vault-2' }
      await store.ensureVaultLoaded('vault-2', 'test-token')
      resolveRefresh({ data: { ...mockVault, bottle_caps: 1200 } })
      await refresh

      expect(store.loadedVaults['vault-1'].bottle_caps).toBe(1200)
      expect(store.activeVaultId).toBe('vault-2')
      expect(store.selectedVaultId).toBe('vault-2')
      expect(sseMock.start).toHaveBeenCalledTimes(2)
    })
  })

  describe('resource polling', () => {
    it('does not write an old vault response into the newly selected vault', async () => {
      vi.useFakeTimers()
      try {
        const store = useVaultStore()
        const vaultB = { ...mockVault, id: 'vault-2', power: 70 }
        store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vaultB }
        store.setActiveVault('vault-1')
        let resolvePoll!: (value: unknown) => void
        vi.mocked(axios.get).mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolvePoll = resolve
            })
        )

        store.startResourcePolling()
        vi.advanceTimersByTime(10000)
        store.setActiveVault('vault-2')
        resolvePoll({ data: { ...mockVault, power: 10 } })
        await nextTick()

        expect(store.loadedVaults['vault-2']).toEqual(vaultB)
        store.stopResourcePolling()
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('game tick updates', () => {
    it('handles each tick once after replacing a vault stream', async () => {
      const store = useVaultStore()
      const { toasts } = useToast()
      toasts.value = []

      store.startGameTickSse('vault-1', 'test-token')
      store.startGameTickSse('vault-2', 'test-token')
      ;(sseMock.event as Ref<{ event: string; data: unknown } | null>).value = {
        event: 'tick',
        data: { updates: { crafting: { completed: 1 } } },
      }
      await nextTick()

      expect(
        toasts.value.filter((toast) => toast.message === 'A workshop order is ready to collect')
      ).toHaveLength(1)
    })

    it('merges tick resources and exposes the net rate per minute', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      store.startGameTickSse('vault-1', 'test-token')
      ;(sseMock.event as Ref<{ event: string; data: unknown } | null>).value = {
        event: 'tick',
        data: {
          seconds_passed: 60,
          updates: {
            resources: {
              power: 60,
              food: 75,
              water: 86,
              events: {
                production: { power: 15, food: 2, water: 9 },
                consumption: { power: 5, food: 7, water: 4 },
              },
            },
          },
        },
      }
      await nextTick()

      expect(store.loadedVaults['vault-1']).toMatchObject({
        ...mockVault,
        power: 60,
        food: 75,
        water: 86,
      })
      expect(store.resourceRates['vault-1']).toEqual({ power: 10, food: -5, water: 5 })
    })

    it('toasts when a workshop order completes', async () => {
      const store = useVaultStore()
      const { toasts } = useToast()
      toasts.value = []
      store.loadedVaults = { 'vault-1': mockVault }

      store.startGameTickSse('vault-1', 'test-token')
      ;(sseMock.event as Ref<{ event: string; data: unknown } | null>).value = {
        event: 'tick',
        data: {
          seconds_passed: 60,
          updates: { crafting: { completed: 2 } },
        },
      }
      await nextTick()

      expect(toasts.value.some((t) => t.message === '2 workshop orders are ready to collect')).toBe(
        true
      )
    })
  })

  describe('setActiveVault Action', () => {
    it('should set active vault if vault is loaded', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      store.setActiveVault('vault-1')

      expect(store.activeVaultId).toBe('vault-1')
    })

    it('should not set active vault if vault is not loaded', () => {
      const store = useVaultStore()
      store.activeVaultId = 'vault-2'

      store.setActiveVault('vault-1')

      expect(store.activeVaultId).toBe('vault-2')
    })
  })

  describe('closeVaultTab Action', () => {
    it('should close vault tab and update active vault', () => {
      const store = useVaultStore()
      const vault2 = { ...mockVault, id: 'vault-2' }
      store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vault2 }
      store.activeVaultId = 'vault-1'

      store.closeVaultTab('vault-1')

      expect(store.loadedVaults['vault-1']).toBeUndefined()
      expect(store.activeVaultId).toBe('vault-2')
    })

    it('should set activeVaultId to null if no vaults remain', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'

      store.closeVaultTab('vault-1')

      expect(store.activeVaultId).toBeNull()
    })

    it('should not change state if vault not loaded', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'

      store.closeVaultTab('vault-2')

      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-1')
    })
  })
})
