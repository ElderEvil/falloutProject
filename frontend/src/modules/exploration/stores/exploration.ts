import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import axios from '@/core/plugins/axios'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useSse } from '@/core/composables/useEventStream'
import { addPendingReport } from '../composables/usePendingReports'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { ExplorationEventType } from '@/modules/exploration/models/exploration'

export interface ExplorationEvent {
  type: ExplorationEventType
  description: string
  timestamp: string
  time_elapsed_hours: number
  location_name?: string
  location_id?: string
  coord_x?: number
  coord_y?: number
  health_loss?: number
  health_restored?: number
  loot?: {
    item: {
      name: string
      rarity: string
      value: number
    }
    item_type?: string
    caps: number
  }
}

export interface LootItem {
  item_name: string
  quantity: number
  rarity: string
  item_type?: string // 'junk', 'weapon', or 'outfit'
  found_at: string
}

export interface Exploration {
  id: string
  vault_id: string
  dweller_id: string
  status: 'active' | 'completed' | 'recalled'
  duration: number
  start_time: string
  end_time: string | null
  events: ExplorationEvent[]
  loot_collected: LootItem[]
  total_distance: number
  total_caps_found: number
  enemies_encountered: number
  created_at: string
  updated_at: string
  dweller_strength: number
  dweller_perception: number
  dweller_endurance: number
  dweller_charisma: number
  dweller_intelligence: number
  dweller_agility: number
  dweller_luck: number
  stimpaks: number
  radaways: number
  health?: number
  radiation?: number
}

export interface ExplorationProgress {
  id: string
  status: 'ACTIVE' | 'COMPLETED' | 'RECALLED'
  progress_percentage: number
  time_remaining_seconds: number
  elapsed_time_seconds: number
  events: ExplorationEvent[]
  loot_collected: LootItem[]
  stimpaks: number
  radaways: number
}

export interface RewardsSummary {
  caps: number
  items: LootItem[]
  experience: number
  distance: number
  enemies_defeated: number
  events_encountered: number
  overflow_items?: LootItem[]
  progress_percentage?: number
  recalled_early?: boolean
}

