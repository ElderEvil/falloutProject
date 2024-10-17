import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import { useRouter } from 'vue-router'

interface Vault {
  id: string
  number: number
  bottle_caps: number
  happiness: number
  power: number
  power_max: number
  food: number
  food_max: number
  water: number
  water_max: number
  population_max: number
  created_at: string
  updated_at: string
  room_count: number
  dweller_count: number
}

export const useVaultStore = defineStore('vault', {
  state: () => ({
    vaults: [] as Vault[],
    selectedVaultId: localStorage.getItem('selectedVaultId') as string | null,
    loadedVaults: {} as Record<string, Vault>,
    activeVaultId: null as string | null,
    isLoading: false
  }),
  getters: {
    selectedVault(state) {
      return state.vaults.find((vault) => vault.id === state.selectedVaultId) || null
    },
    activeVault(state) {
      return state.activeVaultId ? state.loadedVaults[state.activeVaultId] : null
    },
    loadedVaultIds(state) {
      return Object.keys(state.loadedVaults)
    }
  },
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
        await axios.post(
          '/api/v1/vaults/initiate',
          { name },
          {
            headers: {
              Authorization: `Bearer ${token}`
            }
          }
        )
        await this.fetchVaults(token) // Re-fetch the vaults to update the list
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
        this.vaults = this.vaults.filter((vault) => vault.id !== id)
        if (this.loadedVaults[id]) {
          delete this.loadedVaults[id]
        }
        if (this.activeVaultId === id) {
          this.activeVaultId = Object.keys(this.loadedVaults)[0] || null
        }
      } catch (error) {
        console.error('Failed to delete vault', error)
      }
    },
    async loadVault(id: string, token: string) {
      this.isLoading = true
      try {
        const response = await axios.get(`/api/v1/vaults/${id}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        this.loadedVaults[id] = response.data
        this.activeVaultId = id
        const router = useRouter()
        await router.push('/vault')
      } catch (error) {
        console.error('Failed to load vault', error)
        throw error
      } finally {
        this.isLoading = false
      }
    },
    setActiveVault(id: string) {
      if (this.loadedVaults[id]) {
        this.activeVaultId = id
      }
    },
    closeVaultTab(id: string) {
      if (this.loadedVaults[id]) {
        delete this.loadedVaults[id]
        if (this.activeVaultId === id) {
          this.activeVaultId = Object.keys(this.loadedVaults)[0] || null
        }
      }
    }
  }
})
