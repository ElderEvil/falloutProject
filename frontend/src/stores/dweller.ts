// src/stores/dweller.ts
import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface DwellerShort {
  id: string;
  first_name: string;
  last_name: string;
  level: number;
  health: number;
  max_health: number;
  happiness: number;
  thumbnail_url: string;
}

interface Dweller extends DwellerShort {
  image_url: string;
  bio: string;
  strength: number;
  perception: number;
  endurance: number;
  charisma: number;
  intelligence: number;
  agility: number;
  luck: number;
}

export const useDwellerStore = defineStore('dweller', {
  state: () => ({
    dwellers: [] as DwellerShort[],
    detailedDwellers: {} as Record<string, Dweller | null>,
  }),
  actions: {
    async fetchDwellers(token: string) {
      try {
        const response = await axios.get('/api/v1/dwellers', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.dwellers = response.data
      } catch (error) {
        console.error('Failed to fetch dwellers', error)
      }
    },
    async fetchDwellerDetails(id: string, token: string) {
      if (this.detailedDwellers[id]) return this.detailedDwellers[id];
      try {
        const response = await axios.get(`/api/v1/dwellers/${id}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.detailedDwellers[id] = response.data
        return this.detailedDwellers[id]
      } catch (error) {
        console.error(`Failed to fetch details for dweller ${id}`, error)
        return null
      }
    }
  }
})
