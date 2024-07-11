// src/stores/dweller.ts
import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface Dweller {
  id: string;
  first_name: string;
  last_name: string;
  level: number;
  health: number;
  happiness: number;
  bio: string;
  image_url: string;
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
    dwellers: [] as Dweller[],
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
  }
})
