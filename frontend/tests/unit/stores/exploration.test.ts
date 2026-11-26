import { describe, it, expect, beforeEach, afterEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { ref, nextTick } from 'vue'
import {
  ACTIVE_EXPLORATIONS_REFRESH_MS,
  useExplorationStore,
} from '@/modules/exploration/stores/exploration'
import { explorationApi } from '@/modules/exploration/api/exploration'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { addPendingReport } from '@/modules/exploration/composables/usePendingReports'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useToast } from '@/core/composables/useToast'
import type { UserProfile } from '@/modules/profile/models/profile'

vi.mock('@/modules/exploration/api/exploration', () => ({
  explorationApi: {
    dispatchToLocation: vi.fn(),
    suggestHeading: vi.fn(),
    sendDwellerToWasteland: vi.fn(),
    getExplorationsByVault: vi.fn(),
    getExploration: vi.fn(),
    getExplorationProgress: vi.fn(),
    recallDweller: vi.fn(),
    completeExploration: vi.fn(),
    resolveOverflowItem: vi.fn(),
    getPendingOverflow: vi.fn(),
    getExplorationParty: vi.fn(),
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

/** A fresh base exploration; tests mutate store state, so it is rebuilt per test. */
const baseExploration = () => ({
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
})

let mockExploration = baseExploration()

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

/** An exploration row; only fields a test cares about need naming. */
const run = (overrides: Record<string, unknown> = {}) =>
  ({ ...mockExploration, ...overrides }) as typeof mockExploration

/** A live exploration whose event log the SSE handler can append to. */
const liveRun = (overrides: Record<string, unknown> = {}) =>
  ({ ...mockExploration, events: [], ...overrides }) as typeof mockExploration

const explorationEvent = (type: string, description: string) => ({
  type,
  description,
  timestamp: '2026-01-01T00:05:00Z',
  time_elapsed_hours: 0.1,
})

/** Push one SSE frame onto the mocked stream and let the watcher settle. */
async function emitSse(data: Record<string, unknown>) {
  mockSseEvent.value = { event: 'exploration', data }
  await nextTick()
}

const toastShownFor = (message: string) =>
  useToast().toasts.value.some((toast) => toast.message === message)

describe('Exploration Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockExploration = baseExploration()
    useToast().toasts.value = []
  })

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
      store.explorations = [mockExploration, run({ id: 'exploration-2', dweller_id: 'dweller-2' })]
      expect(store.getExplorationByDwellerId('dweller-1')).toEqual(mockExploration)
    })

    it('getExplorationByDwellerId should return undefined for a missing or completed run', () => {
      const store = useExplorationStore()
      store.explorations = [run({ status: 'completed' })]
      expect(store.getExplorationByDwellerId('dweller-1')).toBeUndefined()
      expect(store.getExplorationByDwellerId('dweller-999')).toBeUndefined()
    })

    it('getActiveExplorationsForVault should filter by vault and active-ish status', () => {
      const store = useExplorationStore()
      store.explorations = [
        mockExploration,
        run({ id: 'exploration-2', dweller_id: 'dweller-2' }),
        run({ id: 'exploration-3', dweller_id: 'dweller-3', vault_id: 'vault-2' }),
        run({ id: 'exploration-4', dweller_id: 'dweller-4', status: 'completed' }),
      ]

      const vaultExplorations = store.getActiveExplorationsForVault('vault-1')
      expect(vaultExplorations.map((exploration) => exploration.id)).toEqual([
        'exploration-1',
        'exploration-2',
      ])
    })

    it('treats the return leg as active and prefers an active run over a stale returning one', () => {
      const store = useExplorationStore()
      store.explorations = [run({ status: 'returning' })]

      expect(store.getExplorationByDwellerId('dweller-1')?.status).toBe('returning')
      expect(store.getActiveExplorationsForVault('vault-1').map((entry) => entry.id)).toEqual([
        'exploration-1',
      ])
      store.explorations = [
        run({ id: 'exploration-old', status: 'returning' }),
        run({ id: 'exploration-new', status: 'active' }),
        run({ id: 'exploration-done', dweller_id: 'dweller-3', status: 'completed' }),
      ]
      expect(store.getExplorationByDwellerId('dweller-1')?.id).toBe('exploration-new')
      expect(store.getActiveExplorationsForVault('vault-1').map((entry) => entry.id)).toEqual([
        'exploration-old',
        'exploration-new',
      ])
    })
  })

  describe('sendDwellerToWasteland Action', () => {
    it('should send dweller successfully', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.sendDwellerToWasteland).mockResolvedValueOnce(mockExploration)

      const result = await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4)
      expect(explorationApi.sendDwellerToWasteland).toHaveBeenCalledWith('vault-1', {
        dweller_id: 'dweller-1',
        duration: 4,
        stimpaks: 0,
        radaways: 0,
      })
      expect(result).toEqual(mockExploration)
      expect(store.explorations).toContainEqual(mockExploration)
      expect(store.activeExplorations['exploration-1']).toEqual(mockExploration)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should set loading state correctly', async () => {
      const store = useExplorationStore()
      let loadingDuringRequest = false

      vi.mocked(explorationApi.sendDwellerToWasteland).mockImplementation(async () => {
        loadingDuringRequest = store.isLoading
        return mockExploration
      })
      await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4)
      expect(loadingDuringRequest).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('sends heading_degrees with supplies and omits it for a free-roam send', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.sendDwellerToWasteland).mockResolvedValue(mockExploration)

      await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4, 2, 1, 90)
      expect(explorationApi.sendDwellerToWasteland).toHaveBeenCalledWith('vault-1', {
        dweller_id: 'dweller-1',
        duration: 4,
        stimpaks: 2,
        radaways: 1,
        heading_degrees: 90,
      })
      await store.sendDwellerToWasteland('vault-1', 'dweller-1', 4)
      expect(explorationApi.sendDwellerToWasteland).toHaveBeenLastCalledWith('vault-1', {
        dweller_id: 'dweller-1',
        duration: 4,
        stimpaks: 0,
        radaways: 0,
      })
    })
  })

  describe('dispatchToLocation Action', () => {
    it('should dispatch a dweller to a location successfully', async () => {
      const store = useExplorationStore()
      useAuthStore().token = 'test-token'
      vi.mocked(explorationApi.dispatchToLocation).mockResolvedValueOnce(mockExploration)

      const result = await store.dispatchToLocation('vault-1', ['dweller-1'], 'loc-1')
      expect(explorationApi.dispatchToLocation).toHaveBeenCalledWith('vault-1', {
        dwellerIds: ['dweller-1'],
        locationId: 'loc-1',
        stimpaks: 0,
        radaways: 0,
        purpose: 'clear',
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
      vi.mocked(explorationApi.dispatchToLocation).mockResolvedValueOnce(
        run({ total_caps_found: 100 })
      )

      await store.dispatchToLocation('vault-1', ['dweller-1', 'dweller-2'], 'loc-1')
      expect(store.explorations).toHaveLength(1)
      expect(store.explorations[0].total_caps_found).toBe(100)
    })
  })

  describe('fetchExplorationsByVault Action', () => {
    it('should fetch active explorations successfully', async () => {
      const store = useExplorationStore()
      const explorations = [mockExploration, run({ id: 'exploration-2' })]
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce(explorations)

      const result = await store.fetchExplorationsByVault('vault-1', true)
      expect(explorationApi.getExplorationsByVault).toHaveBeenCalledWith('vault-1', true)
      expect(result).toEqual(explorations)
      expect(store.explorations).toEqual(explorations)
      expect(Object.keys(store.activeExplorations)).toHaveLength(2)
    })

    it('keeps the pack figures and activity the list payload now carries', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce([
        run({
          events: [explorationEvent('loot', 'Found a desk fan')],
          loot_collected: mockRewardsSummary.items,
          carry_capacity: 21,
          pack_slots_used: 2,
        }),
      ])

      const [exploration] = await store.fetchExplorationsByVault('vault-1', true)
      expect(exploration).toMatchObject({ carry_capacity: 21, pack_slots_used: 2 })
      expect(exploration.loot_collected).toHaveLength(1)
      expect(exploration.events[0]?.description).toBe('Found a desk fan')
    })

    it('should fetch all explorations and map only the active ones when activeOnly is false', async () => {
      const store = useExplorationStore()
      const explorations = [mockExploration, run({ id: 'exploration-2', status: 'completed' })]
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce(explorations)

      await store.fetchExplorationsByVault('vault-1', false)
      expect(explorationApi.getExplorationsByVault).toHaveBeenCalledWith('vault-1', false)
      expect(store.explorations).toEqual(explorations)
      expect(Object.keys(store.activeExplorations)).toHaveLength(1)
    })

    it('should handle empty response', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce([])
      await store.fetchExplorationsByVault('vault-1')
      expect(store.explorations).toEqual([])
      expect(store.activeExplorations).toEqual({})
    })

    it('does not toggle loading for a silent background refresh', () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockImplementationOnce(
        () => new Promise(() => undefined)
      )

      void store.fetchExplorationsByVault('vault-1', true, true)
      expect(store.isLoading).toBe(false)
    })

    it('keeps the previous error when a silent refresh fails and clears it on success', async () => {
      const store = useExplorationStore()
      store.error = 'previous error'
      vi.mocked(explorationApi.getExplorationsByVault).mockRejectedValueOnce(
        new Error('Fetch failed')
      )

      await expect(store.fetchExplorationsByVault('vault-1', true, true)).rejects.toThrow(
        'Fetch failed'
      )
      expect(store.error).toBe('previous error')
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce([])
      await store.fetchExplorationsByVault('vault-1', true, true)
      expect(store.error).toBeNull()
    })
  })

  describe('action failures', () => {
    it.each([
      [
        'sendDwellerToWasteland',
        explorationApi.sendDwellerToWasteland,
        (store: ReturnType<typeof useExplorationStore>) =>
          store.sendDwellerToWasteland('vault-1', 'dweller-1', 4),
        'Failed to send dweller',
        'Failed to send dweller to wasteland',
      ],
      [
        'dispatchToLocation',
        explorationApi.dispatchToLocation,
        (store: ReturnType<typeof useExplorationStore>) =>
          store.dispatchToLocation('vault-1', ['dweller-1'], 'loc-1'),
        'Dispatch failed',
        'Failed to dispatch dweller',
      ],
      [
        'recallDweller',
        explorationApi.recallDweller,
        (store: ReturnType<typeof useExplorationStore>) => store.recallDweller('exploration-1'),
        'Recall failed',
        'Failed to recall dweller',
      ],
      [
        'completeExploration',
        explorationApi.completeExploration,
        (store: ReturnType<typeof useExplorationStore>) =>
          store.completeExploration('exploration-1'),
        'Complete failed',
        'Failed to complete exploration',
      ],
      [
        'fetchExplorationsByVault',
        explorationApi.getExplorationsByVault,
        (store: ReturnType<typeof useExplorationStore>) =>
          store.fetchExplorationsByVault('vault-1'),
        'Fetch failed',
        'Failed to fetch explorations',
      ],
    ] as [string, () => unknown, (store: never) => Promise<unknown>, string, string][])(
      '%s rejects, records the store error and clears loading',
      async (_, api, invoke, thrown, recorded) => {
        const store = useExplorationStore()
        useAuthStore().token = 'test-token'
        vi.mocked(api).mockRejectedValueOnce(new Error(thrown))

        await expect(invoke(store as never)).rejects.toThrow(thrown)

        expect(store.error).toBe(recorded)
        expect(store.isLoading).toBe(false)
      }
    )

    it('propagates a progress failure without touching the shared error', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationProgress).mockRejectedValueOnce(
        new Error('Progress fetch failed')
      )

      await expect(store.fetchExplorationProgress('exploration-1')).rejects.toThrow(
        'Progress fetch failed'
      )
      expect(store.error).toBeNull()
    })
  })

  describe('fetchExplorationDetails Action', () => {
    it('should fetch and update exploration details', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }
      const updatedExploration = run({ total_distance: 50 })
      vi.mocked(explorationApi.getExploration).mockResolvedValueOnce(updatedExploration)

      const result = await store.fetchExplorationDetails('exploration-1')
      expect(explorationApi.getExploration).toHaveBeenCalledWith('exploration-1')
      expect(result).toEqual(updatedExploration)
      expect(store.explorations[0]).toEqual(updatedExploration)
      expect(store.activeExplorations['exploration-1']).toEqual(updatedExploration)
    })

    it('drops a run from the active map once it completes but keeps it for the detail view', async () => {
      const store = useExplorationStore()
      const completedExploration = run({ status: 'completed' })
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }
      vi.mocked(explorationApi.getExploration).mockResolvedValueOnce(completedExploration)

      await store.fetchExplorationDetails('exploration-1')
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
      expect(store.explorations[0].status).toBe('completed')
      // A directly loaded completed run is still retained when it was not cached.
      const coldStore = useExplorationStore()
      coldStore.explorations = []
      vi.mocked(explorationApi.getExploration).mockResolvedValueOnce(completedExploration)
      await coldStore.fetchExplorationDetails('exploration-1')
      expect(coldStore.explorations).toEqual([completedExploration])
      expect(coldStore.activeExplorations['exploration-1']).toBeUndefined()
    })

    it('surfaces the failure to the caller', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExploration).mockRejectedValueOnce(new Error('Fetch failed'))
      await expect(store.fetchExplorationDetails('exploration-1')).rejects.toThrow('Fetch failed')
    })
  })

  describe('fetchExplorationProgress Action', () => {
    it('should fetch progress successfully', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationProgress).mockResolvedValueOnce(
        mockExplorationProgress
      )

      const result = await store.fetchExplorationProgress('exploration-1')
      expect(explorationApi.getExplorationProgress).toHaveBeenCalledWith('exploration-1')
      expect(result).toEqual(mockExplorationProgress)
    })
  })

  describe('recallDweller Action', () => {
    it('should recall dweller successfully', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }
      const response = {
        exploration: run({ status: 'recalled' }),
        rewards_summary: { ...mockRewardsSummary, recalled_early: true, progress_percentage: 50 },
      }
      vi.mocked(explorationApi.recallDweller).mockResolvedValueOnce(response)

      const result = await store.recallDweller('exploration-1')
      expect(explorationApi.recallDweller).toHaveBeenCalledWith('exploration-1')
      expect(result).toEqual(response)
      expect(store.lastRewards).toEqual(response.rewards_summary)
      expect(store.explorations[0].status).toBe('recalled')
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
      expect(store.isLoading).toBe(false)
    })
  })

  describe('completeExploration Action', () => {
    it('should complete exploration successfully', async () => {
      const store = useExplorationStore()
      store.explorations = [mockExploration]
      store.activeExplorations = { 'exploration-1': mockExploration }
      const response = {
        exploration: run({ status: 'completed' }),
        rewards_summary: mockRewardsSummary,
      }
      vi.mocked(explorationApi.completeExploration).mockResolvedValueOnce(response)

      const result = await store.completeExploration('exploration-1')
      expect(explorationApi.completeExploration).toHaveBeenCalledWith('exploration-1')
      expect(result).toEqual(response)
      expect(store.lastRewards).toEqual(response.rewards_summary)
      expect(store.explorations[0].status).toBe('completed')
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
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
    it('keeps the explorations array and the active map in sync on fetch and detail update', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce([
        mockExploration,
        run({ id: 'exploration-2', dweller_id: 'dweller-2' }),
        run({ id: 'exploration-3', dweller_id: 'dweller-3', status: 'completed' }),
      ])

      await store.fetchExplorationsByVault('vault-1')
      expect(store.explorations).toHaveLength(3)
      expect(Object.keys(store.activeExplorations)).toEqual(['exploration-1', 'exploration-2'])
      vi.mocked(explorationApi.getExploration).mockResolvedValueOnce(
        run({
          total_caps_found: 100,
          events: [{ type: 'loot_found', description: 'Found loot!' }],
        })
      )
      await store.fetchExplorationDetails('exploration-1')
      expect(store.explorations[0].total_caps_found).toBe(100)
      expect(store.activeExplorations['exploration-1'].total_caps_found).toBe(100)
      expect(store.explorations[0].events).toHaveLength(1)
    })
  })

  describe('SSE Rewards Enqueuing', () => {
    it('should enqueue rewards via addPendingReport on completion SSE', async () => {
      const store = useExplorationStore()
      store.startSseSubscription('vault-1', 'test-token')

      await emitSse({
        type: 'exploration_complete',
        exploration_id: 'exploration-1',
        dweller_id: 'dweller-1',
        rewards: mockRewardsSummary,
      })
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

      await emitSse({
        type: 'exploration_complete',
        exploration_id: 'exploration-2',
        dweller_id: 'unknown-dweller',
        rewards: mockRewardsSummary,
      })
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

      await emitSse({
        type: 'exploration_complete',
        dweller_id: 'dweller-1',
        rewards: mockRewardsSummary,
      })
      expect(store.pendingSseRewards).toEqual({
        rewards: mockRewardsSummary,
        dwellerId: 'dweller-1',
      })
    })
  })

  describe('SSE Deleted Exploration', () => {
    it('closes the journey without queuing a reward report', async () => {
      const store = useExplorationStore()
      const closed = run()
      store.explorations = [closed]
      store.activeExplorations = { 'exploration-1': closed }
      store.startSseSubscription('vault-1', 'test-token')

      await emitSse({
        type: 'exploration_deleted',
        exploration_id: 'exploration-1',
        dweller_id: 'dweller-1',
        status: 'recalled',
      })
      expect(store.explorations[0].status).toBe('recalled')
      expect(store.activeExplorations['exploration-1']).toBeUndefined()
      expect(store.pendingSseRewards).toBeNull()
      expect(addPendingReport).not.toHaveBeenCalled()
    })
  })

  describe('SSE Live Event Log', () => {
    beforeEach(() => {
      const store = useExplorationStore()
      store.explorations = [liveRun()]
      store.activeExplorations = { 'exploration-1': liveRun() }
      store.startSseSubscription('vault-1', 'test-token')
    })

    afterEach(() => {
      useExplorationStore().stopSseSubscription()
      mockSseEvent.value = null
    })

    it('appends live event frames and updates counters and health', async () => {
      await emitSse({
        type: 'combat',
        exploration_id: 'exploration-1',
        event: explorationEvent('combat', 'Raider attacked'),
        total_caps_found: 120,
        enemies_encountered: 3,
        stimpaks: 2,
        radaways: 1,
        health: 85,
        radiation: 12,
      })

      const updated = useExplorationStore().activeExplorations['exploration-1']
      expect(updated.events).toHaveLength(1)
      expect(updated.events[0].description).toBe('Raider attacked')
      expect(updated).toMatchObject({
        total_caps_found: 120,
        enemies_encountered: 3,
        stimpaks: 2,
        radaways: 1,
        health: 85,
        radiation: 12,
      })
    })

    it('deduplicates repeated event frames while still updating counters', async () => {
      const frame = {
        type: 'loot',
        exploration_id: 'exploration-1',
        event: explorationEvent('loot', 'Found a stash'),
      }
      await emitSse(frame)
      await emitSse({ ...frame, total_caps_found: 55 })

      const updated = useExplorationStore().activeExplorations['exploration-1']
      expect(updated.events).toHaveLength(1)
      expect(updated.total_caps_found).toBe(55)
    })

    it('ignores per-event frames for unknown explorations', async () => {
      await emitSse({
        type: 'combat',
        exploration_id: 'unknown-exploration',
        event: explorationEvent('combat', 'Ghost'),
      })
      expect(useExplorationStore().pendingSseRewards).toBeNull()
    })
  })

  describe('SSE Equip Event', () => {
    const profileWithNotifications = (disabledCategories: string[]): UserProfile =>
      ({
        preferences: { notifications: { version: 1, disabled_categories: disabledCategories } },
      }) as UserProfile

    const equipFrame = {
      type: 'combat',
      exploration_id: 'exploration-1',
      dweller_id: 'dweller-1',
      event: explorationEvent('equip', 'Equipped a Hunting Rifle'),
    }

    beforeEach(() => {
      const store = useExplorationStore()
      store.explorations = [liveRun()]
      store.activeExplorations = { 'exploration-1': liveRun() }
      store.startSseSubscription('vault-1', 'test-token')
    })

    afterEach(() => {
      useExplorationStore().stopSseSubscription()
      mockSseEvent.value = null
    })

    it.each([
      ['shows', 'exploration_updates is enabled', [], true],
      ['does not toast', 'exploration_updates is disabled', ['exploration_updates'], false],
    ] as [string, string, string[], boolean][])(
      '%s an equip toast when %s',
      async (_, __, disabledCategories, expected) => {
        useProfileStore().profile = profileWithNotifications(disabledCategories)

        await emitSse(equipFrame)

        expect(toastShownFor('Amata Almodovar equipped a Hunting Rifle')).toBe(expected)
      }
    )

    it('refreshes dweller details on an equip event', async () => {
      await emitSse(equipFrame)
      expect(mockDwellerFilter.fetchDwellerDetails).toHaveBeenCalledWith('dweller-1', true)
    })

    it('does not refresh dweller details for a non-equip event', async () => {
      await emitSse({
        type: 'combat',
        exploration_id: 'exploration-1',
        dweller_id: 'dweller-1',
        event: explorationEvent('combat', 'Raider attacked'),
      })

      expect(mockDwellerFilter.fetchDwellerDetails).not.toHaveBeenCalled()
    })
  })

  describe('refreshActiveExplorations Action', () => {
    it('exposes the shared refresh cadence', () => {
      expect(ACTIVE_EXPLORATIONS_REFRESH_MS).toBe(15_000)
    })

    it('fetches the active list once and updates the active map', async () => {
      const store = useExplorationStore()
      const explorations = [
        mockExploration,
        run({ id: 'exploration-2', dweller_id: 'dweller-2', status: 'returning' }),
        run({ id: 'exploration-3', dweller_id: 'dweller-3', status: 'completed' }),
      ]
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce(explorations)

      const result = await store.refreshActiveExplorations('vault-1')
      expect(explorationApi.getExplorationsByVault).toHaveBeenCalledTimes(1)
      expect(explorationApi.getExplorationsByVault).toHaveBeenCalledWith('vault-1', true)
      expect(result).toEqual(explorations)
      expect(Object.keys(store.activeExplorations)).toEqual(['exploration-1', 'exploration-2'])
      expect(explorationApi.getExplorationParty).not.toHaveBeenCalled()
    })

    it('fetches parties only when includeParties is requested', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce([mockExploration])
      vi.mocked(explorationApi.getExplorationParty).mockResolvedValueOnce([])

      await store.refreshActiveExplorations('vault-1', { includeParties: true })
      expect(explorationApi.getExplorationParty).toHaveBeenCalledWith('vault-1', 'exploration-1')
      expect(store.explorationPartyMap).toEqual({ 'exploration-1': [] })
    })

    it('refreshes parties from the newly fetched active map', async () => {
      const store = useExplorationStore()
      store.activeExplorations = { 'stale-exploration': run({ id: 'stale-exploration' }) }
      vi.mocked(explorationApi.getExplorationsByVault).mockResolvedValueOnce([
        run(),
        run({ id: 'exploration-2', dweller_id: 'dweller-2' }),
      ])
      vi.mocked(explorationApi.getExplorationParty).mockResolvedValue([])

      await store.refreshActiveExplorations('vault-1', { includeParties: true })
      expect(explorationApi.getExplorationParty).toHaveBeenCalledTimes(2)
      expect(explorationApi.getExplorationParty).toHaveBeenCalledWith('vault-1', 'exploration-1')
      expect(explorationApi.getExplorationParty).toHaveBeenCalledWith('vault-1', 'exploration-2')
      expect(explorationApi.getExplorationParty).not.toHaveBeenCalledWith(
        'vault-1',
        'stale-exploration'
      )
    })

    it('surfaces loading and error state for an initial load', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockImplementationOnce(
        () => new Promise(() => undefined)
      )

      void store.refreshActiveExplorations('vault-1')
      expect(store.isLoading).toBe(true)
    })

    it('records the failure for an initial load and clears loading', async () => {
      const store = useExplorationStore()
      vi.mocked(explorationApi.getExplorationsByVault).mockRejectedValueOnce(
        new Error('Fetch failed')
      )

      await expect(store.refreshActiveExplorations('vault-1')).rejects.toThrow('Fetch failed')
      expect(store.error).toBe('Failed to fetch explorations')
      expect(store.isLoading).toBe(false)
    })

    it('stays silent for polling and skips parties on failure', async () => {
      const store = useExplorationStore()
      store.error = 'previous error'
      vi.mocked(explorationApi.getExplorationsByVault).mockRejectedValueOnce(
        new Error('Fetch failed')
      )

      await expect(store.refreshActiveExplorations('vault-1', { silent: true })).rejects.toThrow(
        'Fetch failed'
      )
      expect(store.error).toBe('previous error')
      expect(store.isLoading).toBe(false)
      expect(explorationApi.getExplorationParty).not.toHaveBeenCalled()
    })
  })

  describe('fetchPartiesForActiveExplorations Action', () => {
    it('collects one roster per active run and retains empty dispatch parties', async () => {
      const store = useExplorationStore()
      store.activeExplorations = {
        'exploration-1': run(),
        'exploration-2': run({ id: 'exploration-2' }),
      }
      vi.mocked(explorationApi.getExplorationParty)
        .mockResolvedValueOnce([
          {
            id: 'member-1',
            exploration_id: 'exploration-1',
            vault_id: 'vault-1',
            dweller_id: 'dweller-1',
            slot_number: 1,
            status: 'assigned',
            created_at: null,
            updated_at: null,
          },
        ])
        .mockResolvedValueOnce([])

      await store.fetchPartiesForActiveExplorations('vault-1')
      expect(explorationApi.getExplorationParty).toHaveBeenCalledWith('vault-1', 'exploration-1')
      expect(explorationApi.getExplorationParty).toHaveBeenCalledWith('vault-1', 'exploration-2')
      expect(store.explorationPartyMap['exploration-1']).toHaveLength(1)
      expect(store.explorationPartyMap['exploration-2']).toEqual([])
    })

    it('falls back to an empty roster when a party fetch fails', async () => {
      const store = useExplorationStore()
      store.activeExplorations = { 'exploration-1': run() }
      vi.mocked(explorationApi.getExplorationParty).mockRejectedValueOnce(new Error('network'))
      await store.fetchPartiesForActiveExplorations('vault-1')
      expect(store.explorationPartyMap).toEqual({ 'exploration-1': [] })
    })
  })
})
