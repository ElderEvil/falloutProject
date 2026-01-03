import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useQuestStore } from '@/stores/quest'
import axios from '@/plugins/axios'

vi.mock('@/plugins/axios')

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
          is_completed: false
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
          is_completed: true
        }
      ]

      expect(store.activeQuests).toHaveLength(1)
      expect(store.activeQuests[0].id).toBe('1')
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
          is_completed: false
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
          is_completed: true
        }
      ]

      expect(store.completedQuests).toHaveLength(1)
      expect(store.completedQuests[0].id).toBe('2')
    })

    it('should filter available quests (not assigned)', () => {
      const store = useQuestStore()
      store.quests = [
        {
          id: '1',
          title: 'Quest 1',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01'
        },
        {
          id: '2',
          title: 'Quest 2',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01'
        }
      ]
      store.vaultQuests = [
        {
          id: '1',
          title: 'Quest 1',
          short_description: 'Test',
          long_description: 'Test',
          requirements: 'Test',
          rewards: 'Test',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false
        }
      ]

      expect(store.availableQuests).toHaveLength(1)
      expect(store.availableQuests[0].id).toBe('2')
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
          updated_at: '2025-01-01'
        }
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
          is_completed: false
        }
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockVaultQuests })

      const store = useQuestStore()
      await store.fetchVaultQuests('vault-123')

      expect(axios.get).toHaveBeenCalledWith('/api/v1/quests/vault-123/')
      expect(store.vaultQuests).toEqual(mockVaultQuests)
    })

    it('should handle fetch error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Vault not found'))

      const store = useQuestStore()
      await expect(store.fetchVaultQuests('vault-123')).rejects.toThrow('Vault not found')
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
        is_completed: false
      }

      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockAssignedQuest })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [mockAssignedQuest] })

      const store = useQuestStore()
      await store.assignQuest('vault-123', 'quest-1', true)

      expect(axios.post).toHaveBeenCalledWith('/api/v1/quests/vault-123/quest-1/assign', null, {
        params: { is_visible: true }
      })
      expect(axios.get).toHaveBeenCalledWith('/api/v1/quests/vault-123/')
    })

    it('should handle assign error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Already assigned'))

      const store = useQuestStore()
      await expect(store.assignQuest('vault-123', 'quest-1')).rejects.toThrow('Already assigned')
    })
  })

  describe('completeQuest', () => {
    it('should complete quest and refresh vault quests', async () => {
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
        is_completed: true
      }

      vi.mocked(axios.post).mockResolvedValueOnce({ data: { success: true } })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [completedQuest] })

      const store = useQuestStore()
      await store.completeQuest('vault-123', 'quest-1')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/quests/vault-123/quest-1/complete')
      expect(axios.get).toHaveBeenCalledWith('/api/v1/quests/vault-123/')
    })

    it('should handle complete error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Quest not found'))

      const store = useQuestStore()
      await expect(store.completeQuest('vault-123', 'quest-1')).rejects.toThrow('Quest not found')
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
})
