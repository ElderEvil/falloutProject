import { defineStore } from 'pinia'
import { useLocalStorage, useIntervalFn } from '@vueuse/core'
import { ref, computed, watch } from 'vue'
import axios from '@/core/plugins/axios'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useSse } from '@/core/composables/useEventStream'
import { useToast } from '@/core/composables/useToast'
import type { components } from '@/core/types/api.generated'

// Use generated API types
type VaultReadWithNumbers = components['schemas']['VaultReadWithNumbers']

export type VaultWithNumbers = VaultReadWithNumbers
export const MAX_USER_VAULTS = 3

type ResourceName = 'power' | 'food' | 'water'
type ResourceRates = Record<ResourceName, number>

interface ResourceTickUpdate {
  power?: number
  food?: number
  water?: number
  events?: {
    production?: Partial<ResourceRates>
    consumption?: Partial<ResourceRates>
  }
}

interface CraftingTickUpdate {
  completed?: number
}

interface GameTickUpdate {
  seconds_passed?: number
  updates?: {
    resources?: ResourceTickUpdate
    crafting?: CraftingTickUpdate
  }
}

const resourceNames: ResourceName[] = ['power', 'food', 'water']

// GameState type (not yet in API schemas)
interface GameState {
  is_paused: boolean
  paused_at?: string | null
  resumed_at?: string | null
  total_game_time?: number
}

