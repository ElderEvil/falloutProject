import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useExplorationStore } from '@/stores/exploration'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

describe('Exploration Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockExploration = {
    id: 'exploration-1',
    vault_id: 'vault-1',
    dweller_id: 'dweller-1',
    status: 'active',
    duration: 4,
    start_time: '2025-01-01T00:00:00Z',
    end_time: null,
    events: [],
    loot_collected: [],
    total_distance: 0,
    total_caps_found: 0,
    enemies_encountered: 0,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    dweller_strength: 5,
    dweller_perception: 6,
    dweller_endurance: 7,
    dweller_charisma: 4,
    dweller_intelligence: 5,
    dweller_agility: 6,
    dweller_luck: 8
  }

  const mockExplorationProgress = {
    id: 'exploration-1',
    status: 'ACTIVE',
    progress_percentage: 25.5,
    time_remaining_seconds: 10800,
    elapsed_time_seconds: 3600,
    events: [],
    loot_collected: []
  }

  const mockRewardsSummary = {
    caps: 150,
    items: [
      { item_name: 'Desk Fan', quantity: 1, rarity: 'Common', found_at: '2025-01-01T00:00:00Z' }
    ],
    experience: 750,
    distance: 50,
    enemies_defeated: 5,
    events_encountered: 3
  }

  describe('State Initialization', () => {
    it('should initialize with empty state', () => {
      const store = useExplorationStore()
      expect(store.explorations).toEqual([])
      expect(store.activeExplorations).toEqual({})
      expect(store.lastRewards).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('Getters', () => {
    it('getExplorationByDwellerId should return active exploration for dweller', () => {
      const store = useExplorationStore()
      store.explorations = [
        mockExploration,
        { ...mockExploration, id: 'exploration-2', dweller_id: 'dweller-2' }
      ]

      const exploration = store.getExplorationByDwellerId('dweller-1')
      expect(exploration).toEqual(mockExploration)
    })

    it('getExplorationByDwellerId should return undefined when not found', () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]

      const exploration = store.getExplorationByDwellerId('dweller-999')
      expect(exploration).toBeUndefined()
    })

    it('getExplorationByDwellerId should only return active explorations', () => {
      const store = useExplorationStore()
      const completedExploration = { ...mockExploration, status: 'completed' }
      store.explorations = [completedExploration]

      const exploration = store.getExplorationByDwellerId('dweller-1')
      expect(exploration).toBeUndefined()
    })

    it('getActiveExplorationsForVault should filter by vault and status', () => {
      const store = useExplorationStore()
      store.explorations = [
        mockExploration,
        { ...mockExploration, id: 'exploration-2', dweller_id: 'dweller-2', vault_id: 'vault-1' },
        {
          ...mockExploration,
          id: 'exploration-3',
          dweller_id: 'dweller-3',
          vault_id: 'vault-2',
          status: 'active'
        },
        {
          ...mockExploration,
          id: 'exploration-4',
          dweller_id: 'dweller-4',
          vault_id: 'vault-1',
          status: 'completed'
        }
      ]

      const vaultExplorations = store.getActiveExplorationsForVault('vault-1')
      expect(vaultExplorations).toHaveLength(2)
      expect(vaultExplorations.every((e) => e.vault_id === 'vault-1')).toBe(true)
      expect(vaultExplorations.every((e) => e.status === 'active')).toBe(true)
    })

    it('isDwellerExploring should return true when dweller is exploring', () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]

      expect(store.isDwellerExploring('dweller-1')).toBe(true)
    })

    it('isDwellerExploring should return false when dweller is not exploring', () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]

      expect(store.isDwellerExploring('dweller-999')).toBe(false)
    })

    it('isDwellerExploring should return false for completed explorations', () => {
      const store = useExplorationStore()
      const completedExploration = { ...mockExploration, status: 'completed' }
      store.explorations = [completedExploration]

      expect(store.isDwellerExploring('dweller-1')).toBe(false)
    })
  })

  describe('sendDwellerToWasteland Action', () => {
    it('should send dweller successfully', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockExploration })

      const result = await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4, 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/explorations/send?vault_id=vault-1',
        { dweller_id: 'dweller-1', duration: 4 },
        { headers: { Authorization: 'Bearer test-token' } }
      )
      expect(result).toEqual(mockExploration)
      expect(store.explorations).toContainEqual(mockExploration)
      expect(store.activeExplorations['exploration-1']).toEqual(mockExploration)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should set loading state correctly', async () => {
      const store = useExplorationStore()
      let loadingDuringRequest = false

      vi.mocked(axios.post).mockImplementation(async () => {
        loadingDuringRequest = store.isLoading
        return { data: mockExploration }
      })

      await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4, 'test-token')

      expect(loadingDuringRequest).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      const error = new Error('Failed to send dweller')
      vi.mocked(axios.post).mockRejectedValueOnce(error)

      await expect(
        store.sendDwellerToWasteland('vault-1', 'dweller-1', 4, 'test-token')
      ).rejects.toThrow('Failed to send dweller')

      expect(store.error).toBe('Failed to send dweller to wasteland')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchExplorationsByVault Action', () => {
    it('should fetch active explorations successfully', async () => {
      const store = useExplorationStore()
      const explorations = [mockExploration, { ...mockExploration, id: 'exploration-2' }]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: explorations })

      const result = await store.fetchExplorationsByVault('vault-1', 'test-token', true)

      expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/vault/vault-1?active_only=true', {
        headers: { Authorization: 'Bearer test-token' }
      })
      expect(result).toEqual(explorations)
      expect(store.explorations).toEqual(explorations)
      expect(Object.keys(store.activeExplorations)).toHaveLength(2)
    })

    it('should fetch all explorations when activeOnly is false', async () => {
      const store = useExplorationStore()
      const explorations = [
        mockExploration,
        { ...mockExploration, id: 'exploration-2', status: 'completed' }
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: explorations })

      await store.fetchExplorationsByVault('vault-1', 'test-token', false)

      expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/vault/vault-1?active_only=false', {
        headers: { Authorization: 'Bearer test-token' }
      })
      expect(store.explorations).toEqual(explorations)
      expect(Object.keys(store.activeExplorations)).toHaveLength(1) // Only active ones in map
    })

    it('should handle empty response', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      await store.fetchExplorationsByVault('vault-1', 'test-token')

      expect(store.explorations).toEqual([])
      expect(store.activeExplorations).toEqual({})
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      await expect(store.fetchExplorationsByVault('vault-1', 'test-token')).rejects.toThrow(
        'Fetch failed'
      )

      expect(store.error).toBe('Failed to fetch explorations')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchExplorationDetails Action', () => {
    it('should fetch and update exploration details', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }

      const updatedExploration = { ...mockExploration, total_distance: 50 }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: updatedExploration })

      const result = await store.fetchExplorationDetails('exploration-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/exploration-1', {
        headers: { Authorization: 'Bearer test-token' }
      })
      expect(result).toEqual(updatedExploration)
      expect(store.explorations[0]).toEqual(updatedExploration)
      expect(store.activeExplorations['exploration-1']).toEqual(updatedExploration)
    })

    it('should remove from activeExplorations when status is not active', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }

      const completedExploration = { ...mockExploration, status: 'completed' }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: completedExploration })

      await store.fetchExplorationDetails('exploration-1', 'test-token')

      expect(store.activeExplorations['exploration-1']).toBeUndefined()
      expect(store.explorations[0].status).toBe('completed')
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))

      await expect(store.fetchExplorationDetails('exploration-1', 'test-token')).rejects.toThrow(
        'Fetch failed'
      )
    })
  })

  describe('fetchExplorationProgress Action', () => {
    it('should fetch progress successfully', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockExplorationProgress })

      const result = await store.fetchExplorationProgress('exploration-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith('/api/v1/explorations/exploration-1/progress', {
        headers: { Authorization: 'Bearer test-token' }
      })
      expect(result).toEqual(mockExplorationProgress)
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Progress fetch failed'))

      await expect(store.fetchExplorationProgress('exploration-1', 'test-token')).rejects.toThrow(
        'Progress fetch failed'
      )
    })
  })

  describe('recallDweller Action', () => {
    it('should recall dweller successfully', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }

      const recalledExploration = { ...mockExploration, status: 'recalled' }
      const response = {
        exploration: recalledExploration,
        rewards_summary: { ...mockRewardsSummary, recalled_early: true, progress_percentage: 50 }
      }
      vi.mocked(axios.post).mockResolvedValueOnce({ data: response })

      const result = await store.recallDweller('exploration-1', 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/explorations/exploration-1/recall',
        {},
        { headers: { Authorization: 'Bearer test-token' } }
      )
      expect(result).toEqual(response)
      expect(store.lastRewards).toEqual(response.rewards_summary)
      expect(store.explorations[0].status).toBe('recalled')
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
      expect(store.isLoading).toBe(false)
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Recall failed'))

      await expect(store.recallDweller('exploration-1', 'test-token')).rejects.toThrow(
        'Recall failed'
      )

      expect(store.error).toBe('Failed to recall dweller')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('completeExploration Action', () => {
    it('should complete exploration successfully', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }

      const completedExploration = { ...mockExploration, status: 'completed' }
      const response = {
        exploration: completedExploration,
        rewards_summary: mockRewardsSummary
      }
      vi.mocked(axios.post).mockResolvedValueOnce({ data: response })

      const result = await store.completeExploration('exploration-1', 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/explorations/exploration-1/complete',
        {},
        { headers: { Authorization: 'Bearer test-token' } }
      )
      expect(result).toEqual(response)
      expect(store.lastRewards).toEqual(response.rewards_summary)
      expect(store.explorations[0].status).toBe('completed')
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
      expect(store.isLoading).toBe(false)
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Complete failed'))

      await expect(store.completeExploration('exploration-1', 'test-token')).rejects.toThrow(
        'Complete failed'
      )

      expect(store.error).toBe('Failed to complete exploration')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('clearLastRewards Action', () => {
    it('should clear lastRewards', () => {
      const store = useExplorationStore()
      store.lastRewards = mockRewardsSummary

      store.clearLastRewards()

      expect(store.lastRewards).toBeNull()
    })
  })

  describe('clearError Action', () => {
    it('should clear error', () => {
      const store = useExplorationStore()
      store.error = 'Some error'

      store.clearError()

      expect(store.error).toBeNull()
    })
  })

  describe('State Management', () => {
    it('should maintain explorations array and activeExplorations map in sync', async () => {
      const store = useExplorationStore()
      const explorations = [
        mockExploration,
        { ...mockExploration, id: 'exploration-2', dweller_id: 'dweller-2', status: 'active' },
        { ...mockExploration, id: 'exploration-3', dweller_id: 'dweller-3', status: 'completed' }
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: explorations })

      await store.fetchExplorationsByVault('vault-1', 'test-token')

      expect(store.explorations).toHaveLength(3)
      expect(Object.keys(store.activeExplorations)).toHaveLength(2) // Only active ones
      expect(store.activeExplorations['exploration-1']).toBeDefined()
      expect(store.activeExplorations['exploration-2']).toBeDefined()
      expect(store.activeExplorations['exploration-3']).toBeUndefined()
    })

    it('should update both explorations array and activeExplorations when updating exploration', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }

      const updatedExploration = {
        ...mockExploration,
        total_caps_found: 100,
        events: [{ type: 'loot_found', description: 'Found loot!' }]
      }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: updatedExploration })

      await store.fetchExplorationDetails('exploration-1', 'test-token')

      expect(store.explorations[0].total_caps_found).toBe(100)
      expect(store.activeExplorations['exploration-1'].total_caps_found).toBe(100)
      expect(store.explorations[0].events).toHaveLength(1)
    })
  })
})
