import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')
vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError: vi.fn(),
}))
vi.mock('@vueuse/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@vueuse/core')>()),
  useLocalStorage: <T>(key: string, defaultValue: T) => ref<T>(defaultValue),
}))

import {
  useDwellerFilterStore,
  ALL_DWELLERS_FETCH_LIMIT,
} from '@/modules/dwellers/stores/dwellerFilter'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { handleStoreError } from '@/core/utils/errorHandler'
import { DEFAULT_TABLE_COLUMNS } from '@/modules/dwellers/models/dwellerTable'
import type { DwellerTickSnapshot } from '@/modules/dwellers/models/dweller'

const UUID = '550e8400-e29b-41d4-a716-446655440000'

/** A roster row; only the fields a test cares about need naming. */
function dweller(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    first_name: id,
    last_name: 'Doe',
    status: 'idle',
    level: 1,
    happiness: 50,
    ...overrides,
  } as never
}

function roster(count: number, overrides: Record<string, unknown> = {}) {
  return Array.from({ length: count }, (_, index) => dweller(`d${index}`, overrides)) as never
}

function tickSnapshot(overrides: Partial<DwellerTickSnapshot> = {}): DwellerTickSnapshot {
  return {
    id: 'd1',
    health: 90,
    max_health: 100,
    radiation: 5,
    happiness: 80,
    level: 4,
    experience: 12,
    status: 'idle',
    room_id: null,
    is_dead: false,
    effective_max_health: 95,
    ...overrides,
  }
}

function deferred<T = unknown>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const ids = (rows: { id?: string }[]) => rows.map((row) => row.id)
const calledUrl = (index = 0) => vi.mocked(axios.get).mock.calls[index][0] as string

