import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref, nextTick } from 'vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { explorationApi } from '@/modules/exploration/api/exploration'
import { useAuthStore } from '@/modules/auth/stores/auth'
import axios from '@/core/plugins/axios'
import { addPendingReport } from '@/modules/exploration/composables/usePendingReports'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useToast } from '@/core/composables/useToast'
import type { UserProfile } from '@/modules/profile/models/profile'

vi.mock('@/core/plugins/axios')
vi.mock('@/modules/exploration/api/exploration', () => ({
  explorationApi: {
    dispatchToLocation: vi.fn(),
  },
}))
vi.mock('@/modules/exploration/composables/usePendingReports', () => ({
  addPendingReport: vi.fn(),
}))

const mockSseEvent = ref<Record<string, unknown> | null>(null)

const mockDwellerFilter = {
  dwellers: [{ id: 'dweller-1', first_name: 'Amata', last_name: 'Almodovar' }],
  fetchDwellerDetails: vi.fn().mockResolvedValue(null),
}

vi.mock('@/core/composables/useEventStream', () => ({
  useSse: vi.fn(() => ({
    start: vi.fn().mockResolvedValue(undefined),
    stopReconnect: vi.fn(),
    close: vi.fn(),
    event: mockSseEvent,
  })),
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: vi.fn(() => ({ filter: mockDwellerFilter })),
}))

