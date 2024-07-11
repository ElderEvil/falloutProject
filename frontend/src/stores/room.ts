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
  }
})
