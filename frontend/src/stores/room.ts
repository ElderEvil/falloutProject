// src/stores/room.ts
import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface Room {
  id: string;
  name: string;
  category: string;
  ability: string;
  population_required: number;
  base_cost: number;
  incremental_cost: number;
  t2_upgrade_cost: number;
  t3_upgrade_cost: number;
  capacity: number;
  output: string;
  size_min: number;
  size_max: number;
  size: number;
  tier: number;
  coordinate_x: number;
  coordinate_y: number;
  created_at: string;
  updated_at: string;
}

interface RoomCreate {
  coordinate_x: number;
  coordinate_y: number;
  type: string;
}

export const useRoomStore = defineStore('room', {
  state: () => ({
    rooms: [] as Room[],
  }),
  actions: {
    async fetchRooms(vaultId: string, token: string) {
      try {
        const response = await axios.get(`/api/v1/rooms/vault/${vaultId}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.rooms = response.data
      } catch (error) {
        console.error('Failed to fetch rooms', error)
      }
    },
    async buildRoom(roomData: RoomCreate, token: string) {
      try {
        const response = await axios.post('/api/build/', roomData, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.rooms.push(response.data)
      } catch (error) {
        console.error('Failed to build room', error)
      }
    },
    async destroyRoom(roomId: string, token: string) {
      try {
        await axios.delete(`/api/destroy/${roomId}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.rooms = this.rooms.filter(room => room.id !== roomId)
      } catch (error) {
        console.error('Failed to destroy room', error)
      }
    }
  }
})