describe('DwellerFilter Store', () => {
  let store: ReturnType<typeof useDwellerFilterStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    store = useDwellerFilterStore()
    const flags = useFeatureFlagsStore()
    flags.raceMechanics = true
    // Faction narrows the roster only while its switch is on.
    flags.factionMechanics = true
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  describe('State', () => {
    it('should initialize with empty state and defaults', () => {
      expect(store.dwellers).toEqual([])
      expect(store.detailedDwellers).toEqual({})
      expect(store.isLoading).toBe(false)
      expect(store.filterStatus).toBe('all')
      expect(store.sortBy).toBe('name')
      expect(store.sortDirection).toBe('asc')
      expect(store.viewMode).toBe('list')
      expect(store.tableColumns).toEqual(DEFAULT_TABLE_COLUMNS)
    })
  })

  describe('identity filters', () => {
    it('passes race and faction to the backend and omits them when set to all', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] } as never)
      store.setFilterRace('ghoul')
      store.setFilterFaction('children_of_atom')
      await store.fetchDwellersByVault('vault-1', {
        race: store.filterRace,
        faction: store.filterFaction,
      })
      expect(calledUrl()).toBe(
        '/api/v1/dwellers/vault/vault-1/?race=ghoul&faction=children_of_atom'
      )
      store.setFilterRace('all')
      store.setFilterFaction('all')
      await store.fetchDwellersByVault('vault-1', {
        race: store.filterRace,
        faction: store.filterFaction,
      })
      expect(calledUrl(1)).toBe('/api/v1/dwellers/vault/vault-1/')
    })

    it('narrows the rendered roster by race and faction from visual_attributes', () => {
      store.dwellers = [
        dweller('g', { visual_attributes: { race: 'ghoul', faction: 'children_of_atom' } }),
        dweller('m', { visual_attributes: { race: 'super_mutant', faction: 'raiders' } }),
        dweller('n', { visual_attributes: null }),
      ]

      store.setFilterRace('ghoul')
      expect(ids(store.filteredAndSortedDwellers)).toEqual(['g'])
      store.setFilterRace('all')
      store.setFilterFaction('raiders')
      expect(ids(store.filteredAndSortedDwellers)).toEqual(['m'])
    })
  })

  describe('fetchDwellersByVault', () => {
    it('discards a roster response for a vault that is no longer active', async () => {
      useVaultStore().activeVaultId = 'vault-2'
      vi.mocked(axios.get).mockResolvedValue({ data: [dweller('v1-dweller')] } as never)
      store.dwellers = [dweller('v2-dweller')]

      await store.fetchDwellersByVault('vault-1')
      expect(store.dwellers).toEqual([dweller('v2-dweller')])
    })

    it('fetches the roster and leaves it empty when the request fails', async () => {
      const mockDwellers = [
        dweller('d1', { first_name: 'John', level: 5, happiness: 75 }),
        dweller('d2', { first_name: 'Jane', status: 'working', level: 3, happiness: 80 }),
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockDwellers })

      await store.fetchDwellersByVault('vault-1')
      expect(axios.get).toHaveBeenCalledWith('/api/v1/dwellers/vault/vault-1/')
      expect(store.dwellers).toEqual(mockDwellers)
      expect(store.isLoading).toBe(false)
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))
      await store.fetchDwellersByVault('vault-1')
      expect(store.isLoading).toBe(false)
    })

    it('keeps a cached detail in step with roster refreshes', async () => {
      store.detailedDwellers['d1'] = dweller('d1', {
        room_id: 'room-a',
        room: { id: 'room-a', name: 'Lobby' },
      })

      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [dweller('d1', { status: 'exploring', room_id: null })],
      })
      await store.fetchDwellersByVault('vault-1')
      expect(store.detailedDwellers['d1']).toMatchObject({
        status: 'exploring',
        room: null,
        room_id: null,
      })
      // Room B is not loaded: room_id must move and the stale room A must not linger.
      store.detailedDwellers['d1'] = dweller('d1', {
        room_id: 'room-a',
        room: { id: 'room-a', name: 'Lobby' },
      })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [dweller('d1', { room_id: 'room-b' })],
      })
      await store.fetchDwellersByVault('vault-1')
      expect(store.detailedDwellers['d1']).toMatchObject({ room_id: 'room-b', room: null })
      // A later refresh clears the assignment; the guard must not skip it just
      // because both resolved rooms are null.
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [dweller('d1', { room_id: null })] })
      await store.fetchDwellersByVault('vault-1')
      expect(store.detailedDwellers['d1']).toMatchObject({ room_id: null, room: null })
    })

    it('passes filter parameters as a query string and omits default values', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      await store.fetchDwellersByVault('vault-1', {
        status: 'working',
        sortBy: 'level',
        order: 'desc',
        limit: 20,
      })
      const url = calledUrl()
      expect(url).toContain('status=working')
      expect(url).toContain('sort_by=level')
      expect(url).toContain('order=desc')
      expect(url).toContain('limit=20')
      await store.fetchDwellersByVault('vault-1', { status: 'all', ageGroup: 'all' })
      expect(calledUrl(1)).not.toContain('status=')
      expect(calledUrl(1)).not.toContain('age_group=')
    })

    it('should ignore a stale response after filter inputs change', async () => {
      const first = deferred<{ data: unknown }>()
      const freshData = [dweller('working', { first_name: 'Fresh', status: 'working' })]
      vi.mocked(axios.get)
        .mockReturnValueOnce(first.promise as never)
        .mockResolvedValueOnce({ data: freshData })

      const firstRequest = store.fetchDwellersByVault('vault-1', { status: 'idle' })
      const secondRequest = store.fetchDwellersByVault('vault-1', { status: 'working' })
      await secondRequest
      expect(store.dwellers).toEqual(freshData)
      first.resolve({ data: [dweller('idle', { first_name: 'Stale' })] })
      await firstRequest
      expect(store.dwellers).toEqual(freshData)
    })
  })

  describe('fetchAllDwellers', () => {
    it('rejects an off-vault roster read before it clears the loaded roster', async () => {
      useVaultStore().activeVaultId = 'vault-b'
      const local = [dweller('local', { room_id: 'room-b', status: 'working' })]
      store.allDwellers = local
      store.allDwellersLoadedVaultId = 'vault-b'

      await store.fetchAllDwellers('vault-a')
      expect(vi.mocked(axios.get)).not.toHaveBeenCalled()
      expect(store.allDwellersLoadedVaultId).toBe('vault-b')
      expect(store.allDwellers).toEqual(local)
    })

    it('accepts the filtered response after access-token rotation in the same session', async () => {
      const auth = useAuthStore()
      auth.token = 'token-a'
      const { promise, resolve } = Promise.withResolvers<{ data: unknown[] }>()
      vi.mocked(axios.get).mockReturnValueOnce(promise)
      const pending = store.fetchDwellersByVault('vault-1', 'token-a')
      auth.token = 'refreshed-token'
      resolve({ data: [{ id: 'current' }] })
      await pending
      expect(ids(store.dwellers)).toEqual(['current'])
    })

    it('clears the filtered roster and ignores a pending response after a session change', async () => {
      const auth = useAuthStore()
      auth.token = 'token-a'
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [{ id: 'private' }] })
      await store.fetchDwellersByVault('vault-1', 'token-a')
      const { promise, resolve } = Promise.withResolvers<{ data: unknown[] }>()
      vi.mocked(axios.get).mockReturnValueOnce(promise)
      const pending = store.fetchDwellersByVault('vault-1', 'token-a')
      auth.sessionGeneration++
      expect(store.dwellers).toEqual([])
      resolve({ data: [{ id: 'obsolete' }] })
      await pending
      expect(store.dwellers).toEqual([])
    })

    it.each([false, true])(
      'keeps each caller error policy when the first strict flag is %s',
      async (firstStrict) => {
        const failure = new Error('Roster unavailable')
        const pending = deferred<{ data: unknown }>()
        vi.mocked(axios.get).mockReturnValueOnce(pending.promise as never)
        const first = store.fetchAllDwellers('vault-1', firstStrict)
        const second = store.fetchAllDwellers('vault-1', !firstStrict)
        const results = Promise.allSettled([first, second])
        pending.reject(failure)
        const settled = await results
        expect(settled.map((result) => result.status)).toEqual(
          firstStrict ? ['rejected', 'fulfilled'] : ['fulfilled', 'rejected']
        )
        expect(axios.get).toHaveBeenCalledTimes(1)
        expect(handleStoreError).toHaveBeenCalledTimes(1)
      }
    )

    it('lets a fresh same-vault load supersede an older shared request', async () => {
      const old = deferred<{ data: unknown }>()
      vi.mocked(axios.get)
        .mockReturnValueOnce(old.promise as never)
        .mockResolvedValueOnce({ data: [{ id: 'fresh' }] })
      const oldRequest = store.fetchAllDwellers('vault-1')
      const fresh = store.fetchAllDwellers('vault-1', false, true)
      old.resolve({ data: [{ id: 'stale' }] })
      await Promise.all([oldRequest, fresh])
      expect(axios.get).toHaveBeenCalledTimes(2)
      expect(ids(store.allDwellers)).toEqual(['fresh'])
    })

    it('does not share a pending roster across sessions', async () => {
      const old = deferred<{ data: unknown }>()
      vi.mocked(axios.get)
        .mockReturnValueOnce(old.promise as never)
        .mockResolvedValueOnce({ data: [{ id: 'current-account' }] })
      const auth = useAuthStore()
      const oldRequest = store.fetchAllDwellers('vault-1')
      auth.sessionGeneration += 1
      const current = store.fetchAllDwellers('vault-1')
      old.resolve({ data: [{ id: 'previous-account' }] })
      await Promise.all([oldRequest, current])
      expect(axios.get).toHaveBeenCalledTimes(2)
      expect(ids(store.allDwellers)).toEqual(['current-account'])
    })

    it('clears the loaded marker and rejects stale strict loads after logout', async () => {
      const auth = useAuthStore()
      vi.mocked(axios.get).mockResolvedValueOnce({ data: [{ id: 'private' }] })
      await store.fetchAllDwellers('vault-1')
      const pending = deferred<{ data: unknown }>()
      vi.mocked(axios.get).mockReturnValueOnce(pending.promise as never)
      const request = store.fetchAllDwellers('vault-1', true)
      const settled = Promise.allSettled([request])
      auth.sessionGeneration += 1
      pending.resolve({ data: [{ id: 'private' }] })
      expect((await settled)[0].status).toBe('rejected')
      expect(store.allDwellers).toEqual([])
      expect(store.allDwellersLoadedVaultId).toBeNull()
    })

    it('requests complete pages from skip=0 until a short page arrives', async () => {
      const mockDwellers = [dweller('d1', { first_name: 'John' })]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockDwellers })

      await store.fetchAllDwellers('vault-1')
      const url = calledUrl()
      expect(url).toContain('/api/v1/dwellers/vault/vault-1/')
      expect(url).toContain('skip=0')
      expect(url).toContain(`limit=${ALL_DWELLERS_FETCH_LIMIT}`)
      expect(store.allDwellers).toEqual(mockDwellers)

      const fullPage = roster(ALL_DWELLERS_FETCH_LIMIT)
      const tail = [dweller('tail', { first_name: 'Last' })]
      vi.mocked(axios.get)
        .mockReset()
        .mockResolvedValueOnce({ data: fullPage })
        .mockResolvedValueOnce({ data: tail })
      await store.fetchAllDwellers('vault-1')
      expect(vi.mocked(axios.get)).toHaveBeenCalledTimes(2)
      expect(calledUrl(1)).toContain(`skip=${ALL_DWELLERS_FETCH_LIMIT}`)
      expect(store.allDwellers).toHaveLength(ALL_DWELLERS_FETCH_LIMIT + 1)
      expect(store.allDwellers.at(-1)).toEqual(tail[0])
    })

    it('should clear allDwellers before loading', async () => {
      const request = deferred<{ data: unknown }>()
      vi.mocked(axios.get).mockReturnValueOnce(request.promise as never)

      // Seed with stale data from a previous vault
      store.allDwellers = [dweller('old', { first_name: 'Old' })]
      const promise = store.fetchAllDwellers('vault-1')
      // Cleared before the response resolves
      expect(store.allDwellers).toEqual([])
      request.resolve({ data: [dweller('new', { first_name: 'New' })] })
      await promise
      expect(ids(store.allDwellers)).toEqual(['new'])
    })

    it('keeps the loaded roster visible while a same-vault refresh is in flight', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      const request = deferred<{ data: unknown }>()
      vi.mocked(axios.get).mockReturnValueOnce(request.promise as never)
      store.allDwellers = [dweller('d1', { room_id: 'room-1' })]
      store.allDwellersLoadedVaultId = 'vault-1'

      const pending = store.fetchAllDwellers('vault-1', false, true)
      expect(store.allDwellers).toEqual([dweller('d1', { room_id: 'room-1' })])
      expect(store.allDwellersLoadedVaultId).toBe('vault-1')
      request.resolve({ data: [{ id: 'd1', room_id: 'room-2' }] })
      await pending
      expect(store.allDwellers).toEqual([{ id: 'd1', room_id: 'room-2' }])
    })

    it('shares one request between concurrent same-vault loads', async () => {
      const request = deferred<{ data: unknown }>()
      const data = [dweller('shared', { first_name: 'Shared' })]
      vi.mocked(axios.get).mockReturnValueOnce(request.promise as never)

      const firstPromise = store.fetchAllDwellers('vault-1', true)
      const secondPromise = store.fetchAllDwellers('vault-1', true)
      request.resolve({ data })
      await Promise.all([firstPromise, secondPromise])
      expect(vi.mocked(axios.get)).toHaveBeenCalledTimes(1)
      expect(store.allDwellers).toEqual(data)
    })

    it('should ignore a response for a different vault than the current one', async () => {
      const first = deferred<{ data: unknown }>()
      const vault2Data = [dweller('v2', { first_name: 'Vault2' })]
      vi.mocked(axios.get)
        .mockReturnValueOnce(first.promise as never)
        .mockResolvedValueOnce({ data: vault2Data })

      const vault1Promise = store.fetchAllDwellers('vault-1')
      const vault2Promise = store.fetchAllDwellers('vault-2')
      await vault2Promise
      expect(store.allDwellers).toEqual(vault2Data)
      // Vault-1 response arrives late; must not overwrite vault-2 data
      first.resolve({ data: [dweller('v1', { first_name: 'Vault1' })] })
      await vault1Promise
      expect(store.allDwellers).toEqual(vault2Data)
    })

    it('should preserve cleared state when the request fails', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      store.allDwellers = [dweller('old', { first_name: 'Old' })]
      await store.fetchAllDwellers('vault-1')
      // Cleared state preserved — stale data not restored on failure
      expect(store.allDwellers).toEqual([])
    })
  })

  describe('fetchDwellerDetails', () => {
    it("does not reuse a previous account's cached dweller", async () => {
      const authStore = useAuthStore()
      authStore.user = { id: 'user-a', username: 'Alice' }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: UUID, first_name: 'Private' } })
      await store.fetchDwellerDetails(UUID)

      authStore.user = { id: 'user-b', username: 'Bob' }
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Forbidden'))
      const result = await store.fetchDwellerDetails(UUID)
      expect(result).toBeNull()
      expect(store.detailedDwellers[UUID]).toBeUndefined()
      expect(axios.get).toHaveBeenCalledTimes(2)
    })

    it('discards a detail request that finishes after the account changes', async () => {
      const authStore = useAuthStore()
      const request = deferred<{ data: { id: string; first_name: string } }>()
      vi.mocked(axios.get).mockReturnValueOnce(request.promise as never)

      authStore.user = { id: 'user-a', username: 'Alice' }
      const pending = store.fetchDwellerDetails(UUID)
      authStore.user = { id: 'user-b', username: 'Bob' }
      request.resolve({ data: { id: UUID, first_name: 'Private' } })
      expect(await pending).toBeNull()
      expect(store.detailedDwellers[UUID]).toBeUndefined()
    })

    it('caches a dweller detail, serves it from cache, and refetches when forced', async () => {
      const mockDweller = { id: 'd1', first_name: 'John', last_name: 'Doe', strength: 5 }
      vi.mocked(axios.get).mockResolvedValue({ data: mockDweller })

      const result = await store.fetchDwellerDetails(UUID)
      expect(result).toEqual(mockDweller)
      expect(store.detailedDwellers[UUID]).toEqual(mockDweller)

      vi.mocked(axios.get).mockClear()
      const cached = await store.fetchDwellerDetails(UUID)
      expect(axios.get).not.toHaveBeenCalled()
      expect(cached).toEqual(mockDweller)

      await store.fetchDwellerDetails(UUID, true)
      expect(axios.get).toHaveBeenCalledTimes(1)
    })

    it('should return null for invalid UUID', async () => {
      const result = await store.fetchDwellerDetails('not-a-uuid')
      expect(result).toBeNull()
      expect(axios.get).not.toHaveBeenCalled()
    })
  })

  describe('filteredAndSortedDwellers', () => {
    it('returns the whole roster for all and narrows it by status otherwise', () => {
      store.dwellers = [
        dweller('d1', { first_name: 'A' }),
        dweller('d2', { first_name: 'B', status: 'working' }),
      ]
      expect(store.filteredAndSortedDwellers).toHaveLength(2)

      store.filterStatus = 'working'
      expect(ids(store.filteredAndSortedDwellers)).toEqual(['d2'])
    })

    it.each([
      [
        'name ascending',
        'name',
        'asc',
        [dweller('d1', { first_name: 'B' }), dweller('d2', { first_name: 'A' })],
        ['d2', 'd1'],
      ],
      [
        'name descending',
        'name',
        'desc',
        [dweller('d1', { first_name: 'A' }), dweller('d2', { first_name: 'B' })],
        ['d2', 'd1'],
      ],
      [
        'level numerically',
        'level',
        'asc',
        [dweller('d1', { level: 10 }), dweller('d2', { level: 1 })],
        ['d2', 'd1'],
      ],
      [
        'happiness',
        'happiness',
        'asc',
        [dweller('d1', { happiness: 50 }), dweller('d2', { happiness: 80 })],
        ['d1', 'd2'],
      ],
    ] as [string, string, 'asc' | 'desc', never, string[]][])(
      'should sort by %s',
      (_, sortBy, direction, rows, expected) => {
        store.dwellers = rows
        store.sortBy = sortBy as typeof store.sortBy
        store.sortDirection = direction

        expect(ids(store.filteredAndSortedDwellers)).toEqual(expected)
      }
    )

    it('sorts Needs Care by health percentage, not raw health, breaking ties by id', () => {
      store.dwellers = [
        dweller('low-percent', { health: 100, max_health: 500, radiation: 0 }),
        dweller('mid-percent', { health: 30, max_health: 100, radiation: 0 }),
        dweller('high-percent', { health: 24, max_health: 50, radiation: 0 }),
      ]
      store.filterFocus = 'needs_care'
      store.sortBy = 'health'
      store.sortDirection = 'asc'

      expect(ids(store.filteredAndSortedDwellers)).toEqual([
        'low-percent',
        'mid-percent',
        'high-percent',
      ])

      store.dwellers = [
        dweller('tie-b', { health: 40, max_health: 100, radiation: 0 }),
        dweller('tie-a', { health: 40, max_health: 100, radiation: 0 }),
      ]
      expect(ids(store.filteredAndSortedDwellers)).toEqual(['tie-a', 'tie-b'])
    })

    it('treats a missing stat as zero rather than comparing as NaN', () => {
      store.dwellers = [dweller('has', { strength: 5 }), dweller('missing')]
      store.setSortBy('strength')
      store.setSortDirection('asc')
      expect(ids(store.filteredAndSortedDwellers)).toEqual(['missing', 'has'])
    })
  })

  describe('countByStatus', () => {
    const rosterWithFacets = [
      { id: '1', status: 'idle', age_group: 'adult', race: 'ghoul', faction: 'children_of_atom' },
      { id: '2', status: 'idle', age_group: 'child', race: 'ghoul', faction: 'children_of_atom' },
      { id: '3', status: 'working', age_group: 'adult', race: 'human', faction: 'vault_dweller' },
      { id: '4', status: 'dead', age_group: 'adult', race: 'ghoul', faction: 'children_of_atom' },
    ].map((row) => ({
      id: row.id,
      status: row.status,
      age_group: row.age_group,
      visual_attributes: { race: row.race, faction: row.faction },
    })) as never

    it('counts every status from allDwellers, not the status-narrowed roster', () => {
      store.allDwellers = rosterWithFacets
      store.dwellers = [{ id: 'only-idle', status: 'idle' }] as never
      store.filterStatus = 'idle'

      const { all, byStatus } = store.countByStatus({
        ageGroup: 'all',
        race: 'all',
        faction: 'all',
      })
      expect(all).toBe(4)
      expect(byStatus).toMatchObject({ idle: 2, working: 1, dead: 1, questing: 0 })
    })

    it('narrows counts by the non-status filters it is given', () => {
      store.allDwellers = rosterWithFacets

      const { all, byStatus } = store.countByStatus({
        ageGroup: 'adult',
        race: 'ghoul',
        faction: 'all',
      })
      expect(all).toBe(2)
      expect(byStatus).toMatchObject({ idle: 1, dead: 1, working: 0 })
    })

    it('ignores a faction filter while the faction switch is off', () => {
      useFeatureFlagsStore().factionMechanics = false
      store.allDwellers = rosterWithFacets

      const { all } = store.countByStatus({
        ageGroup: 'all',
        race: 'all',
        faction: 'children_of_atom',
      })
      expect(all).toBe(4)
    })
  })

  describe('facet counts', () => {
    const facetRoster = [
      { id: '1', status: 'idle', age_group: 'adult', gender: 'male', rarity: 'common' },
      { id: '2', status: 'working', age_group: 'adult', gender: 'female', rarity: 'legendary' },
      { id: '3', status: 'idle', age_group: 'child', gender: 'male', rarity: 'common' },
    ].map((row, index) => ({
      ...row,
      visual_attributes:
        index === 1
          ? { race: 'human', faction: 'vault_dweller' }
          : { race: 'ghoul', faction: 'children_of_atom' },
    })) as never

    const all = {
      status: 'all',
      ageGroup: 'all',
      gender: 'all',
      rarity: 'all',
      race: 'all',
      faction: 'all',
    }

    it('counts every gender, rarity and race from allDwellers', () => {
      store.allDwellers = facetRoster

      const genders = store.countByGender({ ...all })
      expect(genders.all).toBe(3)
      expect(genders.byGender).toMatchObject({ male: 2, female: 1 })
      const rarities = store.countByRarity({ ...all })
      expect(rarities.all).toBe(3)
      expect(rarities.byRarity).toMatchObject({ common: 2, legendary: 1, rare: 0 })
      const races = store.countByRace({ ...all })
      expect(races.all).toBe(3)
      expect(races.byRace).toMatchObject({ ghoul: 2, human: 1, super_mutant: 0, synth: 0 })
    })

    it('respects the status and age facets while ignoring each facet itself', () => {
      store.allDwellers = facetRoster

      const genders = store.countByGender({ ...all, status: 'idle', ageGroup: 'adult' })
      expect(genders.all).toBe(1)
      expect(genders.byGender).toMatchObject({ male: 1, female: 0 })
      const rarities = store.countByRarity({ ...all, status: 'idle', ageGroup: 'adult' })
      expect(rarities.byRarity).toMatchObject({ common: 1, legendary: 0 })
      const races = store.countByRace({ ...all, status: 'idle', ageGroup: 'adult' })
      expect(races.byRace).toMatchObject({ ghoul: 1, human: 0 })
    })
  })

  describe('lookups', () => {
    it('should return status for existing dweller and null for a missing one', () => {
      store.dwellers = [{ id: 'd1', status: 'working' } as never]
      expect(store.getDwellerStatus('d1')).toBe('working')
      expect(store.getDwellerStatus('nonexistent')).toBeNull()
    })

    it('should filter dwellers by status', () => {
      store.dwellers = [
        { id: 'd1', status: 'idle' },
        { id: 'd2', status: 'working' },
        { id: 'd3', status: 'idle' },
      ] as never

      expect(store.getDwellersByStatus('idle')).toHaveLength(2)
    })
  })

  describe('Setters', () => {
    it('drops the facet filters when the status becomes dead', () => {
      store.setFilterAgeGroup('adult')
      store.setFilterGender('male')
      store.setFilterRarity('legendary')
      store.setFilterRace('ghoul')
      store.setFilterFaction('children_of_atom')

      store.setFilterStatus('dead')
      expect(store.filterAgeGroup).toBe('all')
      expect(store.filterGender).toBe('all')
      expect(store.filterRarity).toBe('all')
      expect(store.filterRace).toBe('all')
      expect(store.filterFaction).toBe('all')
    })

    it.each([
      ['setFilterStatus', 'filterStatus', 'working'],
      ['setFilterAgeGroup', 'filterAgeGroup', 'adult'],
      ['setFilterRarity', 'filterRarity', 'rare'],
      ['setSortBy', 'sortBy', 'level'],
      ['setSortDirection', 'sortDirection', 'desc'],
      ['setViewMode', 'viewMode', 'grid'],
    ] as const)('%s updates %s', (setter, field, value) => {
      store[setter](value as never)
      expect(store[field]).toBe(value)
    })

    it('setViewMode accepts the table mode', () => {
      store.setViewMode('table')
      expect(store.viewMode).toBe('table')
    })

    it('toggles columns in catalog order and never hides the last one', () => {
      expect(store.tableColumns).not.toContain('rarity')

      store.toggleTableColumn('rarity')
      expect(store.tableColumns).toContain('rarity')
      store.toggleTableColumn('level')
      expect(store.tableColumns).not.toContain('level')
      store.toggleTableColumn('gender')
      expect(store.tableColumns.indexOf('rarity')).toBeLessThan(
        store.tableColumns.indexOf('gender')
      )
      for (const id of [...store.tableColumns]) store.toggleTableColumn(id)
      expect(store.tableColumns.length).toBeGreaterThan(0)
    })

    it('applyTablePreset replaces the visible columns and resetTableColumns restores defaults', () => {
      store.applyTablePreset('vitals')
      expect(store.tableColumns).toEqual(['portrait', 'name', 'status', 'health', 'happiness'])
      store.resetTableColumns()
      expect(store.tableColumns).toEqual(DEFAULT_TABLE_COLUMNS)
    })

    it('ignores an unknown preset', () => {
      const before = [...store.tableColumns]
      store.applyTablePreset('does-not-exist')
      expect(store.tableColumns).toEqual(before)
    })
  })

  describe('applyDwellerTick', () => {
    const rosterEntry = {
      id: 'd1',
      first_name: 'John',
      last_name: 'Doe',
      health: 10,
      max_health: 100,
      radiation: 0,
      happiness: 50,
      level: 1,
      experience: 0,
      status: 'idle',
      room_id: null,
      visual_attributes: { race: 'human' },
    }

    it('patches every cache while preserving immutable roster fields', () => {
      useVaultStore().activeVaultId = 'vault-1'
      store.dwellers = [{ ...rosterEntry }] as never
      store.allDwellers = [{ ...rosterEntry }] as never
      store.allDwellersLoadedVaultId = 'vault-1'
      store.detailedDwellers = { d1: { ...rosterEntry, room: null } as never }

      store.applyDwellerTick(
        'vault-1',
        [tickSnapshot({ health: 90, level: 4, experience: 12, status: 'working' })],
        'token'
      )
      const patched = {
        health: 90,
        max_health: 100,
        radiation: 5,
        happiness: 80,
        level: 4,
        experience: 12,
        status: 'working',
        effective_max_health: 95,
        first_name: 'John',
        visual_attributes: { race: 'human' },
      }
      for (const list of [store.dwellers, store.allDwellers]) {
        expect(list[0]).toMatchObject(patched)
      }
      expect(store.detailedDwellers.d1).toMatchObject(patched)
    })

    it('resolves the detail room from the room store and clears it on a null room_id', () => {
      useVaultStore().activeVaultId = 'vault-1'
      const roomStore = useRoomStore()
      roomStore.rooms = [{ id: 'room-1', name: 'Power Plant' }] as never
      store.detailedDwellers = {
        d1: { id: 'd1', first_name: 'John', room: { id: 'old', name: 'Old' } } as never,
      }

      store.applyDwellerTick('vault-1', [tickSnapshot({ room_id: 'room-1' })], 'token')
      expect(store.detailedDwellers.d1?.room).toEqual(roomStore.rooms[0])
      store.applyDwellerTick('vault-1', [tickSnapshot({ room_id: null })], 'token')
      expect(store.detailedDwellers.d1?.room).toBeNull()
    })

    it('ignores a tick for a vault that is not active', () => {
      useVaultStore().activeVaultId = 'vault-2'
      store.dwellers = [{ id: 'd1', health: 10 }] as never
      store.allDwellers = [{ id: 'd1', health: 10 }] as never
      store.allDwellersLoadedVaultId = 'vault-1'
      store.detailedDwellers = { d1: { id: 'd1', health: 10 } as never }

      store.applyDwellerTick('vault-1', [tickSnapshot({ health: 90 })], 'token')
      expect(store.dwellers[0]).toMatchObject({ health: 10 })
      expect(store.allDwellers[0]).toMatchObject({ health: 10 })
      expect(store.detailedDwellers.d1).toMatchObject({ health: 10 })
    })

    it('patches only the filtered page before the full roster loads', () => {
      useVaultStore().activeVaultId = 'vault-1'
      store.dwellers = [
        { id: 'd1', health: 10 },
        { id: 'd2', health: 10 },
      ] as never
      store.allDwellers = [{ id: 'd1', health: 10 }] as never
      store.allDwellersLoadedVaultId = null

      store.applyDwellerTick(
        'vault-1',
        [tickSnapshot({ id: 'd1' }), tickSnapshot({ id: 'new', health: 40 })],
        'token'
      )
      expect(ids(store.dwellers)).toEqual(['d1', 'd2'])
      expect(store.dwellers[0]).toMatchObject({ health: 90 })
      expect(store.dwellers[1]).toMatchObject({ health: 10 })
      expect(ids(store.allDwellers)).toEqual(['d1'])
      expect(store.allDwellers[0]).toMatchObject({ health: 10 })
      expect(vi.mocked(axios.get)).not.toHaveBeenCalled()
    })

    it('drops ids absent from the snapshot from every cache when the roster is loaded', () => {
      useVaultStore().activeVaultId = 'vault-1'
      store.dwellers = [{ id: 'd1' }, { id: 'gone' }] as never
      store.allDwellers = [{ id: 'd1' }, { id: 'gone' }] as never
      store.allDwellersLoadedVaultId = 'vault-1'
      store.detailedDwellers = { d1: { id: 'd1' } as never, gone: { id: 'gone' } as never }

      store.applyDwellerTick('vault-1', [tickSnapshot({ id: 'd1' })], 'token')
      expect(ids(store.dwellers)).toEqual(['d1'])
      expect(ids(store.allDwellers)).toEqual(['d1'])
      expect(store.detailedDwellers.gone).toBeUndefined()
      expect(store.detailedDwellers.d1).toBeDefined()
    })

    it('refreshes both lists once when a tick adds an id, sharing the roster fetch', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      const rosterRequest = deferred<unknown>()
      vi.mocked(axios.get).mockImplementation(((url: string) =>
        String(url).includes('limit=1000')
          ? rosterRequest.promise
          : Promise.resolve({ data: [] })) as never)
      store.dwellers = [{ id: 'd1' }] as never
      store.allDwellers = [{ id: 'd1' }] as never
      store.allDwellersLoadedVaultId = 'vault-1'
      const rosterCalls = () =>
        vi.mocked(axios.get).mock.calls.filter(([url]) => String(url).includes('limit=1000'))
      const tickWithNewId = () =>
        store.applyDwellerTick(
          'vault-1',
          [tickSnapshot({ id: 'd1' }), tickSnapshot({ id: 'new' })],
          'token'
        )

      tickWithNewId()
      await vi.waitFor(() => expect(vi.mocked(axios.get)).toHaveBeenCalledTimes(2))
      const urls = vi.mocked(axios.get).mock.calls.map((call) => call[0] as string)
      expect(urls.some((url) => url.includes('limit='))).toBe(true)
      expect(urls.some((url) => !url.includes('limit='))).toBe(true)
      expect(store.detailedDwellers.new).toBeUndefined()
      expect(rosterCalls()).toHaveLength(1)
      tickWithNewId()
      expect(rosterCalls()).toHaveLength(1)
      rosterRequest.resolve({ data: [{ id: 'd1' }, { id: 'new' }] })
      await vi.waitFor(() => expect(ids(store.allDwellers)).toEqual(['d1', 'new']))
    })

    it('reapplies a tick that lands during an ordinary filtered fetch', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      const page = deferred<unknown>()
      vi.mocked(axios.get).mockReturnValueOnce(page.promise as never)
      store.dwellers = [{ id: 'd1', health: 10 }] as never

      const request = store.fetchDwellersByVault('vault-1')
      store.applyDwellerTick('vault-1', [tickSnapshot({ id: 'd1', health: 30 })], 'token')
      page.resolve({ data: [{ id: 'd1', first_name: 'John', health: 10 }] })
      await request
      expect(store.dwellers[0]).toMatchObject({ health: 30 })
    })

    it('removes a dweller restored by an older full-roster response', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      const all = deferred<unknown>()
      vi.mocked(axios.get).mockReturnValueOnce(all.promise as never)
      store.allDwellers = [{ id: 'd1' }, { id: 'd2' }] as never
      store.allDwellersLoadedVaultId = 'vault-1'

      const request = store.fetchAllDwellers('vault-1', false, true)
      store.applyDwellerTick('vault-1', [tickSnapshot({ id: 'd1' })], 'token')
      all.resolve({
        data: [
          { id: 'd1', first_name: 'A' },
          { id: 'd2', first_name: 'B' },
        ],
      })
      await request
      expect(ids(store.allDwellers)).toEqual(['d1'])
    })

    it('refreshes the filtered page when a tick changes filter membership', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      vi.mocked(axios.get).mockResolvedValue({ data: [{ id: 'd1', status: 'working' }] } as never)
      store.filterStatus = 'idle'
      store.dwellers = [{ id: 'd1', status: 'idle', health: 100 }] as never
      store.allDwellers = [{ id: 'd1', status: 'idle' }] as never
      store.allDwellersLoadedVaultId = 'vault-1'

      store.applyDwellerTick('vault-1', [tickSnapshot({ id: 'd1', status: 'working' })], 'token')
      await vi.waitFor(() => expect(vi.mocked(axios.get)).toHaveBeenCalledTimes(1))
    })

    it('reapplies a newer tick over a slower full-roster refresh', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      vi.mocked(axios.get).mockResolvedValue({
        data: [{ id: 'd1', first_name: 'John', health: 10 }],
      } as never)
      store.dwellers = [{ id: 'd1', health: 10 }] as never
      store.allDwellers = [{ id: 'd1', health: 10 }] as never
      store.allDwellersLoadedVaultId = 'vault-1'

      store.applyDwellerTick(
        'vault-1',
        [tickSnapshot({ id: 'd1', health: 20 }), tickSnapshot({ id: 'new' })],
        'token'
      )
      store.applyDwellerTick('vault-1', [tickSnapshot({ id: 'd1', health: 30 })], 'token')
      await vi.waitFor(() => expect(vi.mocked(axios.get)).toHaveBeenCalledTimes(2))
      await vi.waitFor(() => {
        expect(store.dwellers.find((d) => d.id === 'd1')?.health).toBe(30)
        expect(store.allDwellers.find((d) => d.id === 'd1')?.health).toBe(30)
      })
    })
  })
})
