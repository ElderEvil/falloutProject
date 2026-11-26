import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick, ref, type Ref } from 'vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import type { DwellerTickSnapshot } from '@/modules/dwellers/models/dweller'
import { useToast } from '@/core/composables/useToast'
import axios from '@/core/plugins/axios'
import { useRouter } from 'vue-router'

import { setAuthTokenProvider } from '@/core/utils/authToken'

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

function tickSnapshot(overrides: Partial<DwellerTickSnapshot> = {}): DwellerTickSnapshot {
  return {
    id: 'd1',
    health: 90,
    max_health: 100,
    radiation: 5,
    happiness: 80,
    level: 4,
    experience: 12,
    status: 'idle',
    room_id: null,
    is_dead: false,
    effective_max_health: 95,
    ...overrides,
  }
}

function deferred<T = unknown>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const baseVault = () => ({
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
})

/** A vault row; tests patch the vault in place, so it is rebuilt per test. */
const mockVault = baseVault()

const vault = (overrides: Record<string, unknown> = {}) =>
  ({ ...mockVault, ...overrides }) as typeof mockVault

const eventRef = () => sseMock.event as Ref<{ event: string; data: unknown } | null>

/** Publish one game-tick frame onto the mocked stream. */
function emitTick(data: unknown) {
  eventRef().value = { event: 'tick', data }
}

const toastShown = (message: string) =>
  useToast().toasts.value.some((toast) => toast.message === message)

