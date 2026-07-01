import { defineStore, acceptHMRUpdate } from 'pinia'
import { useLocalStorage, useIntervalFn } from '@vueuse/core'
import { ref, computed, watch } from 'vue'
import * as http from '@/core/plugins/httpClient'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useSse } from '@/core/composables/useEventStream'
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
  const gameTickSse = ref<ReturnType<typeof useSse> | null>(null)

  // Polling control
  const {
    pause: pausePolling,
    resume: resumePolling,
    isActive: isPollingActive,
  } = useIntervalFn(
    async () => {
      if (activeVaultId.value) {
        try {
          const vault = await http.apiGet<VaultWithNumbers>(
            `/api/v1/vaults/${activeVaultId.value}`
          )
          if (loadedVaults.value[activeVaultId.value]) {
            loadedVaults.value[activeVaultId.value] = vault
          }
        } catch (error) {
          handleStoreError(error, 'Failed to poll resources')
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

  // Top-level SSE event watcher — created ONCE in store-init scope, NOT inside startGameTickSse
  watch(
    () => {
      const sse = gameTickSse.value
      if (!sse) return undefined
      return sse.event?.value
    },
    (evt) => {
      if (!evt || evt.event !== 'tick') return
      const tickData = evt.data as Record<string, unknown> | undefined
      const currentId = activeVaultId.value
      if (tickData && currentId && loadedVaults.value[currentId]) {
        loadedVaults.value[currentId] = tickData as unknown as VaultWithNumbers
      }
    }
  )

  // Actions
  async function fetchVaults(token: string) {
    try {
      vaults.value = await http.apiGet<VaultWithNumbers[]>('/api/v1/vaults/my', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
    } catch (error) {
      handleStoreError(error, 'Failed to fetch vaults')
    }
  }

  async function createVault(number: number, boosted: boolean, token: string) {
    try {
      await http.apiPost(
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
      handleStoreError(error, 'Failed to create vault')
    }
  }

  async function deleteVault(id: string, token: string, hardDelete = false) {
    try {
      const url = hardDelete ? `/api/v1/vaults/${id}?hard_delete=true` : `/api/v1/vaults/${id}`

      await http.apiDelete(url, {
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
      handleStoreError(error, 'Failed to delete vault')
    }
  }

  async function loadVault(id: string, token: string) {
    isLoading.value = true
    try {
      loadedVaults.value[id] = await http.apiGet<VaultWithNumbers>(
        `/api/v1/vaults/${id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      activeVaultId.value = id
      startGameTickSse(id, token)
    } catch (error) {
      handleStoreError(error, 'Failed to load vault')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function refreshVault(id: string, token: string) {
    try {
      loadedVaults.value[id] = await http.apiGet<VaultWithNumbers>(
        `/api/v1/vaults/${id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      activeVaultId.value = id
      startGameTickSse(id, token)
    } catch (error) {
      handleStoreError(error, 'Failed to refresh vault')
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
        stopGameTickSse()
      }
    }
  }

  async function fetchGameState(vaultId: string, token: string) {
    try {
      const state = await http.apiGet<GameState>(
        `/api/v1/game/vaults/${vaultId}/game-state`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      gameState.value = state
      return state
    } catch (error) {
      handleStoreError(error, 'Failed to fetch game state')
      throw error
    }
  }

  async function pauseVault(vaultId: string, token: string) {
    try {
      const result = await http.apiPost<{ paused_at: string }>(
        `/api/v1/game/vaults/${vaultId}/pause`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (gameState.value) {
        gameState.value.is_paused = true
        gameState.value.paused_at = result.paused_at
      }
      stopResourcePolling()
      return result
    } catch (error) {
      handleStoreError(error, 'Failed to pause vault')
      throw error
    }
  }

  async function resumeVault(vaultId: string, token: string) {
    try {
      const result = await http.apiPost<{ resumed_at: string }>(
        `/api/v1/game/vaults/${vaultId}/resume`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (gameState.value) {
        gameState.value.is_paused = false
        gameState.value.resumed_at = result.resumed_at
      }
      startResourcePolling(vaultId, token)
      return result
    } catch (error) {
      handleStoreError(error, 'Failed to resume vault')
      throw error
    }
  }

  function startGameTickSse(vaultId: string, token: string): void {
    stopGameTickSse()
    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    const sse = useSse(`${apiBase}/api/v1/stream/game/${vaultId}/ticks`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    gameTickSse.value = sse
    sse.start()
  }

  function stopGameTickSse(): void {
    if (gameTickSse.value) {
      gameTickSse.value.stopReconnect()
      gameTickSse.value.close()
      gameTickSse.value = null
    }
  }

  function startResourcePolling(vaultId?: string, token?: string) {
    if (!isPollingActive.value) {
      resumePolling()
    }
    if (vaultId && token) {
      startGameTickSse(vaultId, token)
    }
  }

  function stopResourcePolling() {
    stopGameTickSse()
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
    startGameTickSse,
    stopGameTickSse,
  }
})

// HMR support
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useVaultStore, import.meta.hot))
}
