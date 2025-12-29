import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import { useRouter } from 'vue-router'

interface GameState {
  is_paused: boolean
  is_active: boolean
  last_tick_time: string
  paused_at: string | null
  resumed_at: string | null
  total_game_time: number
}

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
  game_state?: GameState
}

export const useVaultStore = defineStore('vault', {
  state: () => ({
    vaults: [] as Vault[],
    selectedVaultId: localStorage.getItem('selectedVaultId') as string | null,
    loadedVaults: {} as Record<string, Vault>,
    activeVaultId: null as string | null,
    isLoading: false,
    gameState: null as GameState | null,
    resourcePollingInterval: null as number | null
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
    async createVault(number: number, token: string) {
      try {
        await axios.post(
          '/api/v1/vaults/initiate',
          { number },
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
    async refreshVault(id: string, token: string) {
      try {
        const response = await axios.get(`/api/v1/vaults/${id}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        this.loadedVaults[id] = response.data
        this.activeVaultId = id
      } catch (error) {
        console.error('Failed to refresh vault', error)
        throw error
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
    },
    async fetchGameState(vaultId: string, token: string) {
      try {
        const response = await axios.get(`/api/v1/game/vaults/${vaultId}/game-state`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        this.gameState = response.data
        return response.data
      } catch (error) {
        console.error('Failed to fetch game state', error)
        throw error
      }
    },
    async pauseVault(vaultId: string, token: string) {
      try {
        const response = await axios.post(
          `/api/v1/game/vaults/${vaultId}/pause`,
          {},
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        )
        // Update game state
        if (this.gameState) {
          this.gameState.is_paused = true
          this.gameState.paused_at = response.data.paused_at
        }
        // Stop resource polling
        this.stopResourcePolling()
        return response.data
      } catch (error) {
        console.error('Failed to pause vault', error)
        throw error
      }
    },
    async resumeVault(vaultId: string, token: string) {
      try {
        const response = await axios.post(
          `/api/v1/game/vaults/${vaultId}/resume`,
          {},
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        )
        // Update game state
        if (this.gameState) {
          this.gameState.is_paused = false
          this.gameState.resumed_at = response.data.resumed_at
        }
        // Restart resource polling
        this.startResourcePolling(vaultId, token)
        return response.data
      } catch (error) {
        console.error('Failed to resume vault', error)
        throw error
      }
    },
    startResourcePolling(vaultId: string, token: string) {
      // Clear existing interval
      this.stopResourcePolling()

      // Poll vault resources every 10 seconds
      this.resourcePollingInterval = window.setInterval(async () => {
        try {
          const response = await axios.get(`/api/v1/vaults/${vaultId}`, {
            headers: { Authorization: `Bearer ${token}` }
          })
          // Update loaded vault with fresh data
          if (this.loadedVaults[vaultId]) {
            this.loadedVaults[vaultId] = response.data
          }
        } catch (error) {
          console.error('Failed to poll resources', error)
        }
      }, 10000)
    },
    stopResourcePolling() {
      if (this.resourcePollingInterval !== null) {
        clearInterval(this.resourcePollingInterval)
        this.resourcePollingInterval = null
      }
    }
  }
})
