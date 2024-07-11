import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface Vault {
  id: string;
  name: string;
  bottle_caps: number;
  happiness: number;
  power: number;
  power_max: number;
  food: number;
  food_max: number;
  water: number;
  water_max: number;
  population_max: number;
  created_at: string;
  updated_at: string;
  room_count: number;
  dweller_count: number;
}

export const useVaultStore = defineStore('vault', {
  state: () => ({
    vaults: [] as Vault[]
  }),
  actions: {
    async fetchVaults(token: string) {
      try {
        const response = await axios.get('/api/v1/vaults/my', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.vaults = response.data
      } catch (error) {
        console.error('Failed to fetch vaults', error)
      }
    },
    async createVault(name: string, token: string) {
      try {
        await axios.post('/api/v1/vaults/initiate', { name }, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        await this.fetchVaults(token) // Refetch the vaults to update the list
      } catch (error) {
        console.error('Failed to create vault', error)
      }
    },
    async deleteVault(id: string, token: string) {
      try {
        await axios.delete(`/api/v1/vaults/${id}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.vaults = this.vaults.filter(vault => vault.id !== id)
      } catch (error) {
        console.error('Failed to delete vault', error)
      }
    }
  }
})
