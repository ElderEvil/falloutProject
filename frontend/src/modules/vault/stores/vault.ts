import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import { usePolling } from '@/core/composables/usePolling'
import { ref, computed, watch } from 'vue'
import * as vaultApi from '../api/vault'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useSse } from '@/core/composables/useEventStream'
import { getAuthToken } from '@/core/utils/authToken'
import { useToast } from '@/core/composables/useToast'
import { useStorageStore } from '@/modules/storage/stores/storage'
import type { DwellerTickSnapshot } from '@/modules/dwellers/models/dweller'
import type { components } from '@/core/types/api.generated'

// Use generated API types
type VaultReadWithNumbers = components['schemas']['VaultReadWithNumbers']
type GameState = vaultApi.GameState

export type VaultWithNumbers = VaultReadWithNumbers
export type VaultScenarioOption = components['schemas']['VaultScenarioRead']
/** Difficulty mode chosen at vault creation; immutable afterwards. */
export type VaultMode = components['schemas']['VaultModeEnum']
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
  vault_id?: string
  seconds_passed?: number
  updates?: {
    resources?: ResourceTickUpdate
    crafting?: CraftingTickUpdate
    dweller_snapshot?: DwellerTickSnapshot[]
  }
}

const resourceNames: ResourceName[] = ['power', 'food', 'water']

