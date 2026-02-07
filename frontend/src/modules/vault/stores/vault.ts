import { defineStore } from 'pinia'
import { useLocalStorage, useIntervalFn } from '@vueuse/core'
import { ref, computed } from 'vue'
import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

// Use generated API types
type VaultReadWithNumbers = components['schemas']['VaultReadWithNumbers']

// Use the generated type directly without overriding resource_warnings
export interface VaultWithNumbers extends VaultReadWithNumbers {
  // resource_warnings is already defined in VaultReadWithNumbers as { [key: string]: string }[]
}

// GameState type (not yet in API schemas)
interface GameState {
  is_paused: boolean
  paused_at?: string | null
  resumed_at?: string | null
  total_game_time?: number
}

export const useVaultStore = defineStore('vault', () => {
  // State
  const vaults = ref<VaultWithNumbers[]>([])
  const selectedVaultId = useLocalStorage<string | null>('selectedVaultId', null)
  const loadedVaults = ref<Record<string, VaultWithNumbers>>({})
  const activeVaultId = ref<string | null>(null)
  const isLoading = ref(false)
  const gameState = ref<GameState | null>(null)

  // Polling control
  const {
    pause: pausePolling,
    resume: resumePolling,
    isActive: isPollingActive,
  } = useIntervalFn(
    async () => {
      if (activeVaultId.value) {
        try {
          const response = await axios.get(`/api/v1/vaults/${activeVaultId.value}`)
          if (loadedVaults.value[activeVaultId.value]) {
            loadedVaults.value[activeVaultId.value] = response.data
          }
        } catch (error) {
          console.error('Failed to poll resources', error)
        }
      }
    },
    10000,
    { immediate: false }
  )

  // Getters
  const selectedVault = computed(
    () => vaults.value.find((vault) => vault.id === selectedVaultId.value) || null
  )
  const activeVault = computed(() =>
    activeVaultId.value ? loadedVaults.value[activeVaultId.value] : null
  )
  const loadedVaultIds = computed(() => Object.keys(loadedVaults.value))

  // Actions
  async function fetchVaults(token: string) {
    try {
      const response = await axios.get('/api/v1/vaults/my', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      vaults.value = response.data
    } catch (error) {
      console.error('Failed to fetch vaults', error)
    }
  }

  async function createVault(number: number, boosted: boolean, token: string) {
    try {
      await axios.post(
        '/api/v1/vaults/initiate',
        { number, boosted },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      await fetchVaults(token)
    } catch (error) {
      console.error('Failed to create vault', error)
    }
  }

  async function deleteVault(id: string, token: string, hardDelete = false) {
    try {
      const url = hardDelete ? `/api/v1/vaults/${id}?hard_delete=true` : `/api/v1/vaults/${id}`

      await axios.delete(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      vaults.value = vaults.value.filter((vault) => vault.id !== id)
      if (loadedVaults.value[id]) {
        delete loadedVaults.value[id]
      }
      if (activeVaultId.value === id) {
        activeVaultId.value = Object.keys(loadedVaults.value)[0] || null
      }

      // Show appropriate notification
      if (hardDelete) {
        console.warn('Vault permanently deleted')
      } else {
        console.info('Vault soft deleted - Data preserved for potential recovery')
      }
    } catch (error) {
      console.error('Failed to delete vault', error)
    }
  }

  async function loadVault(id: string, token: string) {
    isLoading.value = true
    try {
      const response = await axios.get(`/api/v1/vaults/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      loadedVaults.value[id] = response.data
      activeVaultId.value = id
    } catch (error) {
      console.error('Failed to load vault', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function refreshVault(id: string, token: string) {
    try {
      const response = await axios.get(`/api/v1/vaults/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      loadedVaults.value[id] = response.data
      activeVaultId.value = id
    } catch (error) {
      console.error('Failed to refresh vault', error)
      throw error
    }
  }

  function setActiveVault(id: string) {
    if (loadedVaults.value[id]) {
      activeVaultId.value = id
    }
  }

  function closeVaultTab(id: string) {
    if (loadedVaults.value[id]) {
      delete loadedVaults.value[id]
      if (activeVaultId.value === id) {
        activeVaultId.value = Object.keys(loadedVaults.value)[0] || null
      }
    }
  }

  async function fetchGameState(vaultId: string, token: string) {
    try {
      const response = await axios.get(`/api/v1/game/vaults/${vaultId}/game-state`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      gameState.value = response.data
      return response.data
    } catch (error) {
      console.error('Failed to fetch game state', error)
      throw error
    }
  }

  async function pauseVault(vaultId: string, token: string) {
    try {
      const response = await axios.post(
        `/api/v1/game/vaults/${vaultId}/pause`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (gameState.value) {
        gameState.value.is_paused = true
        gameState.value.paused_at = response.data.paused_at
      }
      stopResourcePolling()
      return response.data
    } catch (error) {
      console.error('Failed to pause vault', error)
      throw error
    }
  }

  async function resumeVault(vaultId: string, token: string) {
    try {
      const response = await axios.post(
        `/api/v1/game/vaults/${vaultId}/resume`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (gameState.value) {
        gameState.value.is_paused = false
        gameState.value.resumed_at = response.data.resumed_at
      }
      startResourcePolling()
      return response.data
    } catch (error) {
      console.error('Failed to resume vault', error)
      throw error
    }
  }

  function startResourcePolling() {
    if (!isPollingActive.value) {
      resumePolling()
    }
  }

  function stopResourcePolling() {
    if (isPollingActive.value) {
      pausePolling()
    }
  }

  return {
    // State
    vaults,
    selectedVaultId,
    loadedVaults,
    activeVaultId,
    isLoading,
    gameState,
    // Getters
    selectedVault,
    activeVault,
    loadedVaultIds,
    // Actions
    fetchVaults,
    createVault,
    deleteVault,
    loadVault,
    refreshVault,
    setActiveVault,
    closeVaultTab,
    fetchGameState,
    pauseVault,
    resumeVault,
    startResourcePolling,
    stopResourcePolling,
  }
})
