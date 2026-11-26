import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { groupQuestsByType } from '@/modules/progression/models/quest'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useAuthStore } from '@/modules/auth/stores/auth'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

type VaultQuest = ReturnType<typeof useQuestStore>['vaultQuests'][number]

/** A vault quest; only the fields a test cares about need naming. */
const vaultQuest = (overrides: Record<string, unknown> = {}) =>
  ({
    id: '1',
    title: 'Quest 1',
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
    ...overrides,
  }) as VaultQuest

function deferred<T = unknown>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('Quest Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('starts idle with no quests', () => {
      const store = useQuestStore()
      expect(store.quests).toEqual([])
      expect(store.vaultQuests).toEqual([])
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
    it('should filter active and completed quests', () => {
      const store = useQuestStore()
      store.vaultQuests = [
        vaultQuest(),
        vaultQuest({ id: '2', title: 'Completed Quest', is_completed: true }),
      ]

      expect(store.questCategories.active.map((quest) => quest.id)).toEqual(['1'])
      expect(store.questCategories.completed.map((quest) => quest.id)).toEqual(['2'])
    })

    it('should filter available quests (not started)', () => {
      const store = useQuestStore()
      // availableQuests now filters from vaultQuests (not quests)
      store.vaultQuests = [
        vaultQuest({ title: 'Started Quest' }),
        vaultQuest({ id: '2', title: 'Available Quest', started_at: null, duration_minutes: null }),
      ]

      expect(store.questCategories.available.map((quest) => quest.id)).toEqual(['2'])
    })

    it('classifies a travelling quest into the returning bucket', () => {
      const store = useQuestStore()
      store.vaultQuests = [
        vaultQuest({
          title: 'Travelling Quest',
          is_reward_ready: false,
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: '2025-01-02T01:15:00Z',
        }),
      ]

      expect(store.questCategories.returning.map((quest) => quest.id)).toEqual(['1'])
      expect(store.questCategories.active).toHaveLength(0)
      expect(store.questCategories.readyToClaim).toHaveLength(0)
    })

    it('prefers the arrived and completed buckets over returning', () => {
      const store = useQuestStore()
      const returning = {
        is_reward_ready: false,
        return_started_at: '2025-01-02T01:00:00Z',
        return_completes_at: '2025-01-02T01:15:00Z',
      }
      store.vaultQuests = [
        vaultQuest({ ...returning, id: 'arrived', title: 'Arrived Quest', is_reward_ready: true }),
        vaultQuest({ ...returning, id: 'done', title: 'Done Quest', is_completed: true }),
      ]

      expect(store.questCategories.returning).toHaveLength(0)
      expect(store.questCategories.readyToClaim.map((quest) => quest.id)).toEqual(['arrived'])
      expect(store.questCategories.completed.map((quest) => quest.id)).toEqual(['done'])
    })
  })

  describe('fetchAllQuests', () => {
    it('should fetch all quests successfully', async () => {
      const mockQuests = [vaultQuest()]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockQuests })

      const store = useQuestStore()
      await store.fetchAllQuests()
      expect(axios.get).toHaveBeenCalledWith('/api/v1/quests/', { params: { limit: 1000 } })
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
    const questPage = (prefix: string, count: number) =>
      Array.from({ length: count }, (_, index) => ({ id: `${prefix}-${index}` }))

    it('should fetch vault quests successfully', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [vaultQuest()] })
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

    it('keeps the cached list intact when the API payload is not a list', async () => {
      const store = useQuestStore()
      store.vaultQuests = [{ id: 'cached' } as VaultQuest]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { detail: 'Unexpected response' } })

      await expect(store.fetchVaultQuests('vault-123', { silent: true })).rejects.toThrow(
        'Expected a list of vault quests'
      )
      expect(store.vaultQuests).toEqual([{ id: 'cached' }])
    })

    it('fetches the vault quest list in one request past row 100', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [...questPage('q', 150), { id: 'q-tail' }],
      })

      const store = useQuestStore()
      await store.fetchVaultQuests('vault-123')
      expect(store.vaultQuests).toHaveLength(151)
      expect(axios.get).toHaveBeenCalledTimes(1)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/quests/vault-123/', {
        params: { limit: 1000 },
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
      pending.resolve({ data: [vaultQuest()] })
      await call
      expect(store.vaultQuests).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })

  describe('assignQuest', () => {
    it('should assign quest and refresh vault quests', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: vaultQuest() })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [vaultQuest()] })

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
      vi.mocked(axios.post).mockResolvedValueOnce({
        data: {
          quest_id: 'quest-1',
          quest_title: 'Quest 1',
          is_completed: true,
          granted_rewards: [],
        },
      })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [vaultQuest({ id: 'quest-1', is_completed: true })],
      })

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
      const request = deferred<{ data: unknown }>()
      vi.mocked(axios.get).mockReturnValueOnce(request.promise as never)

      const store = useQuestStore()
      const fetchPromise = store.fetchAllQuests()
      expect(store.isLoading).toBe(true)
      request.resolve({ data: [] })
      await fetchPromise
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchPartiesForActiveQuests', () => {
    it('replaces stale rosters and retains empty active parties', async () => {
      const store = useQuestStore()
      store.vaultQuests = [vaultQuest({ id: 'active-quest', title: 'Active Quest' })]
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

    it("keeps the newest vault's party map when an older load resolves later", async () => {
      const store = useQuestStore()
      store.vaultQuests = [vaultQuest({ id: 'active-quest', title: 'Active Quest' })]
      const pending = deferred<{ data: unknown }>()
      vi.mocked(axios.get)
        .mockReturnValueOnce(pending.promise as never)
        .mockResolvedValueOnce({ data: [{ id: 'party-b', quest_id: 'active-quest' }] })

      const stale = store.fetchPartiesForActiveQuests('vault-a')
      await store.fetchPartiesForActiveQuests('vault-b')
      pending.resolve({ data: [{ id: 'party-a', quest_id: 'active-quest' }] })
      await stale
      expect(store.questPartyMap['active-quest']?.[0]?.id).toBe('party-b')
      expect(axios.get).toHaveBeenCalledTimes(2)
    })
  })
})

describe('groupQuestsByType', () => {
  const quest = (id: string, quest_type: string) => ({ id, quest_type }) as unknown as VaultQuest

  it('orders rotating groups first and groups main and side together', () => {
    const groups = groupQuestsByType([
      quest('side-1', 'side'),
      quest('daily-1', 'daily'),
      quest('event-1', 'event'),
      quest('weekly-1', 'repeatable'),
      quest('main-1', 'main'),
    ])

    expect(groups.map((group) => group.type)).toEqual(['daily', 'repeatable', 'event', 'other'])
    expect(groups.map((group) => group.label)).toEqual([
      'Daily quests',
      'Weekly quests',
      'Event quests',
      'Other quests',
    ])
    expect(groups[3].quests.map((entry) => entry.id)).toEqual(['side-1', 'main-1'])
  })

  it('labels repeatable as Weekly and omits empty groups', () => {
    const groups = groupQuestsByType([quest('weekly-1', 'repeatable')])
    expect(groups).toHaveLength(1)
    expect(groups[0].label).toBe('Weekly quests')
    expect(groups[0].quests.map((entry) => entry.id)).toEqual(['weekly-1'])
  })

  it('buckets unknown types into the other group', () => {
    const groups = groupQuestsByType([quest('odd-1', 'unknown-kind')])
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('other')
    expect(groups[0].quests.map((entry) => entry.id)).toEqual(['odd-1'])
  })
})
