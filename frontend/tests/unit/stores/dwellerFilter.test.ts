import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'
import * as http from '@/core/plugins/httpClient'

vi.mock('@/core/plugins/httpClient')
vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))
vi.mock('@vueuse/core', () => ({
  useLocalStorage: <T>(key: string, defaultValue: T) => ref<T>(defaultValue),
  createSharedComposable: <T>(fn: () => T) => fn,
}))

import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'

describe('DwellerFilter Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  describe('State', () => {
    it('should initialize with empty state and defaults', () => {
      const store = useDwellerFilterStore()

      expect(store.dwellers).toEqual([])
      expect(store.detailedDwellers).toEqual({})
      expect(store.isLoading).toBe(false)
      expect(store.filterStatus).toBe('all')
      expect(store.sortBy).toBe('name')
      expect(store.sortDirection).toBe('asc')
      expect(store.viewMode).toBe('list')
    })
  })

  describe('fetchDwellersByVault', () => {
    it('should fetch dwellers and update state', async () => {
      const mockDwellers = [
        { id: 'd1', first_name: 'John', last_name: 'Doe', status: 'idle', level: 5, happiness: 75 },
        { id: 'd2', first_name: 'Jane', last_name: 'Smith', status: 'working', level: 3, happiness: 80 },
      ]
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockDwellers)

      const store = useDwellerFilterStore()
      await store.fetchDwellersByVault('vault-1', 'test-token')

      expect(http.apiGet).toHaveBeenCalledWith(
        '/api/v1/dwellers/vault/vault-1/',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.dwellers).toEqual(mockDwellers)
      expect(store.isLoading).toBe(false)
    })

    it('should pass filter parameters as query string', async () => {
      vi.mocked(http.apiGet).mockResolvedValueOnce([])

      const store = useDwellerFilterStore()
      await store.fetchDwellersByVault('vault-1', 'test-token', {
        status: 'working',
        sortBy: 'level',
        order: 'desc',
        limit: 20,
      })

      const url = vi.mocked(http.apiGet).mock.calls[0][0] as string
      expect(url).toContain('status=working')
      expect(url).toContain('sort_by=level')
      expect(url).toContain('order=desc')
      expect(url).toContain('limit=20')
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(http.apiGet).mockRejectedValueOnce(new Error('Network error'))

      const store = useDwellerFilterStore()
      await store.fetchDwellersByVault('vault-1', 'test-token')

      expect(store.dwellers).toEqual([])
      expect(store.isLoading).toBe(false)
    })

    it('should not pass default filter values', async () => {
      vi.mocked(http.apiGet).mockResolvedValueOnce([])

      const store = useDwellerFilterStore()
      await store.fetchDwellersByVault('vault-1', 'test-token', {
        status: 'all',
        ageGroup: 'all',
      })

      const url = vi.mocked(http.apiGet).mock.calls[0][0] as string
      expect(url).not.toContain('status=')
      expect(url).not.toContain('age_group=')
    })
  })

  describe('fetchDwellerDetails', () => {
    it('should fetch and cache dweller details', async () => {
      const mockDweller = { id: 'd1', first_name: 'John', last_name: 'Doe', strength: 5, perception: 5 }
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockDweller)

      const store = useDwellerFilterStore()
      const result = await store.fetchDwellerDetails('550e8400-e29b-41d4-a716-446655440000', 'test-token')

      expect(result).toEqual(mockDweller)
      expect(store.detailedDwellers['550e8400-e29b-41d4-a716-446655440000']).toEqual(mockDweller)
    })

    it('should use cached result when available', async () => {
      const mockDweller = { id: 'd1', first_name: 'John', last_name: 'Doe' }
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockDweller)

      const store = useDwellerFilterStore()
      await store.fetchDwellerDetails('550e8400-e29b-41d4-a716-446655440000', 'test-token')
      vi.mocked(http.apiGet).mockClear()

      const result = await store.fetchDwellerDetails('550e8400-e29b-41d4-a716-446655440000', 'test-token')

      expect(http.apiGet).not.toHaveBeenCalled()
      expect(result).toEqual(mockDweller)
    })

    it('should bypass cache when forceRefresh is true', async () => {
      const mockDweller = { id: 'd1', first_name: 'John', last_name: 'Doe' }
      vi.mocked(http.apiGet).mockResolvedValue(mockDweller)

      const store = useDwellerFilterStore()
      await store.fetchDwellerDetails('550e8400-e29b-41d4-a716-446655440000', 'test-token')
      vi.mocked(http.apiGet).mockClear()

      await store.fetchDwellerDetails('550e8400-e29b-41d4-a716-446655440000', 'test-token', true)

      expect(http.apiGet).toHaveBeenCalledTimes(1)
    })

    it('should return null for invalid UUID', async () => {
      const store = useDwellerFilterStore()
      const result = await store.fetchDwellerDetails('not-a-uuid', 'test-token')

      expect(result).toBeNull()
      expect(http.apiGet).not.toHaveBeenCalled()
    })
  })

  describe('filteredAndSortedDwellers', () => {
    it('should return all dwellers when filterStatus is all', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', first_name: 'A', last_name: 'Z', status: 'idle', level: 1, happiness: 50 } as any,
        { id: 'd2', first_name: 'B', last_name: 'Y', status: 'working', level: 2, happiness: 60 } as any,
      ]

      expect(store.filteredAndSortedDwellers).toHaveLength(2)
    })

    it('should filter by status', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', first_name: 'A', last_name: 'Z', status: 'idle', level: 1, happiness: 50 } as any,
        { id: 'd2', first_name: 'B', last_name: 'Y', status: 'working', level: 2, happiness: 60 } as any,
      ]
      store.filterStatus = 'working'

      const result = store.filteredAndSortedDwellers
      expect(result).toHaveLength(1)
      expect(result[0].id).toBe('d2')
    })

    it('should sort by name ascending', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', first_name: 'B', last_name: 'A', status: 'idle', level: 1, happiness: 50 } as any,
        { id: 'd2', first_name: 'A', last_name: 'A', status: 'idle', level: 2, happiness: 60 } as any,
      ]
      store.sortBy = 'name'
      store.sortDirection = 'asc'

      const result = store.filteredAndSortedDwellers
      expect(result[0].id).toBe('d2')
      expect(result[1].id).toBe('d1')
    })

    it('should sort by name descending', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', first_name: 'A', last_name: 'A', status: 'idle', level: 1, happiness: 50 } as any,
        { id: 'd2', first_name: 'B', last_name: 'A', status: 'idle', level: 2, happiness: 60 } as any,
      ]
      store.sortBy = 'name'
      store.sortDirection = 'desc'

      const result = store.filteredAndSortedDwellers
      expect(result[0].id).toBe('d2')
      expect(result[1].id).toBe('d1')
    })

    it('should sort by level numerically', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', first_name: 'A', last_name: 'A', status: 'idle', level: 10, happiness: 50 } as any,
        { id: 'd2', first_name: 'B', last_name: 'A', status: 'idle', level: 1, happiness: 60 } as any,
      ]
      store.sortBy = 'level'
      store.sortDirection = 'asc'

      const result = store.filteredAndSortedDwellers
      expect(result[0].id).toBe('d2')
      expect(result[1].id).toBe('d1')
    })

    it('should sort by happiness', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', first_name: 'A', last_name: 'A', status: 'idle', level: 1, happiness: 50 } as any,
        { id: 'd2', first_name: 'B', last_name: 'A', status: 'idle', level: 1, happiness: 80 } as any,
      ]
      store.sortBy = 'happiness'
      store.sortDirection = 'asc'

      const result = store.filteredAndSortedDwellers
      expect(result[0].id).toBe('d1')
      expect(result[1].id).toBe('d2')
    })
  })

  describe('getDwellerStatus', () => {
    it('should return status for existing dweller', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [{ id: 'd1', status: 'working' } as any]

      expect(store.getDwellerStatus('d1')).toBe('working')
    })

    it('should return null for missing dweller', () => {
      const store = useDwellerFilterStore()
      expect(store.getDwellerStatus('nonexistent')).toBeNull()
    })
  })

  describe('getDwellersByStatus', () => {
    it('should filter dwellers by status', () => {
      const store = useDwellerFilterStore()
      store.dwellers = [
        { id: 'd1', status: 'idle' } as any,
        { id: 'd2', status: 'working' } as any,
        { id: 'd3', status: 'idle' } as any,
      ]

      const idleDwellers = store.getDwellersByStatus('idle')
      expect(idleDwellers).toHaveLength(2)
    })
  })

  describe('Setters', () => {
    it('setFilterStatus updates filterStatus', () => {
      const store = useDwellerFilterStore()
      store.setFilterStatus('working')
      expect(store.filterStatus).toBe('working')
    })

    it('setFilterAgeGroup updates filterAgeGroup', () => {
      const store = useDwellerFilterStore()
      store.setFilterAgeGroup('adult')
      expect(store.filterAgeGroup).toBe('adult')
    })

    it('setSortBy updates sortBy', () => {
      const store = useDwellerFilterStore()
      store.setSortBy('level')
      expect(store.sortBy).toBe('level')
    })

    it('setSortDirection updates sortDirection', () => {
      const store = useDwellerFilterStore()
      store.setSortDirection('desc')
      expect(store.sortDirection).toBe('desc')
    })

    it('setViewMode updates viewMode', () => {
      const store = useDwellerFilterStore()
      store.setViewMode('grid')
      expect(store.viewMode).toBe('grid')
    })
  })
})
