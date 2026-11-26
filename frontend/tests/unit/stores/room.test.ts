import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { FEEDBACK_TIMING_MS } from '@/core/config/feedback'
import { audioManager } from '@/core/audio/audioManager'
import axios from '@/core/plugins/axios'
import { AxiosError } from 'axios'
import type { Room } from '@/modules/rooms/models/room'

const mockToast = vi.hoisted(() => ({ error: vi.fn() }))

vi.mock('@/core/plugins/axios')
vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
vi.mock('@/core/audio/audioManager', () => ({ audioManager: { play: vi.fn() } }))

const dwellerRefresh = vi.hoisted(() => ({
  fetchWithCurrentFilters: vi.fn().mockResolvedValue(undefined),
  fetchAllDwellers: vi.fn().mockResolvedValue(undefined),
  dwellers: [] as unknown[],
  allDwellers: [] as unknown[],
  detailedDwellers: {} as Record<string, unknown>,
}))
vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({ filter: dwellerRefresh }),
}))

function makeRoom(overrides: Partial<Room> = {}): Room {
  return {
    id: 'room-1',
    name: 'Power Generator',
    category: 'production',
    ability: 'strength',
    population_required: 0,
    base_cost: 100,
    incremental_cost: 0,
    t2_upgrade_cost: 200,
    t3_upgrade_cost: 400,
    capacity: 6,
    output: 10,
    size_min: 3,
    size_max: 9,
    size: 3,
    tier: 1,
    coordinate_x: 0,
    coordinate_y: 0,
    image_url: null,
    arena_last_fight_at: null,
    arena_fight_started_at: null,
    arena_fighter_a_id: null,
    arena_fighter_b_id: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

const detailError = (detail: string) => {
  const error = new AxiosError('Request failed')
  error.response = { data: { detail } } as never
  return error
}

/** Answer the post with `response`, then the vault refresh and the rooms refetch. */
const arrangeMutation = (response: unknown, rooms: unknown[] = [response]) => {
  vi.mocked(axios.post).mockResolvedValueOnce({ data: response })
  vi.mocked(axios.get)
    .mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })
    .mockResolvedValueOnce({ data: rooms })
}

const roomIds = () => useRoomStore().rooms.map((room) => room.id)