export const useVaultStore = defineStore('vault', () => {
  const toast = useToast()
  // State
  const vaults = ref<VaultWithNumbers[]>([])
  const selectedVaultId = useLocalStorage<string | null>('selectedVaultId', null)
  const loadedVaults = ref<Record<string, VaultWithNumbers>>({})
  const resourceRates = ref<Record<string, ResourceRates>>({})
  const activeVaultId = ref<string | null>(null)
  const isLoading = ref(false)
  const gameState = ref<GameState | null>(null)
  let gameTickSse: ReturnType<typeof useSse> | null = null
  let stopTickWatch: (() => void) | null = null
  let sessionGeneration = 0
  // Vault the live SSE belongs to, so re-asserting the same stream is a no-op.
  let streamingVaultId: string | null = null
  // Most recently requested vault id; a stale GET for an older id only caches.
  let mostRecentlyRequestedVaultId: string | null = null
  // Deduplicates concurrent loads for the same vault id.
  const inFlightLoads = new Map<string, Promise<void>>()

  // Polling control
  const {
    pause: pausePolling,
    resume: resumePolling,
    isActive: isPollingActive,
  } = useIntervalFn(
    async () => {
      const vaultId = activeVaultId.value
      if (vaultId) {
        try {
          const response = await axios.get(`/api/v1/vaults/${vaultId}`)
          if (activeVaultId.value === vaultId && loadedVaults.value[vaultId]) {
            loadedVaults.value[vaultId] = response.data
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
  // activeVaultId is in-memory only; fall back to the persisted selection so
  // navigation survives a reload.
  const currentVaultId = computed(() => activeVaultId.value ?? selectedVaultId.value)

  // Actions
  async function fetchVaults(token: string): Promise<boolean> {
    const requestGeneration = sessionGeneration
    try {
      const response = await axios.get('/api/v1/vaults/my', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (requestGeneration !== sessionGeneration) return false
      vaults.value = response.data
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to fetch vaults')
      return false
    }
  }

  async function createVault(number: number, boosted: boolean, token: string) {
    if (!(await fetchVaults(token))) return false
    if (vaults.value.length >= MAX_USER_VAULTS) {
      toast.warning(`Creating another vault is prohibited. Limit: ${MAX_USER_VAULTS} vaults.`)
      return false
    }

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
      // Best-effort refresh: a failed GET must not fail a successful creation (a retry would duplicate the vault).
      await fetchVaults(token)
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to create vault')
      return false
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
      if (selectedVaultId.value === id) {
        selectedVaultId.value = activeVaultId.value
      }

      // Show appropriate notification
      if (hardDelete) {
        toast.warning('Vault permanently deleted')
      } else {
        console.info('Vault soft deleted - Data preserved for potential recovery')
      }
    } catch (error) {
      handleStoreError(error, 'Failed to delete vault')
    }
  }

  async function ensureVaultLoaded(id: string, token: string): Promise<void> {
    if (!id || !token) return
    mostRecentlyRequestedVaultId = id

    if (loadedVaults.value[id]) {
      adoptVault(id, token)
      return
    }

    const inFlight = inFlightLoads.get(id)
    if (inFlight) return inFlight

    const requestGeneration = sessionGeneration
    isLoading.value = true
    const loadPromise = (async () => {
      try {
        const response = await axios.get(`/api/v1/vaults/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (requestGeneration !== sessionGeneration) return
        loadedVaults.value[id] = response.data
        if (mostRecentlyRequestedVaultId === id) {
          adoptVault(id, token)
        }
      } catch (error) {
        handleStoreError(error, 'Failed to load vault')
        throw error
      } finally {
        if (requestGeneration === sessionGeneration) {
          inFlightLoads.delete(id)
          isLoading.value = inFlightLoads.size > 0
        }
      }
    })()
    inFlightLoads.set(id, loadPromise)
    return loadPromise
  }

  function adoptVault(id: string, token: string): void {
    if (activeVaultId.value !== id) {
      gameState.value = null
    }
    activeVaultId.value = id
    selectedVaultId.value = id
    if (!gameState.value?.is_paused) {
      startResourcePolling(id, token)
    }
  }

  async function refreshVault(id: string, token: string) {
    const requestGeneration = sessionGeneration
    try {
      const response = await axios.get(`/api/v1/vaults/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (requestGeneration !== sessionGeneration) return
      loadedVaults.value[id] = response.data
      if (
        (activeVaultId.value === id || activeVaultId.value === null) &&
        (!mostRecentlyRequestedVaultId || mostRecentlyRequestedVaultId === id)
      ) {
        adoptVault(id, token)
      }
    } catch (error) {
      handleStoreError(error, 'Failed to refresh vault')
      throw error
    }
  }

  function setActiveVault(id: string) {
    if (loadedVaults.value[id]) {
      activeVaultId.value = id
      selectedVaultId.value = id
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

  function clearSession(): void {
    ++sessionGeneration
    stopResourcePolling()
    inFlightLoads.clear()
    mostRecentlyRequestedVaultId = null
    vaults.value = []
    loadedVaults.value = {}
    resourceRates.value = {}
    activeVaultId.value = null
    selectedVaultId.value = null
    gameState.value = null
    isLoading.value = false
  }

  async function fetchGameState(vaultId: string, token: string) {
    try {
      const response = await axios.get(`/api/v1/game/vaults/${vaultId}/game-state`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (activeVaultId.value === vaultId) {
        gameState.value = response.data
        if (response.data.is_paused) {
          stopResourcePolling()
        } else {
          startResourcePolling(vaultId, token)
        }
      }
      return response.data
    } catch (error) {
      handleStoreError(error, 'Failed to fetch game state')
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
      if (activeVaultId.value === vaultId) {
        gameState.value = {
          ...gameState.value,
          is_paused: true,
          paused_at: response.data.paused_at,
        }
        stopResourcePolling()
      }
      return response.data
    } catch (error) {
      handleStoreError(error, 'Failed to pause vault')
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
      if (activeVaultId.value === vaultId) {
        gameState.value = {
          ...gameState.value,
          is_paused: false,
          resumed_at: response.data.resumed_at,
        }
        startResourcePolling(vaultId, token)
      }
      return response.data
    } catch (error) {
      handleStoreError(error, 'Failed to resume vault')
      throw error
    }
  }

  function startGameTickSse(vaultId: string, token: string): void {
    stopGameTickSse()
    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    const stream = useSse(`${apiBase}/api/v1/stream/game/${vaultId}/ticks`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    gameTickSse = stream
    streamingVaultId = vaultId
    void stream.start()

    stopTickWatch = watch(
      () => stream.event.value,
      (evt) => {
        if (!evt || evt.event !== 'tick') return
        const tickData = evt.data as GameTickUpdate | undefined
        const resourceUpdate = tickData?.updates?.resources
        const vault = loadedVaults.value[vaultId]
        if (resourceUpdate && vault) {
          const resourceValues = Object.fromEntries(
            resourceNames
              .filter((resource) => typeof resourceUpdate[resource] === 'number')
              .map((resource) => [resource, resourceUpdate[resource]])
          ) as Partial<Pick<VaultWithNumbers, ResourceName>>
          loadedVaults.value[vaultId] = { ...vault, ...resourceValues }

          const secondsPassed = tickData?.seconds_passed
          if (typeof secondsPassed === 'number' && secondsPassed > 0) {
            const production = resourceUpdate.events?.production ?? {}
            const consumption = resourceUpdate.events?.consumption ?? {}
            resourceRates.value[vaultId] = Object.fromEntries(
              resourceNames.map((resource) => [
                resource,
                (((production[resource] ?? 0) - (consumption[resource] ?? 0)) / secondsPassed) * 60,
              ])
            ) as ResourceRates
          }
        }

        // A finished workshop order surfaces beyond the bell (progression red line).
        const completedOrders = tickData?.updates?.crafting?.completed ?? 0
        if (completedOrders > 0) {
          toast.success(
            completedOrders === 1
              ? 'A workshop order is ready to collect'
              : `${completedOrders} workshop orders are ready to collect`
          )
        }
      }
    )
  }

  function ensureVaultStream(vaultId: string, token: string): void {
    if (streamingVaultId !== vaultId) {
      startGameTickSse(vaultId, token)
    }
  }

  function stopGameTickSse(): void {
    stopTickWatch?.()
    stopTickWatch = null
    if (gameTickSse) {
      gameTickSse.stopReconnect()
      gameTickSse.close()
      gameTickSse = null
    }
    streamingVaultId = null
  }

  function startResourcePolling(vaultId?: string, token?: string) {
    if (!isPollingActive.value) {
      resumePolling()
    }
    if (vaultId && token) {
      ensureVaultStream(vaultId, token)
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
    resourceRates,
    activeVaultId,
    isLoading,
    gameState,
    // Getters
    selectedVault,
    activeVault,
    currentVaultId,
    loadedVaultIds,
    // Actions
    fetchVaults,
    createVault,
    deleteVault,
    ensureVaultLoaded,
    refreshVault,
    setActiveVault,
    closeVaultTab,
    clearSession,
    fetchGameState,
    pauseVault,
    resumeVault,
    startResourcePolling,
    stopResourcePolling,
    startGameTickSse,
    stopGameTickSse,
  }
})
