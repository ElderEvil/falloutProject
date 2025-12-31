import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRoomStore } from '@/stores/room'
import { useVaultStore } from '@/stores/vault'
import axios from '@/plugins/axios'
import { AxiosError } from 'axios'

vi.mock('@/plugins/axios')

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
          vault_id: 'vault-1'
        },
        {
          id: 'room-2',
          name: 'Diner',
          type: 'food',
          level: 1,
          position_x: 1,
          position_y: 0,
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockRooms })

      const store = useRoomStore()
      await store.fetchRooms('vault-1', 'test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/rooms/vault/vault-1/',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' }
        })
      )
      expect(store.rooms).toEqual(mockRooms)
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useRoomStore()
      await store.fetchRooms('vault-1', 'test-token')

      expect(store.rooms).toEqual([])
      expect(console.error).toHaveBeenCalledWith('Failed to fetch rooms', expect.any(Error))
    })
  })

  describe('fetchRoomsData', () => {
    it('should fetch available room types', async () => {
      const mockAvailableRooms = [
        { id: 'power-gen', name: 'Power Generator', type: 'power', cost: 100 },
        { id: 'diner', name: 'Diner', type: 'food', cost: 150 }
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockAvailableRooms })

      const store = useRoomStore()
      await store.fetchRoomsData('test-token')

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/rooms/read_data/',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' }
        })
      )
      expect(store.availableRooms).toEqual(mockAvailableRooms)
    })

    it('should handle errors', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Failed'))

      const store = useRoomStore()
      await store.fetchRoomsData('test-token')

      expect(console.error).toHaveBeenCalledWith('Failed to fetch rooms data', expect.any(Error))
    })
  })

  describe('buildRoom', () => {
    it('should build a new room and refresh vault', async () => {
      const newRoom = {
        id: 'room-3',
        name: 'Water Treatment',
        type: 'water',
        level: 1,
        position_x: 2,
        position_y: 0,
        vault_id: 'vault-1'
      }

      const roomData = {
        type: 'water',
        position_x: 2,
        position_y: 0,
        vault_id: 'vault-1'
      }

      vi.mocked(axios.post).mockResolvedValueOnce({ data: newRoom })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: 'vault-1', bottle_caps: 900 } })

      const store = useRoomStore()
      const vaultStore = useVaultStore()
      vaultStore.loadedVaults['vault-1'] = { id: 'vault-1', bottle_caps: 1000 } as any

      await store.buildRoom(roomData, 'test-token', 'vault-1')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/rooms/build/',
        roomData,
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' }
        })
      )
      expect(store.rooms).toContainEqual(newRoom)
    })

    it('should throw error with detail message', async () => {
      const error = new AxiosError('Request failed')
      error.response = {
        data: {
          detail: 'Insufficient caps'
        }
      } as any

      vi.mocked(axios.post).mockRejectedValueOnce(error)

      const store = useRoomStore()
      await expect(
        store.buildRoom({ type: 'power' } as any, 'test-token', 'vault-1')
      ).rejects.toThrow('Insufficient caps')
    })
  })

  describe('destroyRoom', () => {
    it('should destroy a room', async () => {
      const store = useRoomStore()
      store.rooms = [
        { id: 'room-1', name: 'Power Gen' } as any,
        { id: 'room-2', name: 'Diner' } as any
      ]

      vi.mocked(axios.delete).mockResolvedValueOnce({ data: {} })

      await store.destroyRoom('room-1', 'test-token')

      expect(axios.delete).toHaveBeenCalledWith(
        '/api/v1/rooms/destroy/room-1',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' }
        })
      )
      expect(store.rooms).toHaveLength(1)
      expect(store.rooms[0].id).toBe('room-2')
    })

    it('should handle errors', async () => {
      vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Failed'))

      const store = useRoomStore()
      store.rooms = [{ id: 'room-1' } as any]

      await store.destroyRoom('room-1', 'test-token')

      expect(console.error).toHaveBeenCalledWith('Failed to destroy room', expect.any(Error))
      expect(store.rooms).toHaveLength(1) // Room not removed on error
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
