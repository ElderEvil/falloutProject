import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useQuestStore } from '@/modules/progression/stores/quest'
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

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/quests/',
        expect.objectContaining({ headers: expect.any(Object) })
      )
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

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/quests/vault-123/',
        expect.objectContaining({ headers: expect.any(Object) })
      )
      expect(store.vaultQuests).toEqual(mockVaultQuests)
    })

    it('should handle fetch error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Vault not found'))

      const store = useQuestStore()
      await expect(store.fetchVaultQuests('vault-123')).rejects.toThrow('Vault not found')
      expect(store.isLoading).toBe(false)
    })

    it('keeps the cached list intact when the API payload is not a list', async () => {
      const store = useQuestStore()
      store.vaultQuests = [{ id: 'cached' } as VaultQuest]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { detail: 'Unexpected response' } })

      await expect(store.fetchVaultQuests('vault-123', { silent: true })).rejects.toThrow(
        'Expected a list of vault quests'
      )

      expect(store.vaultQuests).toEqual([{ id: 'cached' }])
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
      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/quests/vault-123/',
        expect.objectContaining({ headers: expect.any(Object) })
      )
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
        data: { quest_id: 'quest-1', quest_title: 'Quest 1', is_completed: true, granted_rewards: [] },
      })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [completedQuest] })

      const store = useQuestStore()
      await store.claimQuestRewards('vault-123', 'quest-1')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/quests/vault-123/quest-1/claim-rewards')
      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/quests/vault-123/',
        expect.objectContaining({ headers: expect.any(Object) })
      )
    })

    it('should handle reward claim error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Quest not found'))

      const store = useQuestStore()
      await expect(store.claimQuestRewards('vault-123', 'quest-1')).rejects.toThrow('Quest not found')
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
})
