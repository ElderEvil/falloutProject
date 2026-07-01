import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import { AxiosError } from 'axios'
import type { Room, RoomCreate, RoomTemplate } from '../models/room'
import { useVaultStore } from '@/modules/vault/stores/vault'

export const useRoomStore = defineStore('room', () => {
  // State
  const rooms = ref<Room[]>([])
  const availableRooms = ref<RoomTemplate[]>([])
  const selectedRoom = ref<RoomTemplate | null>(null)
  const isPlacingRoom = ref(false)

  // Actions
  async function fetchRooms(vaultId: string, token: string): Promise<void> {
    try {
      const response = await axios.get<Room[]>(`/api/v1/rooms/vault/${vaultId}/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      rooms.value = response.data
    } catch (error) {
      console.error('Failed to fetch rooms', error)
      rooms.value = [] // Reset to empty array on error
    }
  }

  async function fetchRoomsData(token: string, vaultId?: string): Promise<void> {
    try {
      // Use buildable endpoint if vault ID is provided to filter out vault door and unique rooms
      const endpoint = vaultId ? `/api/v1/rooms/buildable/${vaultId}/` : '/api/v1/rooms/read_data/'

      const response = await axios.get<RoomTemplate[]>(endpoint, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      availableRooms.value = response.data
    } catch (error) {
      console.error('Failed to fetch rooms data', error)
      availableRooms.value = []
    }
  }

  async function buildRoom(roomData: RoomCreate, token: string, vaultId: string): Promise<void> {
    try {
      const response = await axios.post<Room>('/api/v1/rooms/build/', roomData, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      rooms.value.push(response.data)
    } catch (error) {
      console.error('Failed to build room', error)
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail)
      }
      throw error
    }
    // Refresh vault to update caps (non-throwing) — separate from mutation error handling
    try {
      const vaultStore = useVaultStore()
      await vaultStore.refreshVault(vaultId, token)
    } catch (error) {
      console.warn('Failed to refresh vault after building room:', error)
    }
  }

  async function destroyRoom(roomId: string, token: string, vaultId: string): Promise<void> {
    try {
      await axios.delete(`/api/v1/rooms/destroy/${roomId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      rooms.value = rooms.value.filter((room) => room.id !== roomId)
    } catch (error) {
      console.error('Failed to destroy room', error)
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail)
      }
      throw error
    }
    // Refresh vault to update caps after refund (non-throwing) — separate from mutation error handling
    try {
      const vaultStore = useVaultStore()
      await vaultStore.refreshVault(vaultId, token)
    } catch (error) {
      console.warn('Failed to refresh vault after destroying room:', error)
    }
  }

  async function upgradeRoom(roomId: string, token: string, vaultId: string): Promise<void> {
    try {
      const response = await axios.post<Room>(
        `/api/v1/rooms/upgrade/${roomId}`,
        {},
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update the room in the local array
      const index = rooms.value.findIndex((room) => room.id === roomId)
      if (index !== -1) {
        rooms.value[index] = response.data
      }
    } catch (error) {
      console.error('Failed to upgrade room', error)
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail)
      }
      throw error
    }
    // Refresh vault to update caps (non-throwing) — separate from mutation error handling
    try {
      const vaultStore = useVaultStore()
      await vaultStore.refreshVault(vaultId, token)
    } catch (error) {
      console.warn('Failed to refresh vault after upgrading room:', error)
    }
  }

  function selectRoom(room: RoomTemplate): void {
    selectedRoom.value = room
    isPlacingRoom.value = true
  }

  function deselectRoom(): void {
    selectedRoom.value = null
    isPlacingRoom.value = false
  }

  return {
    // State
    rooms,
    availableRooms,
    selectedRoom,
    isPlacingRoom,
    // Actions
    fetchRooms,
    fetchRoomsData,
    buildRoom,
    destroyRoom,
    upgradeRoom,
    selectRoom,
    deselectRoom,
  }
})
