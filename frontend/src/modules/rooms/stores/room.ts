import { ref } from 'vue'
import { defineStore, acceptHMRUpdate } from 'pinia'
import * as http from '@/core/plugins/httpClient'
import { handleStoreError } from '@/core/utils/errorHandler'
import type { Room, RoomCreate, RoomTemplate } from '../models/room'
import { useVaultStore } from '@/modules/vault/stores/vault'

export const useRoomStore = defineStore('room', () => {
  // State
  const rooms = ref<Room[]>([])
  const availableRooms = ref<RoomTemplate[]>([])
  const selectedRoom = ref<RoomTemplate | null>(null)
  const isPlacingRoom = ref(false)

  // Actions
  async function fetchRooms(vaultId: string, _token: string): Promise<void> {
    try {
      rooms.value = await http.apiGet<Room[]>(`/api/v1/rooms/vault/${vaultId}/`)
    } catch (error) {
      handleStoreError(error, 'Failed to fetch rooms')
      rooms.value = [] // Reset to empty array on error
    }
  }

  async function fetchRoomsData(_token: string, vaultId?: string): Promise<void> {
    try {
      // Use buildable endpoint if vault ID is provided to filter out vault door and unique rooms
      const endpoint = vaultId ? `/api/v1/rooms/buildable/${vaultId}/` : '/api/v1/rooms/read_data/'

      availableRooms.value = await http.apiGet<RoomTemplate[]>(endpoint)
    } catch (error) {
      handleStoreError(error, 'Failed to fetch rooms data')
    }
  }

  async function buildRoom(roomData: RoomCreate, token: string, vaultId: string): Promise<void> {
    try {
      const newRoom = await http.apiPost<Room>('/api/v1/rooms/build/', roomData)
      rooms.value.push(newRoom)

      // Refresh vault data to update caps
      const vaultStore = useVaultStore()
      await vaultStore.refreshVault(vaultId, token)
    } catch (error) {
      handleStoreError(error, 'Failed to build room')
      if (error instanceof http.ApiError && error.detail) {
        const detail = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)
        throw new Error(detail)
      }
      throw error
    }
  }

  async function destroyRoom(roomId: string, token: string, vaultId: string): Promise<void> {
    try {
      await http.apiDelete(`/api/v1/rooms/destroy/${roomId}`)
      rooms.value = rooms.value.filter((room) => room.id !== roomId)

      // Refresh vault to update caps after refund
      const vaultStore = useVaultStore()
      await vaultStore.refreshVault(vaultId, token)
    } catch (error) {
      handleStoreError(error, 'Failed to destroy room')
      if (error instanceof http.ApiError && error.detail) {
        const detail = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)
        throw new Error(detail)
      }
      throw error
    }
  }

  async function upgradeRoom(roomId: string, token: string, vaultId: string): Promise<void> {
    try {
      const upgraded = await http.apiPost<Room>(`/api/v1/rooms/upgrade/${roomId}`, {})

      // Update the room in the local array
      const index = rooms.value.findIndex((room) => room.id === roomId)
      if (index !== -1) {
        rooms.value[index] = upgraded
      }

      // Refresh vault data to update caps
      const vaultStore = useVaultStore()
      await vaultStore.refreshVault(vaultId, token)
    } catch (error) {
      handleStoreError(error, 'Failed to upgrade room')
      if (error instanceof http.ApiError && error.detail) {
        const detail = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)
        throw new Error(detail)
      }
      throw error
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

// HMR support
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useRoomStore, import.meta.hot))
}