describe('Vault Store', () => {
  let mockRouter: { push: ReturnType<typeof vi.fn> }

  beforeEach(() => {
    setActivePinia(createPinia())
    setAuthTokenProvider(() => 'test-token')
    localStorage.clear()
    vi.clearAllMocks()
    Object.assign(mockVault, baseVault())
    sseMock.event = ref(null) as Ref<unknown>

    mockRouter = { push: vi.fn().mockResolvedValue(undefined) }
    vi.mocked(useRouter).mockReturnValue(mockRouter as never)
  })

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
    it('selectedVault should return the selected vault or null', () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      expect(store.selectedVault).toBeNull()
      store.selectedVaultId = 'vault-1'
      expect(store.selectedVault).toEqual(mockVault)
    })

    it('activeVault should return the active vault or null', () => {
      const store = useVaultStore()
      expect(store.activeVault).toBeNull()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'
      store.selectedVaultId = 'vault-1'
      expect(store.activeVault).toEqual(mockVault)
    })

    it('loadedVaultIds should return array of loaded vault IDs', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vault({ id: 'vault-2' }) }
      expect(store.loadedVaultIds).toEqual(['vault-1', 'vault-2'])
    })

    it('currentVaultId falls back to the persisted selection and prefers the active vault', () => {
      const store = useVaultStore()
      store.selectedVaultId = 'vault-1'

      expect(store.activeVaultId).toBeNull()
      expect(store.currentVaultId).toBe('vault-1')
      store.activeVaultId = 'vault-2'
      expect(store.currentVaultId).toBe('vault-2')
    })
  })

  describe('fetchVaults Action', () => {
    it('should fetch vaults successfully', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [mockVault, vault({ id: 'vault-2' })] })
      await store.fetchVaults()
      expect(store.vaults).toEqual([mockVault, vault({ id: 'vault-2' })])
      expect(axios.get).toHaveBeenCalledWith('/api/v1/vaults/my')

      // A failed refresh must not wipe the roster the player is looking at.
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))
      await store.fetchVaults()
      expect(store.vaults).toEqual([mockVault, vault({ id: 'vault-2' })])
    })
  })

  describe('createVault Action', () => {
    it('blocks creation when the refreshed vault list is already at the limit', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault, vault({ id: 'vault-2' })]
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [mockVault, vault({ id: 'vault-2' }), vault({ id: 'vault-3' })],
      })

      expect(await store.createVault(104, false)).toBe(null)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('does not create a vault when the current list cannot be checked', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))
      expect(await store.createVault(104, false)).toBe(null)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('should create vault and refresh list', async () => {
      const store = useVaultStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-1' } })
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({
          data: [mockVault],
        })

      await store.createVault(101, false)
      expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', {
        number: 101,
        boosted: false,
        vault_mode: 'standard',
      })
      expect(store.vaults).toEqual([mockVault])
    })

    it.each([
      [101, 'survival', undefined, { number: 101, boosted: false, vault_mode: 'survival' }],
      [
        1,
        'standard',
        'vault_1_test',
        { number: 1, boosted: false, vault_mode: 'standard', scenario: 'vault_1_test' },
      ],
    ] as [number, string, string | undefined, Record<string, unknown>][])(
      'posts the chosen mode and scenario for vault %s',
      async (number, mode, scenario, expected) => {
        const store = useVaultStore()
        vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-1' } })
        vi.mocked(axios.get).mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: [] })

        expect(await store.createVault(number, false, mode, scenario)).toBe('vault-1')
        expect(axios.post).toHaveBeenCalledWith('/api/v1/vaults/initiate', expected)
      }
    )

    it('fetches opt-in scenario options', async () => {
      const store = useVaultStore()
      const scenario = {
        number: 1,
        key: 'vault_1_test',
        title: 'Vault 1 — Wasteland Test',
        description: 'Test scenario',
        requires_boosted: false,
        default_boosted: true,
        default_on: true,
        expedition: true,
      }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [scenario] })

      expect(await store.fetchScenarioOptions()).toBe(true)
      expect(store.scenarioOptions).toEqual([scenario])
      expect(axios.get).toHaveBeenCalledWith('/api/v1/vaults/scenarios')
    })

    it('reports success when the vault is created even if the refresh fails', async () => {
      const store = useVaultStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'vault-1' } })
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: [] })
        .mockRejectedValueOnce(new Error('Fetch failed'))

      expect(await store.createVault(101, false)).toBe('vault-1')
      expect(axios.post).toHaveBeenCalled()
    })

    it('should handle creation error gracefully', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Create failed'))
      await store.createVault(101, false)
      expect(store.vaults).toEqual([])
    })
  })

  describe('deleteVault Action', () => {
    it('should delete a vault, clear the selection, and promote the next loaded vault', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault, vault({ id: 'vault-2' })]
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-1'
      store.selectedVaultId = 'vault-1'
      vi.mocked(axios.delete).mockResolvedValueOnce({})

      await store.deleteVault('vault-1')
      expect(store.vaults.map((entry) => entry.id)).toEqual(['vault-2'])
      expect(store.loadedVaults['vault-1']).toBeUndefined()
      expect(store.activeVaultId).toBeNull()
      expect(store.selectedVaultId).toBeNull()
      expect(store.currentVaultId).toBeNull()

      const vault2 = vault({ id: 'vault-2' })
      const second = useVaultStore()
      second.vaults = [mockVault, vault2]
      second.loadedVaults = { 'vault-2': vault2 }
      second.activeVaultId = 'vault-1'
      second.selectedVaultId = 'vault-1'
      vi.mocked(axios.delete).mockResolvedValueOnce({})

      await second.deleteVault('vault-1')
      expect(second.activeVaultId).toBe('vault-2')
      expect(second.selectedVaultId).toBe('vault-2')
    })

    it('leaves the vault list untouched when the delete fails', async () => {
      const store = useVaultStore()
      store.vaults = [mockVault]
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Delete failed'))
      await store.deleteVault('vault-1')
      expect(store.vaults).toHaveLength(1)
    })
  })

  describe('ensureVaultLoaded Action', () => {
    it('should load vault and set active vault', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      await store.ensureVaultLoaded('vault-1')
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-1')
      expect(store.selectedVaultId).toBe('vault-1')
      expect(store.isLoading).toBe(false)
    })

    it('flags loading while the vault header is in flight', async () => {
      const store = useVaultStore()
      let loadingDuringFetch = false

      vi.mocked(axios.get).mockImplementation(async () => {
        loadingDuringFetch = store.isLoading
        return { data: mockVault }
      })
      await store.ensureVaultLoaded('vault-1')
      expect(loadingDuringFetch).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('should handle load error and rethrow', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Load failed'))
      await expect(store.ensureVaultLoaded('vault-1')).rejects.toThrow('Load failed')
      expect(store.isLoading).toBe(false)
    })

    it('deduplicates concurrent loads for the same vault', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      await Promise.all([store.ensureVaultLoaded('vault-1'), store.ensureVaultLoaded('vault-1')])
      expect(axios.get).toHaveBeenCalledTimes(1)
      expect(sseMock.start).toHaveBeenCalledTimes(1)
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
    })

    it('returns without a GET for an already-loaded vault but re-asserts the stream', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      await store.ensureVaultLoaded('vault-1')
      await store.ensureVaultLoaded('vault-1')
      expect(axios.get).not.toHaveBeenCalled()
      expect(store.activeVaultId).toBe('vault-1')
      expect(store.selectedVaultId).toBe('vault-1')
      // The stream is already for vault-1, so re-asserting it starts no second SSE.
      expect(sseMock.start).toHaveBeenCalledTimes(1)
    })

    it('does not adopt a stale response for a superseded vault', async () => {
      const store = useVaultStore()
      const loadA = deferred<unknown>()
      vi.mocked(axios.get).mockReturnValueOnce(loadA.promise as never)

      const loadingA = store.ensureVaultLoaded('vault-1')
      vi.mocked(axios.get).mockResolvedValueOnce({ data: vault({ id: 'vault-2' }) })
      await store.ensureVaultLoaded('vault-2')
      expect(store.activeVaultId).toBe('vault-2')
      loadA.resolve({ data: mockVault })
      await loadingA
      // A is still cached, but B remains active and its stream is untouched.
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
      expect(store.activeVaultId).toBe('vault-2')
      expect(store.selectedVaultId).toBe('vault-2')
      expect(sseMock.start).toHaveBeenCalledTimes(1)
    })

    it('starts the new vault stream when the previous vault was paused', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vault({ id: 'vault-2' }) }
      await store.ensureVaultLoaded('vault-1')
      store.gameState = { is_paused: true }
      store.stopResourcePolling()

      await store.ensureVaultLoaded('vault-2')
      expect(store.activeVaultId).toBe('vault-2')
      expect(store.gameState).toBeNull()
      expect(sseMock.start).toHaveBeenCalledTimes(2)
    })

    it('is a no-op without an id', async () => {
      const store = useVaultStore()
      await store.ensureVaultLoaded('')
      expect(axios.get).not.toHaveBeenCalled()
      expect(store.activeVaultId).toBeNull()
    })
  })

  describe('revalidateVault Action', () => {
    it('fetches fresh data for a cached vault on each route entry', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: vault({ bottle_caps: 1200 }) })
        .mockResolvedValueOnce({ data: vault({ bottle_caps: 1400 }) })

      await store.revalidateVault('vault-1')
      await store.revalidateVault('vault-1')
      expect(axios.get).toHaveBeenCalledTimes(2)
      expect(store.loadedVaults['vault-1'].bottle_caps).toBe(1400)
    })

    it('shares an in-flight header load rather than requesting the same vault twice', async () => {
      const store = useVaultStore()
      const load = deferred<unknown>()
      vi.mocked(axios.get).mockReturnValueOnce(load.promise as never)

      const headerLoad = store.ensureVaultLoaded('vault-1')
      const routeLoad = store.revalidateVault('vault-1')
      load.resolve({ data: mockVault })
      await Promise.all([headerLoad, routeLoad])
      expect(axios.get).toHaveBeenCalledTimes(1)
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
    })

    it('does not toast when a superseded vault load fails, but still rejects', async () => {
      const store = useVaultStore()
      const { toasts } = useToast()
      toasts.value = []
      const oldLoad = deferred<unknown>()
      vi.mocked(axios.get).mockReturnValueOnce(oldLoad.promise as never)

      const pending = store.ensureVaultLoaded('vault-1')
      vi.mocked(axios.get).mockResolvedValueOnce({ data: vault({ id: 'vault-2' }) })
      await store.ensureVaultLoaded('vault-2')
      oldLoad.reject(new Error('Old vault failed'))
      await expect(pending).rejects.toThrow('Old vault failed')
      expect(toasts.value.some((toast) => toast.message.includes('Old vault failed'))).toBe(false)
    })
  })

  describe('refreshVault Action', () => {
    it('persists the vault as the selected vault so navigation survives a reload', async () => {
      const store = useVaultStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVault })

      await store.refreshVault('vault-1')
      expect(store.activeVaultId).toBe('vault-1')
      expect(store.selectedVaultId).toBe('vault-1')
      // A fresh store instance (as after a page reload) still knows the selection.
      setActivePinia(createPinia())
      expect(useVaultStore().selectedVaultId).toBe('vault-1')
    })

    it('only caches a late refresh after another vault becomes active', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      await store.ensureVaultLoaded('vault-1')
      const refresh = deferred<unknown>()
      vi.mocked(axios.get).mockReturnValueOnce(refresh.promise as never)
      const pending = store.refreshVault('vault-1')

      store.loadedVaults['vault-2'] = vault({ id: 'vault-2' })
      await store.ensureVaultLoaded('vault-2')
      refresh.resolve({ data: vault({ bottle_caps: 1200 }) })
      await pending
      expect(store.loadedVaults['vault-1'].bottle_caps).toBe(1200)
      expect(store.activeVaultId).toBe('vault-2')
      expect(store.selectedVaultId).toBe('vault-2')
      expect(sseMock.start).toHaveBeenCalledTimes(2)
    })
  })

  describe('resource polling', () => {
    it('keeps an explicit stop effective when the tab returns', async () => {
      vi.useFakeTimers()
      const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
      localStorage.setItem('token', 'test-token')
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.setActiveVault('vault-1')
      vi.mocked(axios.get).mockResolvedValue({ data: mockVault })
      try {
        store.startResourcePolling()
        visibility.mockReturnValue('hidden')
        document.dispatchEvent(new Event('visibilitychange'))
        await nextTick()
        store.stopResourcePolling()
        visibility.mockReturnValue('visible')
        document.dispatchEvent(new Event('visibilitychange'))
        await vi.advanceTimersByTimeAsync(30_000)
        expect(axios.get).not.toHaveBeenCalled()
      } finally {
        store.stopResourcePolling()
        visibility.mockRestore()
        vi.useRealTimers()
      }
    })

    it('does not write an old vault response into the newly selected vault', async () => {
      vi.useFakeTimers()
      try {
        localStorage.setItem('token', 'test-token')
        const store = useVaultStore()
        const vaultB = vault({ id: 'vault-2', power: 70 })
        store.loadedVaults = { 'vault-1': mockVault, 'vault-2': vaultB }
        store.setActiveVault('vault-1')
        const poll = deferred<unknown>()
        vi.mocked(axios.get).mockReturnValueOnce(poll.promise as never)

        store.startResourcePolling()
        // Authentication is checked before entering each scheduled refresh.
        await vi.advanceTimersByTimeAsync(10000)
        store.setActiveVault('vault-2')
        poll.resolve({ data: vault({ power: 10 }) })
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
      useToast().toasts.value = []

      store.startGameTickSse('vault-1', 'test-token')
      store.startGameTickSse('vault-2', 'test-token')
      emitTick({ results: { updates: { crafting: { completed: 1 } } } })
      await nextTick()
      expect(toastShown('A workshop order is ready to collect')).toBe(true)
      expect(
        useToast().toasts.value.filter(
          (toast) => toast.message === 'A workshop order is ready to collect'
        )
      ).toHaveLength(1)
    })

    it('merges tick resources and exposes the net rate per minute', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({
        results: {
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
      })
      await nextTick()
      expect(store.loadedVaults['vault-1']).toMatchObject({ power: 60, food: 75, water: 86 })
      expect(store.resourceRates['vault-1']).toEqual({ power: 10, food: -5, water: 5 })
    })

    it('ignores a flat tick payload without the results envelope', async () => {
      const store = useVaultStore()
      useToast().toasts.value = []
      store.loadedVaults = { 'vault-1': mockVault }

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({ updates: { crafting: { completed: 1 } } })
      await nextTick()
      expect(toastShown('A workshop order is ready to collect')).toBe(false)
      expect(store.loadedVaults['vault-1']).toEqual(mockVault)
    })

    it('applies the nested results envelope the backend publishes', async () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({
        event_id: 'tick-1',
        type: 'game_tick',
        vault_id: 'vault-1',
        results: {
          vault_id: 'vault-1',
          seconds_passed: 60,
          updates: {
            resources: {
              power: 61,
              food: 76,
              water: 87,
              events: {
                production: { power: 15, food: 2, water: 9 },
                consumption: { power: 5, food: 7, water: 4 },
              },
            },
            crafting: { completed: 1 },
          },
        },
      })
      await nextTick()
      expect(store.loadedVaults['vault-1']).toMatchObject({ power: 61, food: 76, water: 87 })
      expect(store.resourceRates['vault-1']).toEqual({ power: 10, food: -5, water: 5 })
    })

    it('patches the live dweller roster from the nested dweller snapshot', async () => {
      const store = useVaultStore()
      const filterStore = useDwellerFilterStore()
      store.activeVaultId = 'vault-1'
      filterStore.allDwellers = [{ id: 'd1', first_name: 'John', health: 10 }] as never
      filterStore.allDwellersLoadedVaultId = 'vault-1'

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({
        event_id: 'tick-1',
        type: 'game_tick',
        vault_id: 'vault-1',
        results: {
          vault_id: 'vault-1',
          seconds_passed: 60,
          updates: { dweller_snapshot: [tickSnapshot({ health: 90 })] },
        },
      })
      await vi.waitFor(() => {
        expect(filterStore.allDwellers[0]).toMatchObject({ health: 90, first_name: 'John' })
      })
    })

    it('ignores a null payload and a non-array dweller snapshot', async () => {
      const store = useVaultStore()
      const filterStore = useDwellerFilterStore()
      store.activeVaultId = 'vault-1'
      filterStore.allDwellers = [{ id: 'd1', health: 10 }] as never
      filterStore.allDwellersLoadedVaultId = 'vault-1'

      store.startGameTickSse('vault-1', 'test-token')
      emitTick(null)
      await nextTick()
      emitTick({ results: { updates: { dweller_snapshot: 'not-an-array' } } })
      await nextTick()
      expect(filterStore.allDwellers).toHaveLength(1)
      expect(filterStore.allDwellers[0]).toMatchObject({ health: 10 })
    })

    it('leaves the roster untouched when a tick carries no dweller snapshot', async () => {
      const store = useVaultStore()
      const filterStore = useDwellerFilterStore()
      store.activeVaultId = 'vault-1'
      filterStore.allDwellers = [{ id: 'd1', first_name: 'John', health: 10 }] as never
      filterStore.allDwellersLoadedVaultId = 'vault-1'

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({ results: { updates: { resources: { power: 60, food: 75, water: 86 } } } })
      await nextTick()
      expect(filterStore.allDwellers).toHaveLength(1)
      expect(filterStore.allDwellers[0]).toMatchObject({ health: 10 })
    })

    it('coalesces frames so the last dweller snapshot wins', async () => {
      const store = useVaultStore()
      const filterStore = useDwellerFilterStore()
      store.activeVaultId = 'vault-1'
      filterStore.allDwellers = [{ id: 'd1', health: 10 }] as never
      filterStore.allDwellersLoadedVaultId = 'vault-1'

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({ results: { updates: { dweller_snapshot: [tickSnapshot({ health: 50 })] } } })
      emitTick({ results: { updates: { dweller_snapshot: [tickSnapshot({ health: 70 })] } } })
      await vi.waitFor(() => {
        expect(filterStore.allDwellers[0]).toMatchObject({ health: 70 })
      })
    })

    it('toasts when a workshop order completes', async () => {
      const store = useVaultStore()
      useToast().toasts.value = []
      store.loadedVaults = { 'vault-1': mockVault }

      store.startGameTickSse('vault-1', 'test-token')
      emitTick({ results: { seconds_passed: 60, updates: { crafting: { completed: 2 } } } })
      await nextTick()
      expect(toastShown('2 workshop orders are ready to collect')).toBe(true)
    })
  })

  describe('setActiveVault Action', () => {
    it('should only set an active vault that is loaded', () => {
      const store = useVaultStore()
      store.loadedVaults = { 'vault-1': mockVault }
      store.activeVaultId = 'vault-2'

      store.setActiveVault('vault-1')
      expect(store.activeVaultId).toBe('vault-1')
      store.setActiveVault('vault-9')
      expect(store.activeVaultId).toBe('vault-1')
    })
  })

  describe('closeVaultTab Action', () => {
    it('should close vault tab and update active vault', () => {
      const store = useVaultStore()
      const vault2 = vault({ id: 'vault-2' })
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
