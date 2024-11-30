import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface RoomState {
  rooms: Room[]
  availableRooms: Room[]
  selectedRoom: Room | null
  isPlacingRoom: boolean
}

export const useRoomStore = defineStore('room', {
  state: (): RoomState => ({
    rooms: [],
    availableRooms: [],
    selectedRoom: null,
    isPlacingRoom: false
  }),
  actions: {
    async fetchRooms(vaultId: string, token: string): Promise<void> {
      try {
        const response = await axios.get<Room[]>(`/api/v1/rooms/vault/${vaultId}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.rooms = response.data
      } catch (error) {
        console.error('Failed to fetch rooms', error)
      }
    },
    async fetchRoomsData(token: string): Promise<void> {
      try {
        const response = await axios.get<Room[]>('/api/v1/rooms/read_data/', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.availableRooms = response.data
      } catch (error) {
        console.error('Failed to fetch rooms data', error)
      }
    },
    async buildRoom(roomData: RoomCreate, token: string): Promise<void> {
      try {
        const response = await axios.post<Room>('/api/v1/rooms/build/', roomData, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.rooms.push(response.data)
      } catch (error) {
        console.error('Failed to build room', error)
      }
    },
    async destroyRoom(roomId: string, token: string): Promise<void> {
      try {
        await axios.delete(`/api/v1/rooms/destroy/${roomId}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.rooms = this.rooms.filter((room) => room.id !== roomId)
      } catch (error) {
        console.error('Failed to destroy room', error)
      }
    },
    selectRoom(room: Room): void {
      this.selectedRoom = room
      this.isPlacingRoom = true
    },
    deselectRoom(): void {
      this.selectedRoom = null
      this.isPlacingRoom = false
    }
  }
})