export const useExplorationStore = defineStore('exploration', () => {
  const toast = useToast()
  const { filter: dwellerFilter } = useDwellerStore()

  // State
  const explorations = ref<Exploration[]>([])
  const activeExplorations = ref<Record<string, Exploration>>({})
  const lastRewards = ref<RewardsSummary | null>(null)
  const pendingSseRewards = ref<{ rewards: RewardsSummary; dwellerId: string } | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  let sseInstance: ReturnType<typeof useSse> | null = null
  let sseWatchStop: (() => void) | null = null
  let currentVaultId = ''

  // Getters
  function getExplorationByDwellerId(dwellerId: string) {
    return explorations.value.find((e) => e.dweller_id === dwellerId && e.status === 'active')
  }

  function getActiveExplorationsForVault(vaultId: string) {
    return explorations.value.filter((e) => e.vault_id === vaultId && e.status === 'active')
  }

  function isDwellerExploring(dwellerId: string) {
    return explorations.value.some((e) => e.dweller_id === dwellerId && e.status === 'active')
  }

  function startSseSubscription(vaultId: string, token: string): void {
    stopSseSubscription()
    currentVaultId = vaultId

    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    sseInstance = useSse(`${apiBase}/api/v1/stream/exploration/${vaultId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    void sseInstance.start()

    const seenEventKeys = new Set<string>()
    sseWatchStop = watch(
      () => sseInstance?.event.value,
      (evt) => {
        if (!evt || evt.event !== 'exploration') return
        const data = evt.data as Record<string, unknown> | undefined
        if (!data || typeof data.type !== 'string') return
        if (data.type === 'exploration_complete' || data.type === 'exploration_recalled') {
          const rewards = (data.rewards ?? { caps: 0, items: [], experience: 0, distance: 0 }) as RewardsSummary
          const dwellerId = (data.dweller_id as string) ?? ''
          pendingSseRewards.value = { rewards, dwellerId }

          // Persist to durable queue for offline/elsewhere viewing
          if (dwellerId) {
            const dweller = dwellerFilter.dwellers.find((d) => d.id === dwellerId)
            const dwellerName = dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller'
            addPendingReport({ vaultId: currentVaultId, dwellerId, dwellerName, rewards })
          }
          return
        }

        const explorationId = data.exploration_id as string | undefined
        const exploration = explorationId
          ? activeExplorations.value[explorationId] ?? explorations.value.find((e) => e.id === explorationId)
          : undefined
        if (!exploration) return

        const eventRecord = data.event as ExplorationEvent | undefined
        if (eventRecord?.type && eventRecord.description) {
          const key = `${eventRecord.timestamp}|${eventRecord.type}|${eventRecord.description}`
          if (!seenEventKeys.has(key)) {
            seenEventKeys.add(key)
            exploration.events.push(eventRecord)
          }
        }

        if (typeof data.total_caps_found === 'number') exploration.total_caps_found = data.total_caps_found
        if (typeof data.enemies_encountered === 'number') exploration.enemies_encountered = data.enemies_encountered
        if (typeof data.stimpaks === 'number') exploration.stimpaks = data.stimpaks
        if (typeof data.radaways === 'number') exploration.radaways = data.radaways
        if (typeof data.health === 'number') exploration.health = data.health
        if (typeof data.radiation === 'number') exploration.radiation = data.radiation
      }
    )
  }

  function stopSseSubscription(): void {
    if (sseWatchStop) {
      sseWatchStop()
      sseWatchStop = null
    }
    if (sseInstance) {
      sseInstance.stopReconnect()
      sseInstance.close()
      sseInstance = null
    }
  }

  function clearPendingSseRewards(): void {
    pendingSseRewards.value = null
  }

  // Actions
  async function sendDwellerToWasteland(
    vaultId: string,
    dwellerId: string,
    duration: number,
    token: string,
    stimpaks: number = 0,
    radaways: number = 0
  ): Promise<Exploration> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.post(
        `/api/v1/explorations/send?vault_id=${vaultId}`,
        {
          dweller_id: dwellerId,
          duration,
          stimpaks,
          radaways,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )

      const exploration = response.data
      explorations.value.push(exploration)
      activeExplorations.value[exploration.id] = exploration

      return exploration
    } catch (err) {
      handleStoreError(err, 'Failed to send dweller to wasteland')
      error.value = 'Failed to send dweller to wasteland'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchExplorationsByVault(
    vaultId: string,
    token: string,
    activeOnly = true
  ): Promise<Exploration[]> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.get(
        `/api/v1/explorations/vault/${vaultId}?active_only=${activeOnly}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )

      explorations.value = response.data
      // Update active explorations map
      activeExplorations.value = {}
      response.data
        .filter((e: Exploration) => e.status === 'active')
        .forEach((e: Exploration) => {
          activeExplorations.value[e.id] = e
        })

      return response.data
    } catch (err) {
      handleStoreError(err, 'Failed to fetch explorations')
      error.value = 'Failed to fetch explorations'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchExplorationDetails(
    explorationId: string,
    token: string
  ): Promise<Exploration> {
    try {
      const response = await axios.get(`/api/v1/explorations/${explorationId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })

      // Update in explorations list
      const index = explorations.value.findIndex((e) => e.id === explorationId)
      if (index !== -1) {
        explorations.value[index] = response.data
      }

      // Update in active explorations
      if (response.data.status === 'active') {
        activeExplorations.value[explorationId] = response.data
      } else {
        delete activeExplorations.value[explorationId]
      }

      return response.data
    } catch (err) {
      handleStoreError(err, 'Failed to fetch exploration details')
      throw err
    }
  }

  async function fetchExplorationProgress(
    explorationId: string,
    token: string
  ): Promise<ExplorationProgress> {
    try {
      const response = await axios.get(`/api/v1/explorations/${explorationId}/progress`, {
        headers: { Authorization: `Bearer ${token}` },
      })

      return response.data as ExplorationProgress
    } catch (err) {
      handleStoreError(err, 'Failed to fetch exploration progress')
      throw err
    }
  }

  async function recallDweller(explorationId: string, token: string): Promise<any> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.post(
        `/api/v1/explorations/${explorationId}/recall`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )

      const { exploration, rewards_summary } = response.data
      lastRewards.value = rewards_summary

      // Update exploration in state
      const index = explorations.value.findIndex((e) => e.id === explorationId)
      if (index !== -1) {
        explorations.value[index] = exploration
      }

      // Remove from active explorations
      delete activeExplorations.value[explorationId]

      toast.success('Dweller recalled from wasteland!')
      return response.data
    } catch (err) {
      handleStoreError(err, 'Failed to recall dweller')
      error.value = 'Failed to recall dweller'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function completeExploration(explorationId: string, token: string): Promise<any> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.post(
        `/api/v1/explorations/${explorationId}/complete`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )

      const { exploration, rewards_summary } = response.data
      lastRewards.value = rewards_summary

      // Update exploration in state
      const index = explorations.value.findIndex((e) => e.id === explorationId)
      if (index !== -1) {
        explorations.value[index] = exploration
      }

      // Remove from active explorations
      delete activeExplorations.value[explorationId]

      toast.success('Exploration completed successfully!')
      return response.data
    } catch (err) {
      handleStoreError(err, 'Failed to complete exploration')
      error.value = 'Failed to complete exploration'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    explorations,
    activeExplorations,
    lastRewards,
    pendingSseRewards,
    isLoading,
    error,
    // Getters
    getExplorationByDwellerId,
    getActiveExplorationsForVault,
    isDwellerExploring,
    // Actions
    sendDwellerToWasteland,
    fetchExplorationsByVault,
    fetchExplorationDetails,
    fetchExplorationProgress,
    recallDweller,
    completeExploration,
    startSseSubscription,
    stopSseSubscription,
    clearPendingSseRewards,
    clearError,
  }
})
