import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDwellerStore } from '@/stores/dweller'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

describe('Dweller Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Clear localStorage to reset filter/sort preferences
    localStorage.clear()
  })

  describe('Filter State Management', () => {
    it('should initialize with default filter status as "all"', () => {
      const store = useDwellerStore()
      expect(store.filterStatus).toBe('all')
    })

    it('should set filter status', () => {
      const store = useDwellerStore()

      store.setFilterStatus('working')
      expect(store.filterStatus).toBe('working')

      store.setFilterStatus('idle')
      expect(store.filterStatus).toBe('idle')

      store.setFilterStatus('exploring')
      expect(store.filterStatus).toBe('exploring')

      store.setFilterStatus('all')
      expect(store.filterStatus).toBe('all')
    })

    it('should set sort by option', () => {
      const store = useDwellerStore()

      store.setSortBy('name')
      expect(store.sortBy).toBe('name')

      store.setSortBy('level')
      expect(store.sortBy).toBe('level')
    })

    it('should set sort direction', () => {
      const store = useDwellerStore()

      store.setSortDirection('asc')
      expect(store.sortDirection).toBe('asc')

      store.setSortDirection('desc')
      expect(store.sortDirection).toBe('desc')
    })
  })

  describe('API Interaction', () => {
    it('should call API when fetching dwellers by vault', async () => {
      const mockDwellers = [
        { id: '1', first_name: 'John', last_name: 'Doe', status: 'working' },
        { id: '2', first_name: 'Jane', last_name: 'Smith', status: 'idle' }
      ]

      vi.mocked(axios.get).mockResolvedValue({ data: mockDwellers })

      const store = useDwellerStore()
      await store.fetchDwellersByVault('vault-123', 'test-token')

      expect(axios.get).toHaveBeenCalled()
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('vault-123'),
        expect.any(Object)
      )
    })

    it('should include status filter in API call when status is set', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      const store = useDwellerStore()
      store.setFilterStatus('working')

      await store.fetchDwellersByVault('vault-123', 'test-token', {
        status: 'working'
      })

      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('status=working'),
        expect.any(Object)
      )
    })

    it('should call assign API endpoint when assigning dweller to room', async () => {
      vi.mocked(axios.post).mockResolvedValue({
        data: { id: 'dweller-1', status: 'working', room_id: 'room-1' }
      })

      const store = useDwellerStore()
      await store.assignDwellerToRoom('dweller-1', 'room-1', 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/dwellers/dweller-1/move_to/room-1',
        null,
        expect.any(Object)
      )
    })

    it('should call update API endpoint when unassigning dweller', async () => {
      vi.mocked(axios.put).mockResolvedValue({
        data: { id: 'dweller-1', status: 'idle', room_id: null }
      })

      const store = useDwellerStore()
      await store.unassignDwellerFromRoom('dweller-1', 'test-token')

      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/dwellers/dweller-1',
        { room_id: null },
        expect.any(Object)
      )
    })
  })

  describe('Store Initialization', () => {
    it('should initialize with empty dwellers collections', () => {
      const store = useDwellerStore()

      expect(store.dwellers).toEqual([])
      expect(store.detailedDwellers).toEqual({})
    })

    it('should initialize with default sort settings', () => {
      const store = useDwellerStore()

      expect(store.sortBy).toBe('name')
      expect(store.sortDirection).toBe('asc')
    })

    it('should initialize with filter status as "all"', () => {
      const store = useDwellerStore()

      expect(store.filterStatus).toBe('all')
    })

    it('should initialize with empty dead dwellers collections', () => {
      const store = useDwellerStore()

      expect(store.deadDwellers).toEqual([])
      expect(store.graveyardDwellers).toEqual([])
    })
  })

  describe('Death System API', () => {
    it('should fetch dead dwellers', async () => {
      const mockDeadDwellers = [
        { id: '1', first_name: 'Dead', last_name: 'Dweller', is_dead: true, is_permanently_dead: false }
      ]

      vi.mocked(axios.get).mockResolvedValue({ data: mockDeadDwellers })

      const store = useDwellerStore()
      const result = await store.fetchDeadDwellers('vault-123', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/dwellers/vault/vault-123/dead',
        expect.any(Object)
      )
      expect(result).toEqual(mockDeadDwellers)
      expect(store.deadDwellers).toEqual(mockDeadDwellers)
    })

    it('should fetch graveyard dwellers', async () => {
      const mockGraveyardDwellers = [
        { id: '2', first_name: 'Permanent', last_name: 'Dead', is_dead: true, is_permanently_dead: true }
      ]

      vi.mocked(axios.get).mockResolvedValue({ data: mockGraveyardDwellers })

      const store = useDwellerStore()
       const result = await store.fetchGraveyardDwellers('vault-123', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/dwellers/vault/vault-123/graveyard',
        expect.any(Object)
      )
      expect(result).toEqual(mockGraveyardDwellers)
      expect(store.graveyardDwellers).toEqual(mockGraveyardDwellers)
    })

    it('should get revival cost', async () => {
      const mockCost = {
        dweller_id: 'dweller-1',
        revival_cost: 250,
        vault_caps: 1000,
        can_afford: true,
        days_until_permanent: 5
      }

      vi.mocked(axios.get).mockResolvedValue({ data: mockCost })

      const store = useDwellerStore()
      const result = await store.getRevivalCost('dweller-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/dwellers/dweller-1/revival_cost',
        expect.any(Object)
      )
      expect(result).toEqual(mockCost)
    })

    it('should revive dweller', async () => {
      const mockResponse = {
        dweller: { id: 'dweller-1', first_name: 'Revived', is_dead: false },
        caps_spent: 250
      }

      vi.mocked(axios.post).mockResolvedValue({ data: mockResponse })

      const store = useDwellerStore()
      // Add initial dead dweller to the store
      store.deadDwellers = [
        { id: 'dweller-1', first_name: 'Dead', last_name: 'Dweller', is_dead: true, is_permanently_dead: false } as any
      ]

      const result = await store.reviveDweller('dweller-1', 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/dwellers/dweller-1/revive',
        null,
        expect.any(Object)
      )
      expect(result).toEqual(mockResponse)
      // Dead dweller should be removed from list
      expect(store.deadDwellers.find(d => d.id === 'dweller-1')).toBeUndefined()
    })

    it('should handle error when getting revival cost fails', async () => {
      vi.mocked(axios.get).mockRejectedValue({
        response: { data: { detail: 'Dweller not found' } }
      })

      const store = useDwellerStore()
      const result = await store.getRevivalCost('invalid-id', 'test-token')

      expect(result).toBeNull()
    })

    it('should handle error when reviving dweller fails', async () => {
      vi.mocked(axios.post).mockRejectedValue({
        response: { data: { detail: 'Insufficient caps' } }
      })

      const store = useDwellerStore()
      const result = await store.reviveDweller('dweller-1', 'test-token')

      expect(result).toBeNull()
    })
  })
})
