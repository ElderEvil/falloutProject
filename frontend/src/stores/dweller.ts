import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import type { Dweller, DwellerShort } from '@/models/dweller'

export const useDwellerStore = defineStore('dweller', {
  state: () => ({
    dwellers: [] as DwellerShort[],
    detailedDwellers: {} as Record<string, Dweller | null>
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
      if (this.detailedDwellers[id]) return this.detailedDwellers[id]
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
    },
    async generateDwellerInfo(id: string, token: string) {
      try {
        const response = await axios.post(`/api/v1/dwellers/${id}/generate_with_ai/`, null, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.detailedDwellers[id] = response.data
        return this.detailedDwellers[id]
      } catch (error) {
        console.error(`Failed to generate image for dweller ${id}`, error)
        return null
      }
    }
  }
})
