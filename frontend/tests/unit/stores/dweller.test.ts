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
  })
})
