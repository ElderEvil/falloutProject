import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { createToastMock } from '../helpers/mocks'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock the map service module
vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn(),
  getLocationDetail: vi.fn(),
  getWorldSnapshot: vi.fn(),
}))

import * as mapService from '@/modules/map/services/mapService'

const mockToast = createToastMock()

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

/** A promise whose settlement the test drives. */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('Map Store', () => {
  const mockLocation = {
    id: 'loc-1',
    name: 'Rusty Depot',
    normalized_name: 'rusty depot',
    type: 'discovery' as const,
    coord_x: 25.5,
    coord_y: 30.2,
    description: 'An old storage facility',
    vault_id: 'vault-1',
    exploration_id: 'expl-1',
    created_at: '2025-01-01T00:00:00Z',
    dwellers: [],
  }

  const mockLocation2 = {
    id: 'loc-2',
    name: 'Glowing Cave',
    normalized_name: 'glowing cave',
    type: 'visited' as const,
    coord_x: 75.3,
    coord_y: 45.8,
    description: 'Eerie green glow emanates',
    vault_id: 'vault-1',
    exploration_id: null,
    created_at: '2025-01-01T00:00:00Z',
    dwellers: [],
  }

  const mockVaultMarker = {
    name: 'Vault 42',
    coord_x: 12.3,
    coord_y: 88.7,
    type: 'vault' as const,
    description: 'Vault 42 - 22 dwellers',
  }

  const mockMapResponse = {
    locations: [mockLocation, mockLocation2],
    vault_markers: [mockVaultMarker],
  }

  const mockEmptyResponse = {
    locations: [],
    vault_markers: [],
  }

  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())
    localStorage.removeItem(VIEWED_LOCATIONS_STORAGE_KEY)
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('State initialization', () => {
    it('should start empty with no viewed locations or unseen discoveries', () => {
      const store = useMapStore()
      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
      expect(store.viewedLocationKeys.size).toBe(0)
      expect(store.hasUnseenDiscoveries).toBe(false)
    })
  })

  describe('fetchMap Action', () => {
    it('should fetch map data, populate state and clear a previous error', async () => {
      const store = useMapStore()
      store.error = 'Previous error'
      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce(mockMapResponse)

      await store.fetchMap('vault-1')

      expect(mapService.getVaultMap).toHaveBeenCalledWith('vault-1')
      expect(store.locations).toEqual(mockMapResponse.locations)
      expect(store.vaultMarkers).toEqual(mockMapResponse.vault_markers)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('stores the place-group catalog and indexes it by key', async () => {
      const groups = [
        {
          key: 'gas_station',
          label: 'Gas Station',
          icon: 'mdi:gas-station',
          risk: 'low',
          description: 'A roadside fuel stop.',
        },
      ]
      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce({
        ...mockMapResponse,
        place_groups: groups,
      })

      const store = useMapStore()
      await store.fetchMap('vault-1')

      expect(store.placeGroups).toEqual(groups)
      expect(store.placeGroupByKey.get('gas_station')?.label).toBe('Gas Station')
    })

    it('should set loading state correctly during fetch', async () => {
      const store = useMapStore()
      let loadingDuringRequest = false

      vi.mocked(mapService.getVaultMap).mockImplementation(async () => {
        loadingDuringRequest = store.isLoading
        return mockMapResponse
      })

      await store.fetchMap('vault-1')

      expect(loadingDuringRequest).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('should handle error and set error message', async () => {
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockRejectedValueOnce(new Error('Network Error'))

      await store.fetchMap('vault-1')

      expect(store.error).toBe('Failed to load map')
      expect(store.isLoading).toBe(false)
      // State should remain empty on failure
      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should handle empty map response without throwing', async () => {
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce(mockEmptyResponse)

      await store.fetchMap('vault-1')

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    })
  })

  describe('Polling', () => {
    it('startPolling should trigger periodic fetches', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValue(mockMapResponse)

      store.startPolling('vault-1')

      // First fetch shouldn't happen immediately (immediate: false)
      expect(mapService.getVaultMap).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(30000)

      expect(mapService.getVaultMap).toHaveBeenCalledTimes(1)
      expect(store.locations).toEqual(mockMapResponse.locations)
    })

    it('stopPolling should halt periodic fetches', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValue(mockMapResponse)

      store.startPolling('vault-1')

      // Stop before first interval fires
      store.stopPolling()

      await vi.advanceTimersByTimeAsync(30000)

      expect(mapService.getVaultMap).not.toHaveBeenCalled()
    })

    it('poll should update state on each interval', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      const response1 = { locations: [mockLocation], vault_markers: [mockVaultMarker] }
      const response2 = {
        locations: [mockLocation, mockLocation2],
        vault_markers: [mockVaultMarker],
      }

      vi.mocked(mapService.getVaultMap)
        .mockResolvedValueOnce(response1)
        .mockResolvedValueOnce(response2)
      store.startPolling('vault-1')

      await vi.advanceTimersByTimeAsync(30000)
      expect(store.locations).toHaveLength(1)

      await vi.advanceTimersByTimeAsync(30000)
      expect(store.locations).toHaveLength(2)
    })

    it('stopPolling after one cycle should prevent further fetches', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValue(mockMapResponse)

      store.startPolling('vault-1')
      await vi.advanceTimersByTimeAsync(30000)
      expect(mapService.getVaultMap).toHaveBeenCalledTimes(1)

      store.stopPolling()
      await vi.advanceTimersByTimeAsync(30000)
      expect(mapService.getVaultMap).toHaveBeenCalledTimes(1) // Still 1
    })

    it('fetchMap should work independently from polling', async () => {
      const store = useMapStore()
      const fetchResponse = { locations: [mockLocation], vault_markers: [] }
      const pollResponse = {
        locations: [mockLocation, mockLocation2],
        vault_markers: [mockVaultMarker],
      }

      vi.mocked(mapService.getVaultMap)
        .mockResolvedValueOnce(fetchResponse)
        .mockResolvedValueOnce(pollResponse)

      await store.fetchMap('vault-1')
      expect(store.locations).toHaveLength(1)
      expect(store.vaultMarkers).toHaveLength(0)

      await store.fetchMap('vault-1')
      expect(store.locations).toHaveLength(2)
      expect(store.vaultMarkers).toHaveLength(1)
    })
  })

  describe('Viewed location state', () => {
    it('should report unseen discoveries until each is marked viewed', () => {
      const store = useMapStore()
      store.locations = [mockLocation, mockLocation2]

      expect(store.hasUnseenDiscoveries).toBe(true)

      store.markLocationViewed('vault-1', 'loc-1')

      expect(store.isLocationViewed('vault-1', 'loc-1')).toBe(true)
      expect(store.hasUnseenDiscoveries).toBe(false)
    })

    it('should ignore locked discoveries when deriving unseen state', () => {
      const store = useMapStore()
      store.locations = [{ ...mockLocation, is_unlocked: false }]

      expect(store.hasUnseenDiscoveries).toBe(false)
    })

    it('should keep viewed ids across map refreshes and scope them per vault', async () => {
      const store = useMapStore()
      store.markLocationViewed('vault-1', 'loc-1')

      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce(mockMapResponse)
      await store.fetchMap('vault-1')

      expect(store.isLocationViewed('vault-1', 'loc-1')).toBe(true)
      expect(store.isLocationViewed('vault-2', 'loc-1')).toBe(false)
    })

    it('should keep a discovery unseen in another vault with the same location id', () => {
      const store = useMapStore()
      store.markLocationViewed('vault-1', 'loc-1')

      store.locations = [{ ...mockLocation, vault_id: 'vault-1' }]
      expect(store.hasUnseenDiscoveries).toBe(false)

      store.locations = [{ ...mockLocation, vault_id: 'vault-2' }]
      expect(store.hasUnseenDiscoveries).toBe(true)
    })

    it('should persist viewed state across a page reload (new store instance)', async () => {
      const store = useMapStore()
      store.markLocationViewed('vault-1', 'loc-1')
      await nextTick()

      setActivePinia(createPinia())
      const reloaded = useMapStore()

      expect(reloaded.isLocationViewed('vault-1', 'loc-1')).toBe(true)
      reloaded.locations = [mockLocation]
      expect(reloaded.hasUnseenDiscoveries).toBe(false)
    })
  })

  describe('Stale-response guard', () => {
    it.each([
      ['stopPolling', (store: ReturnType<typeof useMapStore>) => store.stopPolling()],
      [
        'switching vaults',
        (store: ReturnType<typeof useMapStore>) => store.startPolling('vault-2'),
      ],
    ])('should drop the in-flight poll after %s invalidates context', async (_, invalidate) => {
      vi.useFakeTimers()
      const store = useMapStore()
      const controlled = deferred<unknown>()
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(controlled.promise as never)

      store.startPolling('vault-1')
      await vi.advanceTimersByTimeAsync(30000)
      invalidate(store)

      controlled.resolve(mockMapResponse)
      await flushPromises()

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should drop fetchMap response after stopPolling invalidates context', async () => {
      const store = useMapStore()
      const controlled = deferred<unknown>()
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(controlled.promise as never)

      const fetchPromise = store.fetchMap('vault-1')
      store.stopPolling()

      controlled.resolve(mockMapResponse)
      await fetchPromise

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should drop fetchMap response when a newer fetchMap is called', async () => {
      const store = useMapStore()
      const old = deferred<unknown>()
      const newData = { locations: [mockLocation2], vault_markers: [] }

      vi.mocked(mapService.getVaultMap)
        .mockReturnValueOnce(old.promise as never)
        .mockResolvedValueOnce(newData)

      const oldFetch = store.fetchMap('vault-1')
      const newFetch = store.fetchMap('vault-2')

      old.resolve(mockMapResponse)
      await oldFetch
      await newFetch

      expect(store.locations).toEqual([mockLocation2])
      expect(store.vaultMarkers).toEqual([])
      expect(store.isLoading).toBe(false)
    })

    it('drops a delayed fetch response after the session changes', async () => {
      const store = useMapStore()
      const auth = useAuthStore()
      const pending = deferred<unknown>()
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(pending.promise as never)

      const fetch = store.fetchMap('vault-1')
      auth.sessionGeneration += 1
      pending.resolve(mockMapResponse)
      await fetch

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(mockToast.success).not.toHaveBeenCalled()
      expect(mockToast.error).not.toHaveBeenCalled()
    })

    it('drops a delayed fetch failure after the session changes', async () => {
      const store = useMapStore()
      const auth = useAuthStore()
      const pending = deferred<unknown>()
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(pending.promise as never)

      const fetch = store.fetchMap('vault-1')
      auth.sessionGeneration += 1
      pending.reject(new Error('stale session failure'))
      await fetch

      expect(store.error).toBeNull()
      expect(store.locations).toEqual([])
      expect(mockToast.error).not.toHaveBeenCalled()
    })

    it('drops a delayed poll response after the session changes', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      const auth = useAuthStore()
      const pending = deferred<unknown>()
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(pending.promise as never)

      store.startPolling('vault-1')
      await vi.advanceTimersByTimeAsync(30000)
      auth.sessionGeneration += 1
      pending.resolve(mockMapResponse)
      await flushPromises()

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
      expect(mockToast.success).not.toHaveBeenCalled()
    })
  })
})

