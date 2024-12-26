import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import type { Room, RoomCreate, RoomShortInfo } from '@/types/room.types'

interface RoomState {
  rooms: Room[]
  buildableRooms: RoomShortInfo[]
  isLoading: boolean
  error: string | null
}

interface ApiResponse<T> {
  data: T
  message?: string
}

export const useRoomStore = defineStore('room', {
  state: (): RoomState => ({
    rooms: [],
    buildableRooms: [],
    isLoading: false,
    error: null
  }),

  getters: {
    getRoomById: (state) => (id: string) => state.rooms.find((room) => room.id === id)
  },

  actions: {
    setError(error: unknown) {
      this.error = error instanceof Error ? error.message : 'An unknown error occurred'
      this.isLoading = false
    },

    async fetchRooms(vaultId: string): Promise<boolean> {
      this.isLoading = true
      this.error = null

      try {
        const response = await axios.get<ApiResponse<Room[]>>(`/api/v1/rooms/vault/${vaultId}`)
        this.rooms = response.data.data
        return true
      } catch (error) {
        this.setError(error)
        return false
      } finally {
        this.isLoading = false
      }
    },

    async fetchBuildableRooms(): Promise<boolean> {
      if (this.buildableRooms.length > 0) return true

      this.isLoading = true
      this.error = null

      try {
        const response = await axios.get<ApiResponse<RoomShortInfo[]>>('/api/v1/rooms/read_data')
        this.buildableRooms = response.data.data
        return true
      } catch (error) {
        this.setError(error)
        return false
      } finally {
        this.isLoading = false
      }
    },

    async buildRoom(roomData: RoomCreate): Promise<Room | null> {
      this.isLoading = true
      this.error = null

      try {
        const response = await axios.post<ApiResponse<Room>>('/api/v1/rooms/build', roomData)
        const newRoom = response.data.data
        this.rooms.push(newRoom)
        return newRoom
      } catch (error) {
        this.setError(error)
        return null
      } finally {
        this.isLoading = false
      }
    },

    async destroyRoom(roomId: string): Promise<boolean> {
      this.isLoading = true
      this.error = null

      const originalRooms = [...this.rooms]
      this.rooms = this.rooms.filter((room) => room.id !== roomId)

      try {
        await axios.delete<ApiResponse<void>>(`/api/v1/rooms/destroy/${roomId}`)
        return true
      } catch (error) {
        this.setError(error)
        this.rooms = originalRooms
        return false
      } finally {
        this.isLoading = false
      }
    }
  }
})