export const useVaultStore = defineStore('vault', () => {
  const toast = useToast()
  // State
  const vaults = ref<VaultWithNumbers[]>([])
  const scenarioOptions = ref<VaultScenarioOption[]>([])
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
  } = usePolling(
    async () => {
      const vaultId = activeVaultId.value
      if (vaultId) {
        const data = await vaultApi.getVault(vaultId)
        if (activeVaultId.value === vaultId && loadedVaults.value[vaultId]) {
          loadedVaults.value[vaultId] = data
        }
      }
    },
    { interval: 10000, immediate: false }
  )

  pausePolling()

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
  async function fetchVaults(): Promise<boolean> {
    const requestGeneration = sessionGeneration
    try {
      const data = await vaultApi.getVaults()
      if (requestGeneration !== sessionGeneration) return false
      vaults.value = data
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to fetch vaults')
      return false
    }
  }

  async function fetchScenarioOptions(): Promise<boolean> {
    try {
      const options = await vaultApi.getScenarioOptions()
      scenarioOptions.value = Array.isArray(options) ? options : []
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to fetch scenario options')
      return false
    }
  }

  async function createVault(
    number: number,
    boosted: boolean,
    vaultMode: VaultMode = 'standard',
    scenario?: string | null
  ) {
    if (!(await fetchVaults())) return null
    if (vaults.value.length >= MAX_USER_VAULTS) {
      toast.warning(`Creating another vault is prohibited. Limit: ${MAX_USER_VAULTS} vaults.`)
      return null
    }

    try {
      const created = await vaultApi.createVault({
        number,
        boosted,
        vault_mode: vaultMode,
        ...(scenario ? { scenario } : {}),
      })
      // Best-effort refresh: a failed GET must not fail a successful creation (a retry would duplicate the vault).
      await fetchVaults()
      return created.id
    } catch (error) {
      handleStoreError(error, 'Failed to create vault')
      return null
    }
  }

  async function deleteVault(id: string, hardDelete = false) {
    try {
      await vaultApi.deleteVault(id, hardDelete)

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

  async function ensureVaultLoaded(id: string): Promise<void> {
    return loadVault(id, false)
  }

  async function revalidateVault(id: string): Promise<void> {
    return loadVault(id, true)
  }

  async function loadVault(id: string, revalidate: boolean): Promise<void> {
    if (!id) return
    mostRecentlyRequestedVaultId = id

    const inFlight = inFlightLoads.get(id)
    if (inFlight) return inFlight

    if (!revalidate && loadedVaults.value[id]) {
      adoptVault(id)
      return
    }

    const requestGeneration = sessionGeneration
    isLoading.value = true
    const loadPromise = (async () => {
      try {
        const data = await vaultApi.getVault(id)
        if (requestGeneration !== sessionGeneration) return
        loadedVaults.value[id] = data
        if (mostRecentlyRequestedVaultId === id) {
          adoptVault(id)
        }
      } catch (error) {
        const isCurrent =
          requestGeneration === sessionGeneration && mostRecentlyRequestedVaultId === id
        handleStoreError(error, 'Failed to load vault', isCurrent)
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

  function adoptVault(id: string): void {
    if (activeVaultId.value !== id) {
      gameState.value = null
    }
    activeVaultId.value = id
    selectedVaultId.value = id
    if (!gameState.value?.is_paused) {
      startResourcePolling(id)
    }
  }

  function applyCaps(id: string, caps: number): void {
    const vault = loadedVaults.value[id]
    if (!vault || vault.bottle_caps === caps) return
    loadedVaults.value[id] = { ...vault, bottle_caps: caps }
  }

  async function refreshVault(id: string) {
    const requestGeneration = sessionGeneration
    try {
      const data = await vaultApi.getVault(id)
      if (requestGeneration !== sessionGeneration) return
      loadedVaults.value[id] = data
      if (
        (activeVaultId.value === id || activeVaultId.value === null) &&
        (!mostRecentlyRequestedVaultId || mostRecentlyRequestedVaultId === id)
      ) {
        adoptVault(id)
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

  function currentSessionGeneration(): number {
    return sessionGeneration
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

  async function fetchGameState(vaultId: string) {
    try {
      const data = await vaultApi.getGameState(vaultId)
      if (activeVaultId.value === vaultId) {
        gameState.value = data
        if (data.is_paused) {
          stopResourcePolling()
        } else {
          startResourcePolling(vaultId)
        }
      }
      return data
    } catch (error) {
      handleStoreError(error, 'Failed to fetch game state')
      throw error
    }
  }

  async function pauseVault(vaultId: string) {
    try {
      const data = await vaultApi.pauseVault(vaultId)
      if (activeVaultId.value === vaultId) {
        gameState.value = {
          ...gameState.value,
          is_paused: true,
          paused_at: data.paused_at,
        }
        stopResourcePolling()
      }
      return data
    } catch (error) {
      handleStoreError(error, 'Failed to pause vault')
      throw error
    }
  }

  async function resumeVault(vaultId: string) {
    try {
      const data = await vaultApi.resumeVault(vaultId)
      if (activeVaultId.value === vaultId) {
        gameState.value = {
          ...gameState.value,
          is_paused: false,
          resumed_at: data.resumed_at,
        }
        startResourcePolling(vaultId)
      }
      return data
    } catch (error) {
      handleStoreError(error, 'Failed to resume vault')
      throw error
    }
  }

  async function pingPresence(vaultId: string): Promise<void> {
    try {
      await vaultApi.pingPresence(vaultId)
    } catch (error) {
      handleStoreError(error, 'Failed to send presence heartbeat', false)
    }
  }

  function startGameTickSse(vaultId: string, tokenOverride?: string): void {
    stopGameTickSse()
    const token = tokenOverride ?? getAuthToken()
    if (!token) return
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
        useStorageStore().refreshIfActive(vaultId)
        const tickData = (evt.data as { results?: GameTickUpdate } | null | undefined)?.results
        if (!tickData) return
        if (tickData.vault_id && tickData.vault_id !== vaultId) return
        const resourceUpdate = tickData.updates?.resources
        const vault = loadedVaults.value[vaultId]
        if (resourceUpdate && vault) {
          const resourceValues = Object.fromEntries(
            resourceNames
              .filter((resource) => typeof resourceUpdate[resource] === 'number')
              .map((resource) => [resource, resourceUpdate[resource]])
          ) as Partial<Pick<VaultWithNumbers, ResourceName>>
          loadedVaults.value[vaultId] = { ...vault, ...resourceValues }

          const secondsPassed = tickData.seconds_passed
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
        const completedOrders = tickData.updates?.crafting?.completed ?? 0
        if (completedOrders > 0) {
          toast.success(
            completedOrders === 1
              ? 'A workshop order is ready to collect'
              : `${completedOrders} workshop orders are ready to collect`
          )
        }

        const dwellerSnapshot = tickData.updates?.dweller_snapshot
        if (Array.isArray(dwellerSnapshot)) {
          const generation = sessionGeneration
          void import('@/modules/dwellers/stores/dwellerFilter')
            .then(({ useDwellerFilterStore }) => {
              if (sessionGeneration !== generation) return
              if (streamingVaultId !== vaultId) return
              if (activeVaultId.value && activeVaultId.value !== vaultId) return
              useDwellerFilterStore().applyDwellerTick(vaultId, dwellerSnapshot)
            })
            .catch((error: unknown) => {
              handleStoreError(error, 'Failed to load the dweller tick applier', false)
            })
        }
      }
    )
  }

  function ensureVaultStream(vaultId: string): void {
    if (streamingVaultId !== vaultId) {
      startGameTickSse(vaultId)
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

  function startResourcePolling(vaultId?: string) {
    if (!isPollingActive.value) {
      resumePolling()
    }
    if (vaultId) {
      ensureVaultStream(vaultId)
    }
  }

  function stopResourcePolling() {
    stopGameTickSse()
    pausePolling()
  }

  return {
    // State
    vaults,
    scenarioOptions,
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
    fetchScenarioOptions,
    createVault,
    deleteVault,
    ensureVaultLoaded,
    revalidateVault,
    refreshVault,
    applyCaps,
    currentSessionGeneration,
    setActiveVault,
    closeVaultTab,
    clearSession,
    fetchGameState,
    pauseVault,
    resumeVault,
    pingPresence,
    startResourcePolling,
    stopResourcePolling,
    startGameTickSse,
    stopGameTickSse,
  }
})