describe('Exploration Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useToast().toasts.value = []
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
    dweller_luck: 8,
  }

  const mockExplorationProgress = {
    id: 'exploration-1',
    status: 'ACTIVE',
    progress_percentage: 25.5,
    time_remaining_seconds: 10800,
    elapsed_time_seconds: 3600,
    events: [],
    loot_collected: [],
  }

  const mockRewardsSummary = {
    caps: 150,
    items: [
      { item_name: 'Desk Fan', quantity: 1, rarity: 'Common', found_at: '2025-01-01T00:00:00Z' },
    ],
    experience: 750,
    distance: 50,
    enemies_defeated: 5,
    events_encountered: 3,
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
        { ...mockExploration, id: 'exploration-2', dweller_id: 'dweller-2' },
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
          status: 'active',
        },
        {
          ...mockExploration,
          id: 'exploration-4',
          dweller_id: 'dweller-4',
          vault_id: 'vault-1',
          status: 'completed',
        },
      ]

      const vaultExplorations = store.getActiveExplorationsForVault('vault-1')
      expect(vaultExplorations).toHaveLength(2)
      expect(vaultExplorations.every((e) => e.vault_id === 'vault-1')).toBe(true)
      expect(vaultExplorations.every((e) => e.status === 'active')).toBe(true)
    })

    it('getExplorationByDwellerId should include a dweller on the return leg', () => {
      const store = useExplorationStore()
      store.explorations = [{ ...mockExploration, status: 'returning' }]

      expect(store.getExplorationByDwellerId('dweller-1')?.status).toBe('returning')
    })

    it('getExplorationByDwellerId should prefer an active run over a stale returning one', () => {
      const store = useExplorationStore()
      store.explorations = [
        { ...mockExploration, id: 'exploration-old', status: 'returning' },
        { ...mockExploration, id: 'exploration-new', status: 'active' },
      ]

      expect(store.getExplorationByDwellerId('dweller-1')?.id).toBe('exploration-new')
    })

    it('getActiveExplorationsForVault should include returning explorations', () => {
      const store = useExplorationStore()
      store.explorations = [
        mockExploration,
        { ...mockExploration, id: 'exploration-2', dweller_id: 'dweller-2', status: 'returning' },
        { ...mockExploration, id: 'exploration-3', dweller_id: 'dweller-3', status: 'completed' },
      ]

      const vaultExplorations = store.getActiveExplorationsForVault('vault-1')
      expect(vaultExplorations.map((e) => e.id).sort()).toEqual(['exploration-1', 'exploration-2'])
    })
  })

  describe('sendDwellerToWasteland Action', () => {
    it('should send dweller successfully', async () => {
      const store = useExplorationStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockExploration })

      const result = await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4, 'test-token')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/explorations/send?vault_id=vault-1',
        { dweller_id: 'dweller-1', duration: 4, stimpaks: 0, radaways: 0 },
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

  describe('dispatchToLocation Action', () => {
    it('should dispatch a dweller to a location successfully', async () => {
      const store = useExplorationStore()
      useAuthStore().token = 'test-token'
      vi.mocked(explorationApi.dispatchToLocation).mockResolvedValueOnce(mockExploration)

      const result = await store.dispatchToLocation('vault-1', ['dweller-1'], 'loc-1')

      expect(explorationApi.dispatchToLocation).toHaveBeenCalledWith('test-token', 'vault-1', {
        dwellerIds: ['dweller-1'],
        locationId: 'loc-1',
      })
      expect(result).toEqual(mockExploration)
      expect(store.explorations).toContainEqual(mockExploration)
      expect(store.activeExplorations['exploration-1']).toEqual(mockExploration)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should upsert an existing exploration instead of duplicating it', async () => {
      const store = useExplorationStore()
      useAuthStore().token = 'test-token'
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }

      const updatedExploration = { ...mockExploration, total_caps_found: 100 }
      vi.mocked(explorationApi.dispatchToLocation).mockResolvedValueOnce(updatedExploration)

      await store.dispatchToLocation('vault-1', ['dweller-1', 'dweller-2'], 'loc-1')

      expect(store.explorations).toHaveLength(1)
      expect(store.explorations[0].total_caps_found).toBe(100)
    })

    it('should handle error', async () => {
      const store = useExplorationStore()
      useAuthStore().token = 'test-token'
      const error = new Error('Dispatch failed')
      vi.mocked(explorationApi.dispatchToLocation).mockRejectedValueOnce(error)

      await expect(store.dispatchToLocation('vault-1', ['dweller-1'], 'loc-1')).rejects.toThrow(
        'Dispatch failed'
      )

      expect(store.error).toBe('Failed to dispatch dweller')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchExplorationsByVault Action', () => {
    it('should fetch active explorations successfully', async () => {
      const store = useExplorationStore()
      const explorations = [mockExploration, { ...mockExploration, id: 'exploration-2' }]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: explorations })

      const result = await store.fetchExplorationsByVault('vault-1', 'test-token', true)

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/explorations/vault/vault-1?active_only=true',
        {
          headers: { Authorization: 'Bearer test-token' },
        }
      )
      expect(result).toEqual(explorations)
      expect(store.explorations).toEqual(explorations)
      expect(Object.keys(store.activeExplorations)).toHaveLength(2)
    })

    it('should fetch all explorations when activeOnly is false', async () => {
      const store = useExplorationStore()
      const explorations = [
        mockExploration,
        { ...mockExploration, id: 'exploration-2', status: 'completed' },
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: explorations })

      await store.fetchExplorationsByVault('vault-1', 'test-token', false)

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/explorations/vault/vault-1?active_only=false',
        {
          headers: { Authorization: 'Bearer test-token' },
        }
      )
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
        headers: { Authorization: 'Bearer test-token' },
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

    it('retains a directly loaded completed exploration for its detail view', async () => {
      const store = useExplorationStore()
      const completedExploration = { ...mockExploration, status: 'completed' }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: completedExploration })

      await store.fetchExplorationDetails('exploration-1', 'test-token')

      expect(store.explorations).toEqual([completedExploration])
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
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
        headers: { Authorization: 'Bearer test-token' },
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
        rewards_summary: { ...mockRewardsSummary, recalled_early: true, progress_percentage: 50 },
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
        rewards_summary: mockRewardsSummary,
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
        { ...mockExploration, id: 'exploration-3', dweller_id: 'dweller-3', status: 'completed' },
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
        events: [{ type: 'loot_found', description: 'Found loot!' }],
      }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: updatedExploration })

      await store.fetchExplorationDetails('exploration-1', 'test-token')

      expect(store.explorations[0].total_caps_found).toBe(100)
      expect(store.activeExplorations['exploration-1'].total_caps_found).toBe(100)
      expect(store.explorations[0].events).toHaveLength(1)
    })
  })

  describe('SSE Rewards Enqueuing', () => {
    it('should enqueue rewards via addPendingReport on completion SSE', async () => {
      const store = useExplorationStore()
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = {
        event: 'exploration',
        data: {
          type: 'exploration_complete',
          exploration_id: 'exploration-1',
          dweller_id: 'dweller-1',
          rewards: mockRewardsSummary,
        },
      }

      await nextTick()

      expect(addPendingReport).toHaveBeenCalledWith({
        explorationId: 'exploration-1',
        vaultId: 'vault-1',
        dwellerId: 'dweller-1',
        dwellerName: 'Amata Almodovar',
        rewards: mockRewardsSummary,
      })
    })

    it('should use fallback dweller name when dweller not found', async () => {
      const store = useExplorationStore()
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = {
        event: 'exploration',
        data: {
          type: 'exploration_complete',
          exploration_id: 'exploration-2',
          dweller_id: 'unknown-dweller',
          rewards: mockRewardsSummary,
        },
      }

      await nextTick()

      expect(addPendingReport).toHaveBeenCalledWith({
        explorationId: 'exploration-2',
        vaultId: 'vault-1',
        dwellerId: 'unknown-dweller',
        dwellerName: 'Dweller',
        rewards: mockRewardsSummary,
      })
    })

    it('should still set pendingSseRewards for live display', async () => {
      const store = useExplorationStore()
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = {
        event: 'exploration',
        data: {
          type: 'exploration_complete',
          dweller_id: 'dweller-1',
          rewards: mockRewardsSummary,
        },
      }

      await nextTick()

      expect(store.pendingSseRewards).toEqual({
        rewards: mockRewardsSummary,
        dwellerId: 'dweller-1',
      })
    })
  })

  describe('SSE Live Event Log', () => {
    const liveExploration = () => ({ ...mockExploration, events: [] as unknown[] })

    afterEach(() => {
      useExplorationStore().stopSseSubscription()
      mockSseEvent.value = null
    })

    it('appends live event frames and updates counters and health', async () => {
      const store = useExplorationStore()
      store.explorations = [liveExploration()]
      store.activeExplorations = { 'exploration-1': liveExploration() }
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = {
        event: 'exploration',
        data: {
          type: 'combat',
          exploration_id: 'exploration-1',
          event: {
            type: 'combat',
            description: 'Raider attacked',
            timestamp: '2026-01-01T00:05:00Z',
            time_elapsed_hours: 0.1,
          },
          total_caps_found: 120,
          enemies_encountered: 3,
          stimpaks: 2,
          radaways: 1,
          health: 85,
          radiation: 12,
        },
      }

      await nextTick()

      const updated = store.activeExplorations['exploration-1']
      expect(updated.events).toHaveLength(1)
      expect(updated.events[0].description).toBe('Raider attacked')
      expect(updated.total_caps_found).toBe(120)
      expect(updated.enemies_encountered).toBe(3)
      expect(updated.stimpaks).toBe(2)
      expect(updated.radaways).toBe(1)
      expect(updated.health).toBe(85)
      expect(updated.radiation).toBe(12)
    })

    it('deduplicates repeated event frames while still updating counters', async () => {
      const store = useExplorationStore()
      store.explorations = [liveExploration()]
      store.activeExplorations = { 'exploration-1': liveExploration() }
      store.startSseSubscription('vault-1', 'test-token')

      const frame = {
        event: 'exploration',
        data: {
          type: 'loot',
          exploration_id: 'exploration-1',
          event: {
            type: 'loot',
            description: 'Found a stash',
            timestamp: '2026-01-01T00:05:00Z',
            time_elapsed_hours: 0.1,
          },
        },
      }
      mockSseEvent.value = frame
      await nextTick()
      mockSseEvent.value = { ...frame, data: { ...frame.data, total_caps_found: 55 } }
      await nextTick()

      const updated = store.activeExplorations['exploration-1']
      expect(updated.events).toHaveLength(1)
      expect(updated.total_caps_found).toBe(55)
    })

    it('ignores per-event frames for unknown explorations', async () => {
      const store = useExplorationStore()
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = {
        event: 'exploration',
        data: {
          type: 'combat',
          exploration_id: 'unknown-exploration',
          event: { type: 'combat', description: 'Ghost', timestamp: '', time_elapsed_hours: 0 },
        },
      }

      await nextTick()

      expect(store.pendingSseRewards).toBeNull()
    })
  })

  describe('SSE Equip Event', () => {
    const liveExploration = () => ({ ...mockExploration, events: [] as unknown[] })

    const profileWithNotifications = (disabledCategories: string[]): UserProfile => ({
      id: 'profile-1',
      user_id: 'user-1',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      total_dwellers_created: 0,
      total_caps_earned: 0,
      total_explorations: 0,
      total_rooms_built: 0,
      total_dwellers_born: 0,
      total_dwellers_died: 0,
      deaths_by_health: 0,
      deaths_by_radiation: 0,
      deaths_by_incident: 0,
      deaths_by_exploration: 0,
      deaths_by_combat: 0,
      preferences: { notifications: { version: 1, disabled_categories: disabledCategories } },
    })

    const equipFrame = {
      event: 'exploration',
      data: {
        type: 'combat',
        exploration_id: 'exploration-1',
        dweller_id: 'dweller-1',
        event: {
          type: 'equip',
          description: 'Equipped a Hunting Rifle',
          timestamp: '2026-01-01T00:05:00Z',
          time_elapsed_hours: 0.1,
        },
      },
    }

    afterEach(() => {
      useExplorationStore().stopSseSubscription()
      mockSseEvent.value = null
    })

    it('shows an equip toast when exploration_updates is enabled', async () => {
      const store = useExplorationStore()
      useProfileStore().profile = profileWithNotifications([])
      store.explorations = [liveExploration()]
      store.activeExplorations = { 'exploration-1': liveExploration() }
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = equipFrame
      await nextTick()

      expect(
        useToast().toasts.value.some(
          (t) => t.message === 'Amata Almodovar equipped a Hunting Rifle'
        )
      ).toBe(true)
    })

    it('does not toast when exploration_updates is disabled', async () => {
      const store = useExplorationStore()
      useProfileStore().profile = profileWithNotifications(['exploration_updates'])
      store.explorations = [liveExploration()]
      store.activeExplorations = { 'exploration-1': liveExploration() }
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = equipFrame
      await nextTick()

      expect(
        useToast().toasts.value.some(
          (t) => t.message === 'Amata Almodovar equipped a Hunting Rifle'
        )
      ).toBe(false)
    })

    it('refreshes dweller details on an equip event', async () => {
      const store = useExplorationStore()
      store.explorations = [liveExploration()]
      store.activeExplorations = { 'exploration-1': liveExploration() }
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = equipFrame
      await nextTick()

      expect(mockDwellerFilter.fetchDwellerDetails).toHaveBeenCalledWith(
        'dweller-1',
        'test-token',
        true
      )
    })

    it('does not refresh dweller details for a non-equip event', async () => {
      const store = useExplorationStore()
      store.explorations = [liveExploration()]
      store.activeExplorations = { 'exploration-1': liveExploration() }
      store.startSseSubscription('vault-1', 'test-token')

      mockSseEvent.value = {
        event: 'exploration',
        data: {
          type: 'combat',
          exploration_id: 'exploration-1',
          dweller_id: 'dweller-1',
          event: {
            type: 'combat',
            description: 'Raider attacked',
            timestamp: '2026-01-01T00:05:00Z',
            time_elapsed_hours: 0.1,
          },
        },
      }
      await nextTick()

      expect(mockDwellerFilter.fetchDwellerDetails).not.toHaveBeenCalled()
    })
  })
})
