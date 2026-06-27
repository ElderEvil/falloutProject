import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')
vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}))
vi.mock('@/modules/dwellers/stores/dwellerFilter', () => ({
  useDwellerFilterStore: () => ({
    dwellers: [],
    detailedDwellers: {},
  }),
}))

import { useDwellerDeathStore } from '@/modules/dwellers/stores/dwellerDeath'

describe('DwellerDeath Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  describe('State', () => {
    it('should initialize with empty state', () => {
      const store = useDwellerDeathStore()

      expect(store.deadDwellers).toEqual([])
      expect(store.graveyardDwellers).toEqual([])
      expect(store.deadLoadingCount).toBe(0)
      expect(store.isDeadLoading).toBe(false)
    })
  })

  describe('fetchDeadDwellers', () => {
    it('should fetch dead dwellers and update state', async () => {
      const mockDead = [
        { id: 'd1', first_name: 'John', last_name: 'Doe', level: 5, cause_of_death: 'Radiation' },
        { id: 'd2', first_name: 'Jane', last_name: 'Smith', level: 3, cause_of_death: 'Combat' },
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockDead })

      const store = useDwellerDeathStore()
      const result = await store.fetchDeadDwellers('vault-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/dwellers/vault/vault-1/dead',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.deadDwellers).toEqual(mockDead)
      expect(result).toEqual(mockDead)
      expect(store.isDeadLoading).toBe(false)
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useDwellerDeathStore()
      const result = await store.fetchDeadDwellers('vault-1', 'test-token')

      expect(result).toEqual([])
      expect(store.deadDwellers).toEqual([])
      expect(store.isDeadLoading).toBe(false)
    })

    it('should track loading count correctly with concurrent calls', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      const store = useDwellerDeathStore()
      const p1 = store.fetchDeadDwellers('vault-1', 'token')
      const p2 = store.fetchDeadDwellers('vault-1', 'token')

      expect(store.deadLoadingCount).toBe(2)
      expect(store.isDeadLoading).toBe(true)

      await Promise.all([p1, p2])

      expect(store.deadLoadingCount).toBe(0)
      expect(store.isDeadLoading).toBe(false)
    })
  })

  describe('fetchGraveyardDwellers', () => {
    it('should fetch graveyard dwellers and update state', async () => {
      const mockGraveyard = [
        { id: 'd3', first_name: 'Dead', last_name: 'Dweller', level: 10, cause_of_death: 'Old age' },
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockGraveyard })

      const store = useDwellerDeathStore()
      const result = await store.fetchGraveyardDwellers('vault-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/dwellers/vault/vault-1/graveyard',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.graveyardDwellers).toEqual(mockGraveyard)
      expect(result).toEqual(mockGraveyard)
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useDwellerDeathStore()
      const result = await store.fetchGraveyardDwellers('vault-1', 'test-token')

      expect(result).toEqual([])
    })
  })

  describe('getRevivalCost', () => {
    it('should fetch revival cost', async () => {
      const mockCost = { caps_cost: 500, stimpak_cost: 2 }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockCost })

      const store = useDwellerDeathStore()
      const result = await store.getRevivalCost('d1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/dwellers/d1/revival_cost',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockCost)
    })

    it('should return null on error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('API error'))

      const store = useDwellerDeathStore()
      const result = await store.getRevivalCost('d1', 'test-token')

      expect(result).toBeNull()
    })
  })

  describe('reviveDweller', () => {
    it('should revive a dweller and remove from deadDwellers', async () => {
      const mockResponse = {
        dweller: { id: 'd1', first_name: 'John', last_name: 'Doe' },
        caps_spent: 500,
        stimpaks_used: 2,
      }
      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockResponse })

      const store = useDwellerDeathStore()
      store.deadDwellers = [
        { id: 'd1', first_name: 'John', last_name: 'Doe', level: 5 },
        { id: 'd2', first_name: 'Other', last_name: 'Dead', level: 3 },
      ]

      const result = await store.reviveDweller('d1', 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/dwellers/d1/revive',
        null,
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockResponse)
      expect(store.deadDwellers).toHaveLength(1)
      expect(store.deadDwellers[0].id).toBe('d2')
    })

    it('should return null on error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Revive failed'))

      const store = useDwellerDeathStore()
      const result = await store.reviveDweller('d1', 'test-token')

      expect(result).toBeNull()
    })
  })
})
