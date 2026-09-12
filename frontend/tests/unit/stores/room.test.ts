import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'
import { AxiosError } from 'axios'
import type { Room } from '@/modules/rooms/models/room'

vi.mock('@/core/plugins/axios')

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
    speedup_multiplier: 1,
    arena_last_fight_at: null,
    arena_fight_started_at: null,
    arena_fighter_a_id: null,
    arena_fighter_b_id: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('Room Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  describe('State', () => {
    it('should initialize with empty state', () => {
      const store = useRoomStore()

      expect(store.rooms).toEqual([])
      expect(store.availableRooms).toEqual([])
      expect(store.selectedRoom).toBeNull()
      expect(store.isPlacingRoom).toBe(false)
    })
  })

  describe('fetchRooms', () => {
    it('should fetch rooms for a vault', async () => {
      const mockRooms = [
        {
          id: 'room-1',
          name: 'Power Generator',
          type: 'power',
          level: 1,
          position_x: 0,
          position_y: 0,
          vault_id: 'vault-1',
        },
        {
          id: 'room-2',
          name: 'Diner',
          type: 'food',
          level: 1,
          position_x: 1,
          position_y: 0,
          vault_id: 'vault-1',
        },
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockRooms })

      const store = useRoomStore()
      await store.fetchRooms('vault-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/rooms/vault/vault-1/',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.rooms).toEqual(mockRooms)
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useRoomStore()
      await store.fetchRooms('vault-1', 'test-token')

      expect(store.rooms).toEqual([])
    })

    it('should ignore a stale room response after a newer modal request', async () => {
      let resolveFirst!: (value: unknown) => void
      const freshRooms = [{ id: 'fresh', name: 'New Gym' }]
      const staleRooms = [{ id: 'stale', name: 'Old Gym' }]

      vi.mocked(axios.get)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveFirst = resolve
            })
        )
        .mockResolvedValueOnce({ data: freshRooms })

      const store = useRoomStore()
      const firstRequest = store.fetchRooms('vault-1', 'test-token')
      const secondRequest = store.fetchRooms('vault-1', 'test-token')

      await secondRequest
      expect(store.rooms).toEqual(freshRooms)

      resolveFirst({ data: staleRooms })
      await firstRequest

      expect(store.rooms).toEqual(freshRooms)
    })
  })

  describe('fetchBuildableRooms', () => {
    it('should fetch buildable rooms for the vault', async () => {
      const mockBuildableRooms = [
        { id: 'power-gen', name: 'Power Generator', type: 'power', cost: 100 },
        { id: 'diner', name: 'Diner', type: 'food', cost: 150 },
        // Note: Vault Door should NOT be in this list
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockBuildableRooms })

      const store = useRoomStore()
      await store.fetchBuildableRooms('test-token', 'vault-1')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/rooms/buildable/vault-1/',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.availableRooms).toEqual(mockBuildableRooms)
    })

    it('should handle errors', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Failed'))

      const store = useRoomStore()
      await store.fetchBuildableRooms('test-token', 'vault-1')
    })

    it('should ignore stale responses and errors', async () => {
      let resolveFirst!: (value: unknown) => void
      let rejectThird!: (reason: unknown) => void
      const freshRooms = [{ id: 'fresh', name: 'New Gym' }]

      vi.mocked(axios.get)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveFirst = resolve
            })
        )
        .mockResolvedValueOnce({ data: freshRooms })
        .mockImplementationOnce(
          () =>
            new Promise((_, reject) => {
              rejectThird = reject
            })
        )
        .mockResolvedValueOnce({ data: freshRooms })

      const store = useRoomStore()
      const staleResponse = store.fetchBuildableRooms('test-token', 'vault-1')
      await store.fetchBuildableRooms('test-token', 'vault-2')
      resolveFirst({ data: [{ id: 'stale', name: 'Old Gym' }] })
      await staleResponse
      expect(store.availableRooms).toEqual(freshRooms)

      const staleError = store.fetchBuildableRooms('test-token', 'vault-1')
      await store.fetchBuildableRooms('test-token', 'vault-2')
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
        category: 'production',
        ability: 'perception',
        coordinate_x: 2,
        coordinate_y: 0,
      })

      vi.mocked(axios.post).mockResolvedValueOnce({ data: newRoom })
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })
        .mockResolvedValueOnce({ data: [newRoom] })

      const store = useRoomStore()

      const result = await store.buildRoom('Water Treatment', 2, 0, 'test-token', 'vault-1')

      expect(result).toBe('built')
      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/rooms/build/',
        {
          vault_id: 'vault-1',
          room_name: 'Water Treatment',
          coordinate_x: 2,
          coordinate_y: 0,
        },
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.rooms).toHaveLength(1)
      expect(store.rooms[0]).toEqual(newRoom)
    })

    it('should replace an existing room when the response id is already present', async () => {
      const existingRoom = makeRoom({ id: 'room-1', name: 'Power Generator', size: 3, coordinate_x: 0 })
      const extendedRoom = makeRoom({
        id: 'room-1',
        name: 'Power Generator',
        size: 6,
        coordinate_x: 0,
        capacity: 12,
        output: 20,
      })

      vi.mocked(axios.post).mockResolvedValueOnce({ data: extendedRoom })
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })
        .mockResolvedValueOnce({ data: [extendedRoom] })

      const store = useRoomStore()
      store.rooms = [existingRoom]

      const result = await store.buildRoom('Power Generator', 3, 0, 'test-token', 'vault-1')

      expect(result).toBe('extended')
      expect(store.rooms).toHaveLength(1)
      expect(store.rooms[0]).toEqual(extendedRoom)
    })

    it('drops rooms absorbed by a merge when the refetched list omits them', async () => {
      const survivor = makeRoom({ id: 'room-1', name: 'Power Generator', size: 9, coordinate_x: 0 })
      const absorbedA = makeRoom({ id: 'room-2', name: 'Power Generator', size: 3, coordinate_x: 3 })
      const absorbedB = makeRoom({ id: 'room-3', name: 'Power Generator', size: 3, coordinate_x: 6 })

      vi.mocked(axios.post).mockResolvedValueOnce({ data: survivor })
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })
        .mockResolvedValueOnce({ data: [survivor] })

      const store = useRoomStore()
      store.rooms = [survivor, absorbedA, absorbedB]

      const result = await store.buildRoom('Power Generator', 3, 1, 'test-token', 'vault-1')

      expect(result).toBe('extended')
      expect(store.rooms).toEqual([survivor])
    })

    it('should throw error with detail message', async () => {
      const error = new AxiosError('Request failed')
      error.response = {
        data: {
          detail: 'Insufficient caps',
        },
      } as any

      vi.mocked(axios.post).mockRejectedValueOnce(error)

      const store = useRoomStore()
      await expect(
        store.buildRoom('Power Generator', 0, 0, 'test-token', 'vault-1')
      ).rejects.toThrow('Insufficient caps')
    })
  })

  describe('destroyRoom', () => {
    it('should destroy a room', async () => {
      vi.mocked(axios.delete).mockResolvedValueOnce({ data: {} })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })

      const store = useRoomStore()
      const vaultStore = useVaultStore()
      store.rooms = [
        { id: 'room-1', name: 'Power Gen' } as any,
        { id: 'room-2', name: 'Diner' } as any,
      ]
      vaultStore.loadedVaults['vault-1'] = { id: 'vault-1', bottle_caps: 1000 } as any

      await store.destroyRoom('room-1', 'test-token', 'vault-1')

      expect(axios.delete).toHaveBeenCalledWith(
        '/api/v1/rooms/destroy/room-1',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.rooms).toHaveLength(1)
      expect(store.rooms[0].id).toBe('room-2')
    })

    it('should handle errors', async () => {
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Failed'))

      const store = useRoomStore()
      store.rooms = [{ id: 'room-1' } as any]

      await expect(store.destroyRoom('room-1', 'test-token', 'vault-1')).rejects.toThrow('Failed')

      expect(store.rooms).toHaveLength(1) // Room not removed on error
    })
  })

  describe('upgradeRoom', () => {
    it('should upgrade a room and refresh vault', async () => {
      const originalRoom = {
        id: 'room-1',
        name: 'Power Generator',
        tier: 1,
        capacity: 10,
        output: 20,
        vault_id: 'vault-1',
      }

      const upgradedRoom = {
        ...originalRoom,
        tier: 2,
        capacity: 12,
        output: 24,
      }

      vi.mocked(axios.post).mockResolvedValueOnce({ data: upgradedRoom })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 500 } })

      const store = useRoomStore()
      const vaultStore = useVaultStore()
      store.rooms = [originalRoom as any]
      vaultStore.loadedVaults['vault-1'] = { id: 'vault-1', bottle_caps: 1000 } as any

      await store.upgradeRoom('room-1', 'test-token', 'vault-1')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/rooms/upgrade/room-1',
        {},
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(store.rooms[0].tier).toBe(2)
      expect(store.rooms[0].capacity).toBe(12)
      expect(store.rooms[0].output).toBe(24)
    })

    it('should throw error when insufficient caps', async () => {
      const error = new AxiosError('Request failed')
      error.response = {
        data: {
          detail: 'Insufficient caps for upgrade',
        },
      } as any

      vi.mocked(axios.post).mockRejectedValueOnce(error)

      const store = useRoomStore()
      await expect(store.upgradeRoom('room-1', 'test-token', 'vault-1')).rejects.toThrow(
        'Insufficient caps for upgrade'
      )
    })

    it('should throw error when room is at max tier', async () => {
      const error = new AxiosError('Request failed')
      error.response = {
        data: {
          detail: 'Room is already at maximum tier 3',
        },
      } as any

      vi.mocked(axios.post).mockRejectedValueOnce(error)

      const store = useRoomStore()
      await expect(store.upgradeRoom('room-1', 'test-token', 'vault-1')).rejects.toThrow(
        'Room is already at maximum tier 3'
      )
    })

    it('should handle generic errors', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Network error'))

      const store = useRoomStore()
      await expect(store.upgradeRoom('room-1', 'test-token', 'vault-1')).rejects.toThrow()
    })

    it('should update the correct room in the array', async () => {
      const room1 = { id: 'room-1', name: 'Power Gen', tier: 1 }
      const room2 = { id: 'room-2', name: 'Diner', tier: 1 }
      const upgradedRoom1 = { ...room1, tier: 2 }

      vi.mocked(axios.post).mockResolvedValueOnce({ data: upgradedRoom1 })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: 'vault-1' } })

      const store = useRoomStore()
      const vaultStore = useVaultStore()
      store.rooms = [room1 as any, room2 as any]
      vaultStore.loadedVaults['vault-1'] = { id: 'vault-1' } as any

      await store.upgradeRoom('room-1', 'test-token', 'vault-1')

      expect(store.rooms[0].tier).toBe(2)
      expect(store.rooms[1].tier).toBe(1) // Other room unchanged
    })
  })

  describe('Room Selection', () => {
    it('should select a room for placement', () => {
      const store = useRoomStore()
      const room = { id: 'power-gen', name: 'Power Generator' } as any

      store.selectRoom(room)

      expect(store.selectedRoom).toEqual(room)
      expect(store.isPlacingRoom).toBe(true)
    })

    it('should deselect room', () => {
      const store = useRoomStore()
      store.selectedRoom = { id: 'power-gen' } as any
      store.isPlacingRoom = true

      store.deselectRoom()

      expect(store.selectedRoom).toBeNull()
      expect(store.isPlacingRoom).toBe(false)
    })
  })
})
