import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useMapStore } from '@/modules/map/stores/map'

// Mock the map service module
vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn(),
  getLocationDetail: vi.fn(),
}))

import * as mapService from '@/modules/map/services/mapService'

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
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('State Initialization', () => {
    it('should initialize with empty state', () => {
      const store = useMapStore()
      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchMap Action', () => {
    it('should fetch map data and populate state successfully', async () => {
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce(mockMapResponse)

      await store.fetchMap('vault-1', 'test-token')

      expect(mapService.getVaultMap).toHaveBeenCalledWith('test-token', 'vault-1')
      expect(store.locations).toEqual(mockMapResponse.locations)
      expect(store.vaultMarkers).toEqual(mockMapResponse.vault_markers)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should set loading state correctly during fetch', async () => {
      const store = useMapStore()
      let loadingDuringRequest = false

      vi.mocked(mapService.getVaultMap).mockImplementation(async () => {
        loadingDuringRequest = store.isLoading
        return mockMapResponse
      })

      await store.fetchMap('vault-1', 'test-token')

      expect(loadingDuringRequest).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('should handle error and set error message', async () => {
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockRejectedValueOnce(new Error('Network Error'))

      await store.fetchMap('vault-1', 'test-token')

      expect(store.error).toBe('Failed to load map')
      expect(store.isLoading).toBe(false)
      // State should remain empty on failure
      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should handle empty map response without throwing', async () => {
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce(mockEmptyResponse)

      await store.fetchMap('vault-1', 'test-token')

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    })

    it('should clear previous error on successful fetch', async () => {
      const store = useMapStore()
      store.error = 'Previous error'

      vi.mocked(mapService.getVaultMap).mockResolvedValueOnce(mockMapResponse)

      await store.fetchMap('vault-1', 'test-token')

      expect(store.error).toBeNull()
      expect(store.locations).toEqual(mockMapResponse.locations)
    })
  })

  describe('Polling', () => {
    it('startPolling should trigger periodic fetches', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValue(mockMapResponse)

      store.startPolling('vault-1', 'test-token')

      // First fetch shouldn't happen immediately (immediate: false)
      expect(mapService.getVaultMap).not.toHaveBeenCalled()

      // Advance 30 seconds - should trigger a poll
      await vi.advanceTimersByTimeAsync(30000)

      expect(mapService.getVaultMap).toHaveBeenCalledTimes(1)
      expect(store.locations).toEqual(mockMapResponse.locations)
    })

    it('stopPolling should halt periodic fetches', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValue(mockMapResponse)

      store.startPolling('vault-1', 'test-token')

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

      store.startPolling('vault-1', 'test-token')

      await vi.advanceTimersByTimeAsync(30000)
      expect(store.locations).toHaveLength(1)

      await vi.advanceTimersByTimeAsync(30000)
      expect(store.locations).toHaveLength(2)
    })

    it('stopPolling after one cycle should prevent further fetches', async () => {
      vi.useFakeTimers()
      const store = useMapStore()
      vi.mocked(mapService.getVaultMap).mockResolvedValue(mockMapResponse)

      store.startPolling('vault-1', 'test-token')

      // Let one poll cycle through
      await vi.advanceTimersByTimeAsync(30000)
      expect(mapService.getVaultMap).toHaveBeenCalledTimes(1)

      store.stopPolling()

      // Advance another cycle
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

      // Direct fetch
      await store.fetchMap('vault-1', 'test-token')
      expect(store.locations).toHaveLength(1)
      expect(store.vaultMarkers).toHaveLength(0)

      // Another direct fetch (uses second mock)
      await store.fetchMap('vault-1', 'test-token')
      expect(store.locations).toHaveLength(2)
      expect(store.vaultMarkers).toHaveLength(1)
    })
  })

  describe('Stale-response guard', () => {
    it('should drop poll response after stopPolling invalidates context', async () => {
      vi.useFakeTimers()
      const store = useMapStore()

      let resolveFn: (value: any) => void
      const controlled = new Promise((resolve) => {
        resolveFn = resolve
      })
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(controlled as any)

      store.startPolling('vault-1', 'test-token')
      await vi.advanceTimersByTimeAsync(30000)
      store.stopPolling()

      resolveFn!(mockMapResponse)
      await flushPromises()

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should drop poll response after switching vaults', async () => {
      vi.useFakeTimers()
      const store = useMapStore()

      let resolveFn: (value: any) => void
      const controlled = new Promise((resolve) => {
        resolveFn = resolve
      })
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(controlled as any)

      store.startPolling('vault-1', 'test-token')
      await vi.advanceTimersByTimeAsync(30000)
      store.startPolling('vault-2', 'test-token')

      resolveFn!(mockMapResponse)
      await flushPromises()

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should drop fetchMap response after stopPolling invalidates context', async () => {
      const store = useMapStore()

      let resolveFn: (value: any) => void
      const controlled = new Promise((resolve) => {
        resolveFn = resolve
      })
      vi.mocked(mapService.getVaultMap).mockReturnValueOnce(controlled as any)

      const fetchPromise = store.fetchMap('vault-1', 'test-token')
      store.stopPolling()

      resolveFn!(mockMapResponse)
      await fetchPromise

      expect(store.locations).toEqual([])
      expect(store.vaultMarkers).toEqual([])
    })

    it('should drop fetchMap response when a newer fetchMap is called', async () => {
      const store = useMapStore()

      let resolveOld: (value: any) => void
      const oldPromise = new Promise((resolve) => {
        resolveOld = resolve
      })

      const newData = {
        locations: [mockLocation2],
        vault_markers: [],
      }

      vi.mocked(mapService.getVaultMap)
        .mockReturnValueOnce(oldPromise as any)
        .mockResolvedValueOnce(newData)

      const oldFetch = store.fetchMap('vault-1', 'token-old')
      const newFetch = store.fetchMap('vault-2', 'token-new')

      resolveOld!(mockMapResponse)
      await oldFetch
      await newFetch

      expect(store.locations).toEqual([mockLocation2])
      expect(store.vaultMarkers).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })
})