describe('Map Store unlock toasts', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const loc = (id: string, name: string, unlocked: boolean) => ({ id, name, is_unlocked: unlocked })

  async function load(store: ReturnType<typeof useMapStore>, vaultId: string, locs: unknown[]) {
    vi.mocked(mapService.getVaultMap).mockResolvedValueOnce({ locations: locs, vault_markers: [] })
    await store.fetchMap(vaultId)
  }

  async function refresh(store: ReturnType<typeof useMapStore>, vaultId: string, locs: unknown[]) {
    vi.mocked(mapService.getVaultMap).mockResolvedValueOnce({ locations: locs, vault_markers: [] })
    await store.refreshMap(vaultId)
  }

  it('stays silent on baseline initial load', async () => {
    const store = useMapStore()
    await load(store, 'vault-1', [loc('a', 'Alpha', true)])
    expect(mockToast.success).not.toHaveBeenCalled()
  })

  it('names a single newly unlocked location on refresh', async () => {
    const store = useMapStore()
    const a = loc('a', 'Alpha', true)
    await load(store, 'vault-1', [a])
    await refresh(store, 'vault-1', [a, loc('b', 'Beta', true)])
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith('New discovery: Beta')
  })

  it('counts multiple newly unlocked locations in one toast', async () => {
    const store = useMapStore()
    const a = loc('a', 'Alpha', true)
    await load(store, 'vault-1', [a])
    await refresh(store, 'vault-1', [a, loc('b', 'Beta', true), loc('c', 'Gamma', true)])
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith('2 new discoveries on the map')
  })

  it('does not re-toast on unchanged refresh', async () => {
    const store = useMapStore()
    const locs = [loc('a', 'Alpha', true), loc('b', 'Beta', true)]
    await load(store, 'vault-1', locs)
    await refresh(store, 'vault-1', locs)
    expect(mockToast.success).not.toHaveBeenCalled()
  })

  it('toasts locked-to-unlocked transitions', async () => {
    const store = useMapStore()
    await load(store, 'vault-1', [loc('c', 'Gamma', false)])
    await refresh(store, 'vault-1', [loc('c', 'Gamma', true)])
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith('New discovery: Gamma')
  })

  it('isolates snapshots per vault', async () => {
    const store = useMapStore()
    await load(store, 'vault-1', [loc('a', 'Alpha', true)])
    await load(store, 'vault-2', [loc('x', 'Xi', true), loc('y', 'Psi', true)])
    expect(mockToast.success).not.toHaveBeenCalled()
    await refresh(store, 'vault-2', [
      loc('x', 'Xi', true),
      loc('y', 'Psi', true),
      loc('z', 'Zed', true),
    ])
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith('New discovery: Zed')
    await refresh(store, 'vault-1', [loc('a', 'Alpha', true)])
    expect(mockToast.success).toHaveBeenCalledTimes(1)
  })

  describe('fetchWorldSnapshot Action', () => {
    const snapshot = (terrain: string[], width = 80, height = 80) => ({
      world_id: 'wasteland-atlas',
      generator_version: 1,
      recipe_fingerprint: 'fp',
      snapshot_checksum: 'cs',
      width,
      height,
      terrain,
      slots: [],
    })

    it('stores a well-formed snapshot', async () => {
      vi.mocked(mapService.getWorldSnapshot).mockResolvedValueOnce(
        snapshot(new Array(80 * 80).fill('wasteland')) as never
      )
      const store = useMapStore()

      await store.fetchWorldSnapshot()

      expect(mapService.getWorldSnapshot).toHaveBeenCalled()
      expect(store.worldSnapshot?.width).toBe(80)
      expect(store.snapshotError).toBeNull()
    })

    it.each([
      ['whose terrain does not match its grid', snapshot(new Array(10).fill('wasteland'))],
      ['with a non-square grid', snapshot(new Array(80 * 60).fill('wasteland'), 80, 60)],
    ])('rejects a snapshot %s', async (_, payload) => {
      vi.mocked(mapService.getWorldSnapshot).mockResolvedValueOnce(payload as never)
      const store = useMapStore()

      await store.fetchWorldSnapshot()

      expect(store.worldSnapshot).toBeNull()
      expect(store.snapshotError).not.toBeNull()
    })

    it('clears the snapshot on fetch failure instead of keeping stale terrain', async () => {
      vi.mocked(mapService.getWorldSnapshot).mockRejectedValueOnce(new Error('offline'))
      const store = useMapStore()

      await store.fetchWorldSnapshot()

      expect(store.worldSnapshot).toBeNull()
      expect(store.snapshotError).not.toBeNull()
      expect(mockToast.error).toHaveBeenCalledTimes(1)
      expect(mockToast.error).toHaveBeenCalledWith(
        'World terrain unavailable — showing markers only: offline'
      )
    })
  })
})
