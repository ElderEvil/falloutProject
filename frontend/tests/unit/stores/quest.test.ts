import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useAuthStore } from '@/modules/auth/stores/auth'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

describe('Quest Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('should have empty quests array', () => {
      const store = useQuestStore()
      expect(store.quests).toEqual([])
    })

    it('should have empty vaultQuests array', () => {
      const store = useQuestStore()
      expect(store.vaultQuests).toEqual([])
    })

    it('should not be loading', () => {
      const store = useQuestStore()
      expect(store.isLoading).toBe(false)
    })
  })

  it('sends the selected party with start in one mutation request', async () => {
    const store = useQuestStore()
    vi.mocked(axios.post).mockResolvedValue({ data: {} })
    vi.mocked(axios.get).mockResolvedValue({ data: [] })

    await store.startQuest('vault-1', 'quest-1', ['dweller-1', 'dweller-2'])

    expect(axios.post).toHaveBeenCalledExactlyOnceWith('/api/v1/quests/vault-1/quest-1/start', {
      dweller_ids: ['dweller-1', 'dweller-2'],
    })
  })

  describe('Computed Properties', () => {
    it('should filter active quests', () => {
      const store = useQuestStore()
      store.vaultQuests = [
        {
          id: '1',
          title: 'Active Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
        {
          id: '2',
          title: 'Completed Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: true,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      expect(store.questCategories.active).toHaveLength(1)
      expect(store.questCategories.active[0].id).toBe('1')
    })

    it('should filter completed quests', () => {
      const store = useQuestStore()
      store.vaultQuests = [
        {
          id: '1',
          title: 'Active Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
        {
          id: '2',
          title: 'Completed Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: true,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      expect(store.questCategories.completed).toHaveLength(1)
      expect(store.questCategories.completed[0].id).toBe('2')
    })

    it('should filter available quests (not started)', () => {
      const store = useQuestStore()
      // availableQuests now filters from vaultQuests (not quests)
      store.vaultQuests = [
        {
          id: '1',
          title: 'Started Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
        {
          id: '2',
          title: 'Available Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
      ]

      expect(store.questCategories.available).toHaveLength(1)
      expect(store.questCategories.available[0].id).toBe('2')
    })

    it('classifies a travelling quest into the returning bucket', () => {
      const store = useQuestStore()
      store.vaultQuests = [
        {
          id: '1',
          title: 'Travelling Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          is_reward_ready: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: '2025-01-02T01:15:00Z',
        },
      ]

      expect(store.questCategories.returning).toHaveLength(1)
      expect(store.questCategories.returning[0].id).toBe('1')
      expect(store.questCategories.active).toHaveLength(0)
      expect(store.questCategories.readyToClaim).toHaveLength(0)
    })

    it('prefers the arrived and completed buckets over returning', () => {
      const store = useQuestStore()
      store.vaultQuests = [
        {
          id: 'arrived',
          title: 'Arrived Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          is_reward_ready: true,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: '2025-01-02T01:15:00Z',
        },
        {
          id: 'done',
          title: 'Done Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: true,
          is_reward_ready: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: '2025-01-02T01:15:00Z',
        },
      ]

      expect(store.questCategories.returning).toHaveLength(0)
      expect(store.questCategories.readyToClaim.map((q) => q.id)).toEqual(['arrived'])
      expect(store.questCategories.completed.map((q) => q.id)).toEqual(['done'])
    })
  })

  describe('fetchAllQuests', () => {
    it('should fetch all quests successfully', async () => {
      const mockQuests = [
        {
          id: '1',
          title: 'Quest 1',
          short_description: 'Test 1',
          long_description: 'Test 1',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
        },
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockQuests })

      const store = useQuestStore()
      await store.fetchAllQuests()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/quests/')
      expect(store.quests).toEqual(mockQuests)
      expect(store.isLoading).toBe(false)
    })

    it('should handle fetch error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useQuestStore()
      await expect(store.fetchAllQuests()).rejects.toThrow('Network error')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchVaultQuests', () => {
    it('should fetch vault quests successfully', async () => {
      const mockVaultQuests = [
        {
          id: '1',
          title: 'Quest 1',
          short_description: 'Test 1',
          long_description: 'Test 1',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
        },
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVaultQuests })

      const store = useQuestStore()
      await store.fetchVaultQuests('vault-123')

      expect(store.vaultQuests).toMatchObject([{ id: '1', title: 'Quest 1' }])
    })

    it('should handle fetch error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Vault not found'))

      const store = useQuestStore()
      await expect(store.fetchVaultQuests('vault-123')).rejects.toThrow('Vault not found')
      expect(store.isLoading).toBe(false)
    })

    const questPage = (prefix: string, count: number) =>
      Array.from({ length: count }, (_, index) => ({ id: `${prefix}-${index}` }))

    it('keeps the cached list intact when a later page is not a list', async () => {
      const store = useQuestStore()
      store.vaultQuests = [{ id: 'cached' } as VaultQuest]
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: questPage('q', 100) })
        .mockResolvedValueOnce({ data: { detail: 'Unexpected response' } })

      await expect(store.fetchVaultQuests('vault-123', { silent: true })).rejects.toThrow(
        'Expected a list of vault quests'
      )

      // Page one is never published: the cached list survives the failed page two.
      expect(store.vaultQuests).toEqual([{ id: 'cached' }])
      expect(axios.get).toHaveBeenCalledTimes(2)
    })

    it('keeps fetching until the catalog is exhausted beyond row 100', async () => {
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: questPage('q', 100) })
        .mockResolvedValueOnce({ data: [{ id: 'q-tail' }] })

      const store = useQuestStore()
      await store.fetchVaultQuests('vault-123')

      expect(store.vaultQuests).toHaveLength(101)
      expect(store.vaultQuests.at(-1)?.id).toBe('q-tail')
      expect(axios.get).toHaveBeenCalledTimes(2)
      expect(axios.get).toHaveBeenNthCalledWith(2, '/api/v1/quests/vault-123/', {
        params: { skip: 100, limit: 100 },
      })
    })

    it("keeps the newest vault's quests when an older load resolves later", async () => {
      const newest = [{ id: 'b', title: 'Vault B Quest' }]
      const pending = deferred<{ data: unknown }>()
      vi.mocked(axios.get)
        .mockReturnValueOnce(pending.promise as never)
        .mockResolvedValueOnce({ data: newest })
      const store = useQuestStore()

      const first = store.fetchVaultQuests('vault-a')
      await store.fetchVaultQuests('vault-b')
      pending.resolve({ data: [{ id: 'a', title: 'Vault A Quest' }] })
      await first

      expect(store.vaultQuests).toMatchObject(newest)
    })

    it('discards a quest list that resolves after the session changed', async () => {
      const auth = useAuthStore()
      const pending = deferred<{ data: unknown }>()
      vi.mocked(axios.get).mockReturnValueOnce(pending.promise as never)
      const store = useQuestStore()

      const call = store.fetchVaultQuests('vault-123')
      auth.sessionGeneration += 1
      pending.resolve({ data: [{ id: '1', title: 'Quest 1' }] })
      await call

      expect(store.vaultQuests).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })

  describe('assignQuest', () => {
    it('should assign quest and refresh vault quests', async () => {
      const mockAssignedQuest = {
        id: '1',
        title: 'Quest 1',
        short_description: 'Test 1',
        long_description: 'Test 1',
        requirements: 'Level 5',
        rewards: '50 caps',
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
        is_visible: true,
        is_completed: false,
      }

      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockAssignedQuest })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [mockAssignedQuest] })

      const store = useQuestStore()
      await store.assignQuest('vault-123', 'quest-1', true)

      expect(axios.post).toHaveBeenCalledWith('/api/v1/quests/vault-123/quest-1/assign', null, {
        params: { is_visible: true },
      })
      expect(store.vaultQuests).toMatchObject([{ id: '1', title: 'Quest 1' }])
    })

    it('should handle assign error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Already assigned'))

      const store = useQuestStore()
      await expect(store.assignQuest('vault-123', 'quest-1')).rejects.toThrow('Already assigned')
    })
  })

  describe('claimQuestRewards', () => {
    it('should claim rewards and refresh vault quests', async () => {
      const completedQuest = {
        id: 'quest-1',
        title: 'Quest 1',
        short_description: 'Test 1',
        long_description: 'Test 1',
        requirements: 'Level 5',
        rewards: '50 caps',
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
        is_visible: true,
        is_completed: true,
      }

      vi.mocked(axios.post).mockResolvedValueOnce({
        data: {
          quest_id: 'quest-1',
          quest_title: 'Quest 1',
          is_completed: true,
          granted_rewards: [],
        },
      })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [completedQuest] })

      const store = useQuestStore()
      await store.claimQuestRewards('vault-123', 'quest-1')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/quests/vault-123/quest-1/claim-rewards')
      expect(store.vaultQuests).toMatchObject([{ id: 'quest-1', is_completed: true }])
    })

    it('should handle reward claim error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Quest not found'))

      const store = useQuestStore()
      await expect(store.claimQuestRewards('vault-123', 'quest-1')).rejects.toThrow(
        'Quest not found'
      )
    })
  })

  describe('Loading State', () => {
    it('should set loading state during fetch', async () => {
      let resolvePromise: (value: any) => void
      const promise = new Promise((resolve) => {
        resolvePromise = resolve
      })

      vi.mocked(axios.get).mockReturnValueOnce(promise as any)

      const store = useQuestStore()
      const fetchPromise = store.fetchAllQuests()

      expect(store.isLoading).toBe(true)

      resolvePromise!({ data: [] })
      await fetchPromise

      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchPartiesForActiveQuests', () => {
    it('replaces stale rosters and retains empty active parties', async () => {
      const store = useQuestStore()
      store.vaultQuests = [
        {
          id: 'active-quest',
          title: 'Active Quest',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]
      store.questPartyMap = {
        'completed-quest': [
          {
            id: 'party-1',
            quest_id: 'completed-quest',
            vault_id: 'vault-123',
            dweller_id: 'dweller-1',
            slot_number: 1,
            status: 'completed',
            created_at: '2025-01-01',
            updated_at: '2025-01-01',
          },
        ],
      }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [] })

      await store.fetchPartiesForActiveQuests('vault-123')

      expect(store.questPartyMap).toEqual({ 'active-quest': [] })
    })
  })

  function deferred<T>() {
    let resolve!: (value: T) => void
    let reject!: (reason?: unknown) => void
    const promise = new Promise<T>((res, rej) => {
      resolve = res
      reject = rej
    })
    return { promise, resolve, reject }
  }
})