describe('Room Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().token = 'test-token'
    vi.clearAllMocks()
    dwellerRefresh.allDwellers = []
    dwellerRefresh.dwellers = []
    dwellerRefresh.detailedDwellers = {}
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('initializes with empty state', () => {
    const store = useRoomStore()

    expect(store.rooms).toEqual([])
    expect(store.availableRooms).toEqual([])
    expect(store.selectedRoom).toBeNull()
    expect(store.isPlacingRoom).toBe(false)
  })

  describe('fetchRooms', () => {
    it('rejects an off-vault rooms read before it requests or publishes anything', async () => {
      useVaultStore().activeVaultId = 'vault-2'

      const result = await useRoomStore().fetchRooms('vault-1')

      expect(result).toBe('superseded')
      expect(vi.mocked(axios.get)).not.toHaveBeenCalled()
      expect(useRoomStore().rooms).toEqual([])
    })

    it('does not publish a rooms response that lands after a vault switch', async () => {
      useVaultStore().activeVaultId = 'vault-1'
      const store = useRoomStore()
      store.rooms = [makeRoom({ id: 'kept' })]
      let release!: (value: { data: Room[] }) => void
      vi.mocked(axios.get).mockReturnValueOnce(
        new Promise<{ data: Room[] }>((resolve) => (release = resolve))
      )

      const pending = store.fetchRooms('vault-1')
      useVaultStore().activeVaultId = 'vault-2'
      release({ data: [makeRoom({ id: 'stale' })] })
      expect(await pending).toBe('superseded')
      expect(roomIds()).toEqual(['kept'])

      let releaseSecond!: (value: { data: Room[] }) => void
      vi.mocked(axios.get).mockReturnValueOnce(
        new Promise<{ data: Room[] }>((resolve) => (releaseSecond = resolve))
      )
      const second = store.fetchRooms('vault-2')
      useAuthStore().sessionGeneration++
      releaseSecond({ data: [makeRoom({ id: 'post-logout' })] })
      expect(await second).toBe('superseded')
      expect(roomIds()).toEqual(['kept'])

      let rejectThird!: (error: unknown) => void
      vi.mocked(axios.get).mockReturnValueOnce(
        new Promise((_resolve, reject) => (rejectThird = reject)) as never
      )
      const third = store.fetchRooms('vault-2')
      useAuthStore().sessionGeneration++
      rejectThird(new Error('Network gone'))
      await third
      expect(mockToast.error).not.toHaveBeenCalled()
      expect(roomIds()).toEqual(['kept'])
    })

    it('should fetch rooms for a vault', async () => {
      const mockRooms = [
        { id: 'room-1', name: 'Power Generator', type: 'power', vault_id: 'vault-1' },
        { id: 'room-2', name: 'Diner', type: 'food', vault_id: 'vault-1' },
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockRooms })

      const result = await useRoomStore().fetchRooms('vault-1')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/rooms/vault/vault-1/',
        expect.objectContaining({ params: { limit: expect.any(Number) } })
      )
      expect(useRoomStore().rooms).toEqual(mockRooms)
      expect(result).toBe('loaded')
    })

    it('loads beyond the API default page so build prices count the entire vault', async () => {
      const rooms = Array.from({ length: 101 }, (_, index) => ({
        id: `room-${index}`,
        name: 'Diner',
      }))
      vi.mocked(axios.get).mockImplementationOnce(async (_url, config) => ({
        data: rooms.slice(0, config?.params?.limit ?? 100),
      }))

      const store = useRoomStore()
      await store.fetchRooms('vault-1')

      expect(store.rooms).toHaveLength(101)
      expect(store.roomsLoadedVaultId).toBe('vault-1')
    })

    it.each([false, true])(
      'invalidates a failed refresh cache (throwOnError=%s)',
      async (throwOnError) => {
        const store = useRoomStore()
        vi.mocked(axios.get).mockResolvedValueOnce({ data: [makeRoom()] })
        await store.fetchRooms('vault-1')
        expect(store.roomsLoadedVaultId).toBe('vault-1')

        vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))
        const refresh = store.fetchRooms('vault-1', throwOnError)
        if (throwOnError) await expect(refresh).rejects.toThrow('Network error')
        else expect(await refresh).toBe('failed')
        expect(store.rooms).toEqual([])
        expect(store.roomsLoadedVaultId).toBeNull()

        vi.mocked(axios.get).mockResolvedValueOnce({ data: [makeRoom()] })
        expect(await store.fetchRooms('vault-1')).toBe('loaded')
        expect(store.roomsLoadedVaultId).toBe('vault-1')
      }
    )

    it('should handle errors gracefully', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useRoomStore()
      const result = await store.fetchRooms('vault-1')

      expect(store.rooms).toEqual([])
      expect(result).toBe('failed')
      expect(mockToast.error).toHaveBeenCalledTimes(1)
      expect(mockToast.error).toHaveBeenCalledWith('Failed to fetch rooms: Network error')
    })

    it('should ignore a stale room response after a newer modal request', async () => {
      let resolveFirst!: (value: unknown) => void
      const freshRooms = [{ id: 'fresh', name: 'New Gym' }]
      const staleRooms = [{ id: 'stale', name: 'Old Gym' }]

      vi.mocked(axios.get)
        .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
        .mockResolvedValueOnce({ data: freshRooms })

      const store = useRoomStore()
      const firstRequest = store.fetchRooms('vault-1')
      const secondRequest = store.fetchRooms('vault-1')

      expect(await secondRequest).toBe('loaded')
      expect(store.rooms).toEqual(freshRooms)

      resolveFirst({ data: staleRooms })
      expect(await firstRequest).toBe('superseded')
      expect(store.rooms).toEqual(freshRooms)
    })

    it('reports a superseded request as superseded even when it errored', async () => {
      let rejectFirst!: (reason: unknown) => void
      const freshRooms = [{ id: 'fresh', name: 'New Gym' }]

      vi.mocked(axios.get)
        .mockImplementationOnce(() => new Promise((_, reject) => (rejectFirst = reject)))
        .mockResolvedValueOnce({ data: freshRooms })

      const store = useRoomStore()
      const firstRequest = store.fetchRooms('vault-1')
      await store.fetchRooms('vault-1')

      rejectFirst(new Error('Network error'))
      expect(await firstRequest).toBe('superseded')
      expect(store.rooms).toEqual(freshRooms)
      expect(store.roomsLoadedVaultId).toBe('vault-1')
    })
  })

  describe('fetchBuildableRooms', () => {
    it('should fetch buildable rooms for the vault', async () => {
      // Vault Door must never be buildable, so it is absent from this list.
      const mockBuildableRooms = [
        { id: 'power-gen', name: 'Power Generator', type: 'power', cost: 100 },
        { id: 'diner', name: 'Diner', type: 'food', cost: 150 },
      ]
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockBuildableRooms })

      const store = useRoomStore()
      await store.fetchBuildableRooms('vault-1')

      expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/buildable/vault-1/')
      expect(store.availableRooms).toEqual(mockBuildableRooms)
    })

    it('swallows a failure', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Failed'))

      await expect(useRoomStore().fetchBuildableRooms('vault-1')).resolves.toBeUndefined()
    })

    it('should ignore stale responses and errors', async () => {
      let resolveFirst!: (value: unknown) => void
      let rejectThird!: (reason: unknown) => void
      const freshRooms = [{ id: 'fresh', name: 'New Gym' }]

      vi.mocked(axios.get)
        .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
        .mockResolvedValueOnce({ data: freshRooms })
        .mockImplementationOnce(() => new Promise((_, reject) => (rejectThird = reject)))
        .mockResolvedValueOnce({ data: freshRooms })

      const store = useRoomStore()
      const staleResponse = store.fetchBuildableRooms('vault-1')
      await store.fetchBuildableRooms('vault-2')
      resolveFirst({ data: [{ id: 'stale', name: 'Old Gym' }] })
      await staleResponse
      expect(store.availableRooms).toEqual(freshRooms)

      const staleError = store.fetchBuildableRooms('vault-1')
      await store.fetchBuildableRooms('vault-2')
      rejectThird(new Error('Failed'))
      await staleError
      expect(store.availableRooms).toEqual(freshRooms)
    })
  })

  describe('buildRoom', () => {
    it('should build a new room and refresh vault', async () => {
      const newRoom = makeRoom({
        id: 'room-3',
        name: 'Water Treatment',
        ability: 'perception',
        coordinate_x: 2,
      })
      arrangeMutation(newRoom)

      const result = await useRoomStore().buildRoom('Water Treatment', 2, 0, 'vault-1')

      expect(result).toBe('built')
      expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/build/', {
        vault_id: 'vault-1',
        room_name: 'Water Treatment',
        coordinate_x: 2,
        coordinate_y: 0,
      })
      expect(useRoomStore().rooms).toEqual([newRoom])
      expect(dwellerRefresh.fetchWithCurrentFilters).toHaveBeenCalledWith('vault-1')
      expect(audioManager.play).toHaveBeenCalledWith('vaultBuild', 'sfx')
    })

    it.each([
      {
        label: 'a left-side survivor',
        rooms: [makeRoom({ id: 'absorbed', name: 'Water Treatment', coordinate_x: 3 })],
        absorbedId: 'absorbed',
        buildAt: 0,
        survivor: makeRoom({ id: 'survivor', name: 'Water Treatment', size: 6 }),
      },
      {
        label: 'a same-id survivor',
        rooms: [
          makeRoom({ id: 'left', name: 'Water Treatment' }),
          makeRoom({ id: 'right', name: 'Water Treatment', coordinate_x: 6 }),
        ],
        absorbedId: 'right',
        buildAt: 3,
        survivor: makeRoom({ id: 'left', name: 'Water Treatment', size: 9 }),
      },
    ])(
      'repoints occupants absorbed by $label',
      async ({ rooms, absorbedId, buildAt, survivor }) => {
        const store = useRoomStore()
        store.roomsLoadedVaultId = 'vault-1'
        const occupant = { id: 'd1', room_id: absorbedId, status: 'working' }
        store.rooms = rooms
        dwellerRefresh.allDwellers = [occupant]
        dwellerRefresh.dwellers = [occupant]
        arrangeMutation(survivor)

        expect(await store.buildRoom('Water Treatment', buildAt, 0, 'vault-1')).toBe('extended')
        expect(roomIds()).toEqual([survivor.id])
        expect(dwellerRefresh.allDwellers[0]?.room_id).toBe(survivor.id)
        expect(dwellerRefresh.dwellers[0]?.room_id).toBe(survivor.id)
      }
    )

    it('skips the local publish when the build response lands on another vault', async () => {
      const store = useRoomStore()
      store.roomsLoadedVaultId = 'vault-1'
      const occupant = { id: 'd1', room_id: 'absorbed', status: 'working' }
      store.rooms = [makeRoom({ id: 'absorbed', name: 'Water Treatment', coordinate_x: 3 })]
      dwellerRefresh.allDwellers = [occupant]
      dwellerRefresh.dwellers = [occupant]
      useVaultStore().activeVaultId = 'vault-1'

      const survivor = makeRoom({ id: 'survivor', name: 'Water Treatment', size: 6 })
      let resolveBuild!: (value: unknown) => void
      vi.mocked(axios.post).mockReturnValueOnce(
        new Promise((resolve) => (resolveBuild = resolve)) as never
      )

      const building = store.buildRoom('Water Treatment', 0, 0, 'vault-1')
      await vi.waitFor(() => expect(vi.mocked(axios.post)).toHaveBeenCalled())
      useVaultStore().activeVaultId = 'vault-2'
      resolveBuild({ data: survivor })
      await building

      expect(vi.mocked(axios.get)).not.toHaveBeenCalled()
      expect(roomIds()).toEqual(['absorbed'])
      expect(dwellerRefresh.allDwellers[0]?.room_id).toBe('absorbed')
    })

    it('should replace an existing room when the response id is already present', async () => {
      const existingRoom = makeRoom()
      const extendedRoom = makeRoom({ size: 6, capacity: 12, output: 20 })
      arrangeMutation(extendedRoom)

      const store = useRoomStore()
      store.rooms = [existingRoom]

      expect(await store.buildRoom('Power Generator', 3, 0, 'vault-1')).toBe('extended')
      expect(store.rooms).toEqual([extendedRoom])
    })

    it('drops rooms absorbed by a merge when the refetched list omits them', async () => {
      const survivor = makeRoom({ size: 9 })
      const absorbedA = makeRoom({ id: 'room-2', coordinate_x: 3 })
      const absorbedB = makeRoom({ id: 'room-3', coordinate_x: 6 })
      arrangeMutation(survivor)

      const store = useRoomStore()
      store.rooms = [survivor, absorbedA, absorbedB]

      expect(await store.buildRoom('Power Generator', 3, 1, 'vault-1')).toBe('extended')
      expect(store.rooms).toEqual([survivor])
    })

    it('should throw error with detail message', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(detailError('Insufficient caps'))

      await expect(useRoomStore().buildRoom('Power Generator', 0, 0, 'vault-1')).rejects.toThrow(
        'Insufficient caps'
      )
      expect(audioManager.play).not.toHaveBeenCalled()
    })
  })

  describe('destroyRoom', () => {
    it('should destroy a room', async () => {
      vi.mocked(axios.delete).mockResolvedValueOnce({ data: {} })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })

      const store = useRoomStore()
      store.rooms = [
        { id: 'room-1', name: 'Power Gen' } as any,
        { id: 'room-2', name: 'Diner' } as any,
      ]
      useVaultStore().loadedVaults['vault-1'] = { id: 'vault-1', bottle_caps: 1000 } as any

      await store.destroyRoom('room-1', 'vault-1')

      expect(axios.delete).toHaveBeenCalledWith('/api/v1/rooms/destroy/room-1')
      expect(store.rooms).toEqual([expect.objectContaining({ id: 'room-2' })])
    })

    it('should handle errors', async () => {
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Failed'))

      const store = useRoomStore()
      store.rooms = [{ id: 'room-1' } as any]

      await expect(store.destroyRoom('room-1', 'vault-1')).rejects.toThrow('Failed')

      expect(store.rooms).toHaveLength(1) // Room not removed on error
    })
  })

  describe('upgradeRoom', () => {
    function mockUpgradeFlow(upgradedRoom: unknown, roomsList: unknown[]) {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: upgradedRoom })
      vi.mocked(axios.get).mockImplementation((url: string) =>
        url.includes('/api/v1/rooms/vault/')
          ? Promise.resolve({ data: roomsList })
          : Promise.resolve({ data: { id: 'vault-1', bottle_caps: 500 } })
      )
    }

    it('should upgrade a room and refresh vault', async () => {
      const originalRoom = {
        id: 'room-1',
        name: 'Power Generator',
        tier: 1,
        capacity: 10,
        output: 20,
        vault_id: 'vault-1',
      }
      const upgradedRoom = { ...originalRoom, tier: 2, capacity: 12, output: 24 }
      mockUpgradeFlow(upgradedRoom, [upgradedRoom])

      const store = useRoomStore()
      store.rooms = [originalRoom as any]
      useVaultStore().loadedVaults['vault-1'] = { id: 'vault-1', bottle_caps: 1000 } as any

      await store.upgradeRoom('room-1', 'vault-1')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/upgrade/room-1', {})
      expect(store.rooms[0]).toMatchObject({ tier: 2, capacity: 12, output: 24 })
      expect(store.mergedRoomId).toBeNull()
      expect(audioManager.play).toHaveBeenCalledWith('upgrade', 'sfx')
    })

    it.each(['Insufficient caps for upgrade', 'Room is already at maximum tier 3'])(
      'surfaces the API detail "%s"',
      async (detail) => {
        vi.mocked(axios.post).mockRejectedValueOnce(detailError(detail))

        await expect(useRoomStore().upgradeRoom('room-1', 'vault-1')).rejects.toThrow(detail)
      }
    )

    it('should handle generic errors', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Network error'))

      await expect(useRoomStore().upgradeRoom('room-1', 'vault-1')).rejects.toThrow()
    })

    it('should update the correct room in the array', async () => {
      const room1 = { id: 'room-1', name: 'Power Gen', tier: 1 }
      const room2 = { id: 'room-2', name: 'Diner', tier: 1 }
      const upgradedRoom1 = { ...room1, tier: 2 }
      mockUpgradeFlow(upgradedRoom1, [upgradedRoom1, room2])

      const store = useRoomStore()
      store.rooms = [room1 as any, room2 as any]
      useVaultStore().loadedVaults['vault-1'] = { id: 'vault-1' } as any

      await store.upgradeRoom('room-1', 'vault-1')

      expect(store.rooms.map((room) => room.tier)).toEqual([2, 1])
    })

    it('should resync rooms and flash the survivor when the upgrade merges', async () => {
      const absorbed = { id: 'room-1', name: 'Power Gen', tier: 1, size: 3 }
      const survivor = { id: 'room-9', name: 'Power Gen', tier: 2, size: 6 }
      mockUpgradeFlow(survivor, [survivor])

      const store = useRoomStore()
      store.rooms = [{ id: 'room-9', size: 3 } as any, absorbed as any]
      useVaultStore().loadedVaults['vault-1'] = { id: 'vault-1' } as any

      await store.upgradeRoom('room-1', 'vault-1')

      expect(store.rooms).toEqual([survivor])
      expect(store.mergedRoomId).toBe('room-9')
      expect(dwellerRefresh.fetchWithCurrentFilters).toHaveBeenCalledWith('vault-1')
    })

    it('reconciles cached dweller details with the survivor room after a merge', async () => {
      const absorbed = { id: 'room-1', name: 'Power Gen', tier: 1, size: 3 }
      const survivor = makeRoom({ id: 'room-9', name: 'Power Gen', tier: 2, size: 6 })
      mockUpgradeFlow(survivor, [survivor])

      const store = useRoomStore()
      store.rooms = [absorbed as never]
      useVaultStore().loadedVaults['vault-1'] = { id: 'vault-1' } as never
      dwellerRefresh.allDwellers = [{ id: 'd1', room_id: 'room-9' }]
      dwellerRefresh.detailedDwellers = { d1: { id: 'd1', room: { id: 'room-1' } } }

      await store.upgradeRoom('room-1', 'vault-1')

      const detailed = dwellerRefresh.detailedDwellers.d1 as { room?: { id: string } | null }
      expect(detailed.room?.id).toBe('room-9')
    })
  })

  it('selects a room for placement and deselects it', () => {
    const store = useRoomStore()
    const room = { id: 'power-gen', name: 'Power Generator' } as any

    store.selectRoom(room)
    expect(store.selectedRoom).toEqual(room)
    expect(store.isPlacingRoom).toBe(true)

    store.deselectRoom()
    expect(store.selectedRoom).toBeNull()
    expect(store.isPlacingRoom).toBe(false)
  })

  describe('room remodeling', () => {
    it('replaces a split footprint locally and preserves unrelated rooms', async () => {
      const store = useRoomStore()
      const source = makeRoom({ size: 6 })
      const pieces = [makeRoom(), makeRoom({ id: 'piece-2', coordinate_x: 3 })]
      store.rooms = [source, makeRoom({ id: 'other' })]
      vi.mocked(axios.post).mockResolvedValueOnce({ data: pieces })

      await store.remodelRoom(source.id)

      expect(axios.post).toHaveBeenCalledWith(`/api/v1/rooms/split/${source.id}`, {})
      expect(store.rooms.map((room) => room.id)).toEqual(['other', 'room-1', 'piece-2'])
    })

    it('removes both merge inputs, accepts the survivor id, and keeps state on failure', async () => {
      const store = useRoomStore()
      store.rooms = [makeRoom(), makeRoom({ id: 'right' })]
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Incident active'))

      await expect(store.remodelRoom('room-1', 'right')).rejects.toThrow('Incident active')
      expect(store.rooms).toHaveLength(2)

      vi.mocked(axios.post).mockResolvedValueOnce({ data: makeRoom({ size: 6 }) })
      await store.remodelRoom('right', 'room-1')
      expect(store.rooms).toHaveLength(1)
      expect(store.rooms[0]?.size).toBe(6)
    })
  })

  describe('room rush', () => {
    const payout = { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 }
    const quote = {
      can_rush: true,
      blocked_reason: null,
      fail_chance: 23,
      success_chance: 77,
      stacks: 2,
      max_stacks: 6,
      avg_ability: 8,
      avg_luck: 7,
      worker_count: 2,
      payout,
      caps_chance: 35,
      eligible_incidents: ['fire'],
      next_stack_penalty: 10,
    }
    const result = {
      outcome: 'success' as const,
      payout,
      caps: 120,
      xp_per_worker: 25,
      happiness_delta: 10,
      incident_id: null,
      incident_type: null,
      stacks_after: 3,
      next_fail_chance: 33,
      message: 'The rush succeeded.',
    }

    it('fetches a rush quote through the shared HTTP boundary', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: quote })

      await expect(useRoomStore().fetchRushQuote('room-1')).resolves.toEqual(quote)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/room-1/rush')
    })

    it('rushes a room, flashes the outcome after the feedback delay, and returns the result', async () => {
      vi.useFakeTimers()
      try {
        vi.mocked(axios.post).mockResolvedValueOnce({ data: result })
        vi.mocked(axios.get).mockResolvedValue({ data: { id: 'vault-1' } })
        const store = useRoomStore()

        await expect(store.rushRoom('room-1', 'vault-1')).resolves.toEqual(result)
        expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/room-1/rush', {})
        expect(store.rushedRoomId).toBeNull()

        await vi.advanceTimersByTimeAsync(FEEDBACK_TIMING_MS.rushDelay)

        expect(store.rushedRoomId).toBe('room-1')
        expect(store.rushOutcome).toBe('success')
      } finally {
        vi.useRealTimers()
      }
    })

    it('returns the confirmed outcome without waiting for background refreshes', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: result })
      vi.mocked(axios.get).mockImplementation(() => new Promise(() => {}))
      let returned = false

      void useRoomStore()
        .rushRoom('room-1', 'vault-1')
        .then(() => (returned = true))
      await flushPromises()

      expect(returned).toBe(true)
    })

    it('surfaces a rush conflict detail', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(
        detailError('Resolve the active incident before rushing.')
      )
      const store = useRoomStore()

      await expect(store.rushRoom('room-1', 'vault-1')).rejects.toThrow(
        'Resolve the active incident before rushing.'
      )
      expect(store.rushedRoomId).toBeNull()
      expect(store.rushOutcome).toBeNull()
    })
  })
})
